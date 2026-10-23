"""One chronological warmup validation split; locked before evaluation is scored."""
import hashlib
import itertools
import json
import numpy as np
import pandas as pd
from src.data.download import sha256, save_json
from src.evaluation.metrics import qlike_loss
from src.evaluation.walkforward import Task, select_training
from src.models.enet import ElasticNetRV
from src.models.xgb import XGBoostRV
from src.models.ml_common import load_ml_config, ml_config_hash
from src.utils.config import ROOT, load_config, protocol_hash

LOCK = ROOT / "outputs/model_selection/backend3_locked.json"


def warmup_splits(dataset, symbol, task, config, options):
    tuning = options["tuning"]
    cutoff = pd.Timestamp(tuning["train_target_end"], tz="UTC")
    start = pd.Timestamp(tuning["validation_target_start"], tz="UTC")
    end = pd.Timestamp(tuning["validation_target_end"], tz="UTC")
    warmup_end = pd.Timestamp(config["data"]["warmup_end"], tz="UTC")
    if cutoff >= start or end > warmup_end or start > end:
        raise ValueError("Tuning split must be chronological and wholly within warmup")
    data = dataset.loc[dataset.symbol.eq(symbol)].sort_values("origin_date")
    features = options["features"]["core"] + options["features"]["volume"]
    train, lower, train_end = select_training(data, task, features, cutoff, config, "expanding")
    mask = data[f"target_start_h{task.horizon}"].ge(start) & data[f"target_end_h{task.horizon}"].le(end)
    mask &= data[f"target_segment_h{task.horizon}"].eq("warmup")
    mask &= np.isfinite(data[features]).all(axis=1) & data[task.y_col].gt(0) & np.isfinite(data[task.y_col])
    validation = data.loc[mask].copy()
    if len(train) < tuning["min_train_rows"] or len(validation) < tuning["min_validation_rows"]:
        raise ValueError(f"Insufficient warmup train/validation rows for {symbol}/h{task.horizon}")
    return train, validation, {"train_start": lower, "train_end": train_end, "refit_origin": cutoff}


def warmup_fingerprint(dataset, config, options):
    digest = hashlib.sha256()
    features = options["features"]["core"] + options["features"]["volume"]
    for symbol in config["data"]["symbols"]:
        for horizon in [1, 7]:
            task = Task(horizon)
            train, validation, _ = warmup_splits(dataset, symbol, task, config, options)
            columns = ["symbol", "origin_date", *features, task.y_col, task.ylog_col,
                       f"target_start_h{horizon}", f"target_end_h{horizon}"]
            for frame in [train, validation]:
                digest.update(pd.util.hash_pandas_object(frame[columns], index=False).to_numpy().tobytes())
    return digest.hexdigest()


def candidate_settings(name, options):
    if name == "enet":
        return [dict(alpha=a, l1_ratio=l) for a, l in itertools.product(
            options["enet"]["alpha_grid"], options["enet"]["l1_ratio_grid"])]
    return [dict(max_depth=d, learning_rate=e, num_boost_round=n) for d, e, n in itertools.product(
        options["xgboost"]["max_depth_grid"], options["xgboost"]["learning_rate_grid"],
        options["xgboost"]["num_boost_round_grid"])]


def tune(dataset, config=None, options=None):
    config = config or load_config()
    options = options or load_ml_config()
    selected, records, splits = {}, [], []
    for symbol in config["data"]["symbols"]:
        selected[symbol] = {}
        for horizon in [1, 7]:
            task = Task(horizon)
            train, validation, context = warmup_splits(dataset, symbol, task, config, options)
            context.update(symbol=symbol, window="warmup_validation", horizon_days=horizon)
            splits.append({"symbol": symbol, "horizon_days": horizon, "n_train": len(train),
                "n_validation": len(validation), "train_feature_end": train.origin_date.max().isoformat(),
                "train_label_end": train[f"target_end_h{horizon}"].max().isoformat(),
                "validation_target_start": validation[f"target_start_h{horizon}"].min().isoformat(),
                "validation_target_end": validation[f"target_end_h{horizon}"].max().isoformat()})
            selected[symbol][str(horizon)] = {}
            for name, cls in [("enet", ElasticNetRV), ("xgboost", XGBoostRV)]:
                best = None
                for number, settings in enumerate(candidate_settings(name, options)):
                    model = cls(settings=settings, options=options)
                    model.set_context(context)
                    model.fit(train, task)
                    prediction = model.predict(validation[["symbol", "origin_date", *model.features]], task)
                    score = float(qlike_loss(validation[task.y_col], prediction).mean())
                    row = {"symbol": symbol, "horizon_days": horizon, "model": name,
                           "candidate": number, "settings": json.dumps(settings, sort_keys=True),
                           "validation_QLIKE": score, "n_train": len(train), "n_validation": len(validation)}
                    records.append(row)
                    if best is None or score < best[0]:
                        best = (score, settings)
                selected[symbol][str(horizon)][name] = best[1]
                print(f"Locked warmup choice {symbol}/{name}/h{horizon}: QLIKE={best[0]:.6f}, {best[1]}", flush=True)
    return {"selected_parameters": selected, "splits": splits,
            "warmup_fingerprint": warmup_fingerprint(dataset, config, options)}, pd.DataFrame(records)


def prepare_selection(dataset, meta, config, options):
    fingerprint = warmup_fingerprint(dataset, config, options)
    if LOCK.exists():
        locked = json.loads(LOCK.read_text(encoding="utf-8"))
        for key, expected in [("ml_config_sha256", ml_config_hash()), ("protocol_sha256", protocol_hash(config)),
                              ("dataset_sha256", meta["dataset_sha256"]), ("warmup_fingerprint", fingerprint)]:
            if locked[key] != expected:
                raise ValueError("Locked selection differs from current inputs: " + key)
        return locked
    selection, scores = tune(dataset, config, options)
    selection.update(ml_config_sha256=ml_config_hash(), protocol_sha256=protocol_hash(config),
                     dataset_sha256=meta["dataset_sha256"], selection_period="warmup_only",
                     evaluation_used_for_selection=False, holdout_used_for_selection=False,
                     selection_metric="QLIKE", seed=options["general"]["seed"],
                     ablation="same_hyperparameters_and_training_eligibility_as_full_model")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(LOCK.parent / "backend3_tuning_scores.csv", index=False)
    save_json(LOCK, selection)
    return json.loads(LOCK.read_text(encoding="utf-8"))


def main():
    config, options = load_config(), load_ml_config()
    path = ROOT / "data/processed/dataset.parquet"
    meta = json.loads((path.parent / "dataset_meta.json").read_text(encoding="utf-8"))
    if sha256(path) != meta["dataset_sha256"] or protocol_hash(config) != meta["protocol_sha256"]:
        raise ValueError("Stale shared dataset")
    prepare_selection(pd.read_parquet(path), meta, config, options)


if __name__ == "__main__":
    main()

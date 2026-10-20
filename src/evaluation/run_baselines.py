"""python -m src.evaluation.run_baselines -> outputs/forecasts/{model}__{asset}__h{h}.parquet"""
from src.evaluation.baselines import BASELINES
from src.evaluation.walkforward import run_all_assets
from src.evaluation.validate import validate_forecasts
from src.utils.config import load_config, ROOT
from src.utils.io import read_table, write_table


def eval_kwargs(cfg):
    e = cfg["evaluation"]
    return dict(scheme=e["scheme"], min_train=e["min_train"], window=e["rolling_window"],
                refit_every=e["refit_every"], test_start=e["test_start"], test_end=e["test_end"])


def main():
    cfg = load_config()
    ds = read_table(ROOT / "data/processed/dataset.parquet")
    out = ROOT / "outputs/forecasts"
    for h in cfg["horizons"]:
        for name, cls in BASELINES.items():
            fc = run_all_assets(ds, cls, h, **eval_kwargs(cfg))
            errs = validate_forecasts(fc, ds, f"{name}_h{h}")
            assert not errs, errs
            for a, g in fc.groupby("asset"):
                write_table(g, out / f"{name}__{a}__h{h}.parquet")
            print(f"{name:12s} h={h}: {len(fc)} forecasts")


if __name__ == "__main__":
    main()

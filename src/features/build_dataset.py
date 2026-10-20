"""python -m src.features.build_dataset  ->  data/processed/dataset.parquet + dataset_meta.json"""
import json
import pandas as pd

from src.features.build_features import build_dataset
from src.features.schema import FEATURE_COLS, target_cols
from src.utils.config import load_config, ROOT
from src.utils.io import read_table, write_table


def main():
    cfg = load_config()
    raw = ROOT / "data/raw"
    bars = {a: read_table(raw / f"{a}_5m.parquet") for a in cfg["assets"]}
    macro = read_table(raw / "macro.parquet")
    ds = build_dataset(bars, macro, cfg)
    path = write_table(ds, ROOT / "data/processed/dataset.parquet")
    meta = {
        "data_source": cfg["data_source"], "assets": cfg["assets"], "horizons": cfg["horizons"],
        "rows": int(len(ds)), "date_min": str(ds["date"].min().date()), "date_max": str(ds["date"].max().date()),
        "feature_cols": FEATURE_COLS, "target_cols": target_cols(cfg["horizons"]),
        "regime_counts": ds["regime"].value_counts().to_dict(),
        "nan_share": ds[FEATURE_COLS].isna().mean().round(4).to_dict(),
    }
    (ROOT / "data/processed/dataset_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print("wrote", path, ds.shape)
    print(json.dumps({k: meta[k] for k in ("data_source", "rows", "date_min", "date_max", "regime_counts")}, indent=2))


if __name__ == "__main__":
    main()

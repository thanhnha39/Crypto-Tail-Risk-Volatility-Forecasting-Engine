"""Strict Parquet I/O: do not silently substitute CSV or synthetic data."""
from pathlib import Path
import pandas as pd

def write_table(frame, path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_parquet(path,index=False,compression="zstd")
    return path

def read_table(path):
    return pd.read_parquet(path)

def table_exists(path):
    return Path(path).exists()

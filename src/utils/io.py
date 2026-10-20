"""Đọc/ghi bảng: parquet nếu có pyarrow, nếu không fallback csv.gz (cùng tên, đổi đuôi)."""
import warnings
from pathlib import Path
import pandas as pd

try:
    import pyarrow  # noqa: F401
    HAS_PARQUET = True
except ImportError:  # pragma: no cover
    HAS_PARQUET = False

DATE_COLS = ["date", "origin_date", "target_date", "train_end", "timestamp"]


def _alt(path: Path) -> Path:
    return path.with_name(path.name.replace(".parquet", ".csv.gz"))


def write_table(df: pd.DataFrame, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet" and HAS_PARQUET:
        df.to_parquet(path, index=False)
        return path
    if path.suffix == ".parquet":
        path = _alt(path)
        warnings.warn(f"pyarrow chưa cài -> ghi {path.name} (csv.gz). `pip install pyarrow` để có parquet.")
    df.to_csv(path, index=False)
    return path


def read_table(path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet" and path.exists():
        return pd.read_parquet(path)
    if path.suffix == ".parquet":
        path = _alt(path)
    if not path.exists():
        raise FileNotFoundError(path)
    head = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(path, parse_dates=[c for c in DATE_COLS if c in head])


def table_exists(path) -> bool:
    path = Path(path)
    return path.exists() or _alt(path).exists()

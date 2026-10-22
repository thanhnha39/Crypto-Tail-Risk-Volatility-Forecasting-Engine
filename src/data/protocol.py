"""Shared calendar labels for the data handoff; no model fitting."""
import pandas as pd


SEGMENTS = ("pre_sample", "warmup", "evaluation", "holdout")


def sample_segments(dates, settings):
    dates = pd.DatetimeIndex(pd.to_datetime(dates, utc=True))
    start, warmup_end, evaluation_start, evaluation_end, holdout_start, holdout_end = (
        pd.Timestamp(settings[key], tz="UTC") for key in (
            "research_start", "warmup_end", "evaluation_start", "research_end",
            "holdout_start", "holdout_end"))
    day = pd.Timedelta(days=1)
    if not (start <= warmup_end and warmup_end + day == evaluation_start
            and evaluation_start <= evaluation_end and evaluation_end + day == holdout_start
            and holdout_start <= holdout_end):
        raise ValueError("Study periods must be ordered, contiguous UTC date ranges")
    if dates.isna().any() or (dates > holdout_end).any():
        raise ValueError("Missing date or date beyond the configured holdout end")
    labels = pd.Series("pre_sample", index=dates, dtype="str", name="sample_segment")
    labels.loc[(dates >= start) & (dates <= warmup_end)] = "warmup"
    labels.loc[(dates >= evaluation_start) & (dates <= evaluation_end)] = "evaluation"
    labels.loc[(dates >= holdout_start) & (dates <= holdout_end)] = "holdout"
    return labels.to_numpy()

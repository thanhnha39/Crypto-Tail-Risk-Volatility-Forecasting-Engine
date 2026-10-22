"""Dataset: one symbol and UTC forecast origin; all main features available at origin end."""
HAR_COLS = ["rv_d", "rv_w", "rv_m"]
HAR_LOG_COLS = ["log_rv_d", "log_rv_w", "log_rv_m"]
FEATURE_COLS = HAR_COLS + HAR_LOG_COLS + ["park", "log_park", "ret_d", "log_qv", "log_turn_rel"]
MACRO_COLS = ["log_vix_l1", "log_usd_l1"]

def y_col(h): return f"y_rv_h{h}"
def ylog_col(h): return f"y_logrv_h{h}"
def target_cols(horizons): return [c for h in horizons for c in (y_col(h), ylog_col(h))]

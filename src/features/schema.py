"""Hợp đồng cột của dataset.parquet (1 dòng = 1 asset x 1 ngày UTC, ngày t = ORIGIN dự báo).

Quy ước thời gian: dòng `date = t` chỉ chứa thông tin có sẵn tới hết ngày t (UTC, 23:59:59).
Crypto giao dịch 24/7 nên RV_t hoàn tất đúng cuối ngày t. Biến mục tiêu y_* là tương lai (t+1...).
"""

HAR_COLS = ["rv_d", "rv_w", "rv_m"]
HAR_LOG_COLS = ["log_rv_d", "log_rv_w", "log_rv_m"]

FEATURE_COLS = [
    "rv_d",          # RV_t           ("hôm qua" từ góc nhìn ngày t+1 cần dự báo)
    "rv_w",          # TB RV_{t-4..t}   (5 ngày)
    "rv_m",          # TB RV_{t-21..t}  (22 ngày)
    "log_rv_d", "log_rv_w", "log_rv_m",
    "park",          # Parkinson variance ngày t, (100*ln(H/L))^2 / (4 ln2)
    "log_park",
    "ret_d",         # log return ngày t (%), close-to-close UTC
    "log_qv",        # ln(quote volume ngày t, USDT)
    "log_turn_rel",  # ln(qv_t / TB qv_{t-21..t})  -> turnover tương đối
    "log_vix_l1",    # ln VIX, giá trị của ngày <= t-1 (ffill từ quá khứ)
    "log_usd_l1",    # ln chỉ số USD (broad), như trên
]

META_COLS = ["asset", "date", "close", "n_ret", "regime"]


def y_col(h: int) -> str:
    return f"y_rv_h{h}"        # TB RV_{t+1..t+h}  (h=1: RV_{t+1})


def ylog_col(h: int) -> str:
    return f"y_logrv_h{h}"     # ln của biến trên (dùng cho ML)


def target_cols(horizons):
    return [c for h in horizons for c in (y_col(h), ylog_col(h))]

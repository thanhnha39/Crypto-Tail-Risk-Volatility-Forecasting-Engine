# Phiếu review chống leakage (người review KHÔNG phải tác giả của feature)

Người review: ____________   Ngày: ________   Commit: ________

**Bước 0 – Chạy:** `python run_tests.py` (hoặc `pytest tests/`) -> 12/12 PASS. [ ]

**Bước 1 – Đọc code** (`src/features/intraday.py`, `build_features.py`, `regimes.py`):
- [ ] Mọi `rolling(...)` là trailing (không `center=True`), mọi `shift` trong feature là số dương.
- [ ] Không có `bfill`, `interpolate`, `fillna(method="bfill")`, `groupby(...).transform` trên toàn mẫu cho feature.
- [ ] Không có chuẩn hoá/thống kê toàn mẫu (mean/std/quantile) dùng làm feature; regime dùng `expanding` (quantile tới t).
- [ ] VIX/USD: `ffill` rồi `shift(lag)`; không dùng giá trị của ngày t hoặc sau t.
- [ ] Cột `y_*` chỉ xuất hiện ở `targets`, không có trong `FEATURE_COLS` của bất kỳ mô hình nào.
- [ ] Ngày dưới ngưỡng coverage -> NaN (không điền bằng ngày lân cận).

**Bước 2 – Phá hoại thủ công:** trong notebook, thay 5-min bars sau ngày T bằng số ngẫu nhiên, build lại, so `dataset` các ngày ≤ T. [ ] giống hệt

**Bước 3 – Walk-forward:**
- [ ] Train tại origin t chỉ gồm dòng `date <= t - h` (xem `iter_splits`).
- [ ] Không có tuning siêu tham số trên mẫu test (nếu có: tuning chỉ trong train, ghi rõ).
- [ ] `validate_forecasts` không báo `LEAKAGE` cho file của mô hình mới.

**Kết luận:** [ ] Đạt   [ ] Cần sửa: ______________________________________

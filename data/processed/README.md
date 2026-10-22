# Dataset mô hình

Thư mục này chưa có dataset có feature/target. Huân đã nhận tiếp phần chuẩn bị feature của Châu và sẽ thực hiện ở bước sau.

Đầu vào ở `data/interim`. Các bảng QA có nhãn ngày quan sát: `pre_sample` (12/2018), `warmup` (2019–2020), `evaluation` (2021–2025), `holdout` (2026, snapshot đến 17/10/2026). Đọc `config/data.toml` và `docs/GROUP_PROTOCOL.md`.

Khi xây feature/target, giữ lưới ngày UTC và RV NaN ở ngày không đủ điều kiện; feature đến hết ngày t, target ngày t+1. Split dataset mô hình phải theo target_date. `daily_reference_qa` là bảng đối chiếu RV %²/volatility %, chưa có lag, target hay dự báo.

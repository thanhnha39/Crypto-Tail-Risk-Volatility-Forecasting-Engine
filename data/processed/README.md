# Bộ đầu vào Backend 1

`dataset.parquet` là dữ liệu thật BTC/ETH, một dòng mỗi ngày origin UTC, giữ lịch đầy đủ. `dataset_meta.json` ghi feature, target, provenance và hash. `regime_thresholds.json`, `regime_labels.csv` ghi ngưỡng warmup cố định và nhãn tại origin. `forecast_schedule.parquet` là lịch chung cho hai horizon/hai cửa sổ, có cả holdout nhưng không tự đánh giá holdout.

Đọc `docs/TECHNICAL_GUIDE.md`, `docs/forecast_format.md` và `config/data.toml`. Macro bị loại khỏi main; log_turn_rel là proxy relative quote volume, không phải turnover/market cap. Không đưa cột y_* hoặc target_* vào feature. Target 7 ngày là tổng RV, đơn vị %², thiếu bất kỳ ngày nào thì NaN. Chia mẫu theo khoảng target, không theo nhãn origin.

Các file mô phỏng cũ đã chuyển sang outputs/legacy_synthetic. Tạo lại dữ liệu thật: `python -m src.features.build_dataset`.

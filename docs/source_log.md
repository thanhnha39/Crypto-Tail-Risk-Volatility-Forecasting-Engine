# Nhật ký nguồn dữ liệu

Bản máy đọc đầy đủ: source_log.csv (mỗi file/nguồn một dòng). Snapshot 2026-10-18; 277 nguồn/file, 273 Binance ZIP gồm phần chính và đối chiếu bổ sung khớp checksum. Raw archives giữ nguyên, metadata SHA256 và retrieved_at lưu bên cạnh. Raw Parquet là bảng tổng hợp token nguồn, có thể tái tạo từ archive. Độ phủ, row count, timestamp unit và local_path nằm trong CSV; status unavailable nếu tải thất bại.


## Bộ nguồn bổ sung cho sensitivity macro

Manifest riêng: `data/raw/alfred/manifest.json`, gồm URL và SHA256 của 216 CSV snapshot và hai trang danh sách vintage. Bộ này bổ sung 1.790 vintage VIX và 361 vintage USD đến 31/12/2025; không thay 277 nguồn gốc hoặc dataset chính. Bảng dẫn xuất: `data/interim/macro_vintages.parquet`. Quy tắc thời điểm và giới hạn: `docs/macro_sensitivity.md`.

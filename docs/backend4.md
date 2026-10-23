# Backend 4: VaR/ES và kiểm định rủi ro

## Phạm vi hoàn thành

BTCUSDT, ETHUSDT; 9 mô hình đã có từ Backend 1–3: HAR-RV, GARCH,
GJR-GARCH, XGBoost, Elastic Net, naive random walk, historical mean,
combo_econ và combo_core4. Dự báo **1 ngày**, rolling chính, expanding kiểm tra
độ nhạy; VaR/ES ở mức tin cậy 95%/99%. Giai đoạn kiểm định 2021–2025.
Không chạy holdout cuối 2026; không viết chương báo cáo.

## Chạy ngay trên nhánh backend-4

Repo trên nhánh này đã có đầy đủ Data và Backend 1–3. Từ thư mục gốc repo,
dùng Python đã cài `requirements.txt`:

```powershell
python -B -m src.backend4
python -B -m unittest discover -s tests -p "test_backend4*.py"
python -B -X utf8 verify_backend4.py --input-root .
```

Kết quả đã tính sẵn tại `outputs/risk/` và `outputs/figures/risk/`.
Các hướng dẫn dùng bộ submission riêng dưới đây dành cho trường hợp chưa ghép repo.

## Đầu vào và cách chạy

Đây là bộ bàn giao bổ sung vào repo Data–Backend 3, không chứa lại dữ liệu gốc.
Cần `config/data.toml`, `config/backend1.toml`, `data/processed/dataset.parquet`,
`dataset_meta.json`, và 18 file `outputs/forecasts/{coin}_{model}.parquet`.
Dùng môi trường Python của dự án và dependencies trong requirements.txt của repo.

**Chạy bộ bàn giao riêng**, không cần sao chép data:

```powershell
cd "E:\Python\Backend4\Backend4_Submission"
& "E:\Python\Goi_1_Crypto\.venv\Scripts\python.exe" -B -X utf8 .\run_backend4.py --input-root "E:\Python\Goi_1_Crypto_GitHub\Crypto-Tail-Risk-Volatility-Forecasting-Engine"
```

Kiểm tra lại các file kết quả đã sinh (checksum, số dòng, lịch ngày, ES <= VaR,
chung mẫu, FHS không nhìn tương lai và đường vốn chiến lược):

```powershell
python -B -X utf8 .\verify_backend4.py --input-root "DUONG_DAN_REPO_DATA_BACKEND_3"
```

Dùng cùng môi trường Python như lệnh chạy chính. Kết quả lưu vào
`outputs/risk/verification.json`. Script này chỉ xác minh, không refit mô hình.

Đổi input-root thành repo đã có đầy đủ bản main Data–Backend 3 trên máy.
Đầu ra ghi vào chính Backend4_Submission. Để chỉ chạy test, thêm `--test`.
Nếu môi trường thiếu thư viện, cài requirements.txt của repo vào đúng môi trường.

**Tích hợp vào repo**: chép `src/risk/`, `src/backend4.py`, hai file test
`tests/test_backend4*.py`, `docs/backend4.md` vào đúng đường dẫn tương ứng.
Sau đó từ thư mục gốc repo:

```powershell
python -B -m src.backend4
python -B -m unittest discover -s tests -p "test_backend4*.py"
```

## Quy tắc tính và chống leakage

- Return là **100 × log(Pt/Pt−1)**. RV có đơn vị %², sigma có đơn vị %.
- GARCH/GJR dùng Student-t chuẩn hóa phương sai bằng 1: scale t thông thường
  bằng sigma × sqrt((nu−2)/nu), yêu cầu nu > 2.
- Các mô hình khác dùng FHS từ residual ngoài mẫu **của đúng coin, model và window**.
  residual = (return thực tế − mean dự báo) / sigma dự báo.
- Return của ngày d chỉ biết lúc 00:00 UTC ngày d+1. Residual được phép dùng khi
  `observable_at <= forecast_available_at` và target residual nằm trước target hiện tại.
  So sánh datetime UTC đã chuẩn hóa nanosecond, không trộn số microsecond/nanosecond.
- Pool FHS mở rộng từ các dự báo OOS, tối thiểu **20 residual quá khứ**, giữ nguyên
  ngưỡng đã có trong bản nộp; không chọn lại ngưỡng dựa trên kết quả kiểm định.
  Vì vậy các ngày đầu chưa có VaR FHS. 99% với pool ngắn có thể chỉ có một điểm
  trong đuôi; xem `n_fhs_tail` trước khi diễn giải ES.
- Dataset và từng forecast được kiểm tra schema, thời điểm train/refit, lịch ngày,
  danh tính coin/model và checksum dataset/protocol. Không refit mô hình ở Backend 4.
- Residual được dựng lại từ forecast đã xác minh và return đích; không phụ thuộc
  file residual xuất cũ có thể khác phiên bản.

## Hợp đồng đầu ra

`outputs/risk/{coin}_{model}.parquet`: không trộn với outputs/forecasts.
Đây là quy ước đường dẫn của PCCV Backend 4; các file risk không phải RV forecast.

| Nhóm | Cột |
|---|---|
| PCCV bắt buộc | date, coin, model, alpha, return, var, es, breach |
| Phân biệt bài toán | window, horizon_days, method, confidence |
| Tình trạng | status, score_valid, common_sample |
| Nguồn forecast | origin_date, forecast_available_at, sigma_pct, variance_pct2, mean_forecast_pct, nu |
| Truy vết FHS | n_fhs_residuals, n_fhs_tail, last_residual_observable_at, last_residual_target_date |
| Phiên bản | dataset_sha256, protocol_sha256, các hash chọn mô hình nếu có ở nguồn |

`alpha=.05/.01` là xác suất đuôi trái, tương ứng confidence=.95/.99.
VaR/ES là return đuôi trái, thường âm; **không ép âm** nếu phân phối có mean rất cao.
ES <= VaR. `breach=1` khi return < VaR; bằng ngưỡng không tính vi phạm.
Ngày thiếu forecast/lịch sử giữ nguyên dòng, VaR/ES/breach để thiếu, không gán 0.

## Bảng và hình RQ4

- `backtest.csv`: **bảng chính, cùng mẫu ngày hợp lệ của cả 9 mô hình**, riêng
  từng coin/window/alpha. Kupiec, Christoffersen, quantile loss, thống kê ES mô tả.
- `backtest_available_sample.csv`: độ phủ thực tế riêng mô hình; không dùng để
  xếp hạng trực tiếp giữa mô hình khác mẫu.
- `coverage.csv`: số ngày lịch, số ngày dùng được, số ngày chung, lý do chưa có dự báo.
- `crisis_breaches.csv`: cùng mẫu và mẫu riêng, các cửa sổ tháng 5/2021,
  Luna 7–13/5/2022, FTX 6–14/11/2022. COVID 12–16/3/2020 được ghi rõ
  `outside_evaluation`, không tạo kết quả giả cho giai đoạn chưa dự báo.
- `outputs/figures/risk/*_var_breaches.png`: rolling, hai panel 95%/99%, return,
  VaR, ES và các điểm vi phạm.
- `simulation_checks.csv`: sáu kiểm tra xác suất đuôi biết trước, seed=4104.
- `run_manifest.json`: checksum đầu vào/đầu ra, phạm vi, phương pháp và hạn chế.

Christoffersen chỉ đếm chuyển trạng thái giữa **hai ngày lịch liền nhau**.
Không nối ngày trước/sau khoảng thiếu. `n_adjacent_pairs`, `n_gaps`, `cc_status`
cho biết độ phủ; mẫu không đủ biến thiên trả p-value thiếu, không coi là đạt.
P-value trên mẫu có khoảng thiếu chỉ là chẩn đoán tiệm cận, phụ thuộc cơ chế thiếu.
Kupiec/Christoffersen kiểm tra VaR, **không thay thế kiểm định hiệu chuẩn ES**.
Không tuyên bố mô hình đạt chỉ vì p-value > .05; phải xem số breach và cỡ mẫu.

## RQ5 tùy chọn đã triển khai

`volatility_targeting.csv` và `strategy_paths/{coin}_{model}_{window}.parquet`.
Dùng sigma forecast gốc, không suy ngược sigma từ VaR Student-t/FHS.
Forecast cho target ngày t được dùng ngay cho return ngày t, không thêm một lag.

Tham số minh họa cố định: mục tiêu 15%/năm, 365 ngày/năm (crypto), tối đa 100%
vốn, phí một chiều 5 bps, lãi tiền mặt 0. Không chọn tham số trên evaluation.
Return log chuyển thành simple return bằng expm1; tài sản tích lũy bằng nhân
wealth. Phí tính trên turnover so với tỷ trọng đã trôi theo giá, kể cả lệnh mua
ban đầu. Buy-and-hold cũng chịu phí mua ban đầu, cả hai giữ vị thế đến cuối mẫu.
Drawdown bao gồm vốn ban đầu bằng 1.

Nếu thiếu sigma: giữ nguyên lượng coin đang nắm, không giao dịch hoặc nhìn tương lai.
Nếu thiếu return thực tế: dừng thay vì bỏ ngày hoặc bịa P&L=0.
Đây là mô phỏng giao dịch tại mốc đóng/mở ngày với phí cố định; chưa mô hình hóa
slippage, độ trễ khớp lệnh hay lãi tiền mặt. Không phải khuyến nghị đầu tư.

## Các sửa đổi so với bản ban đầu

Đã sửa lỗi FHS lấy residual tương lai do trộn đơn vị timestamp; giữ ngày chưa đủ
lịch sử có trạng thái; kiểm định theo lịch ngày; thêm so sánh cùng mẫu và độ phủ;
truy vết checksum; sửa alignment, sigma, phí, compounding và drawdown RQ5.
Kết quả cũ không được dùng lại. Test hồi quy thay đổi dữ liệu tương lai để đảm
bảo VaR/ES trước đó không đổi, kể cả dữ liệu timestamp microsecond.

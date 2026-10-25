# Hướng dẫn kỹ thuật Data và Backend 1 đến 4

Tài liệu này dành cho người chạy code hoặc nối dashboard. Người viết luận bắt
đầu tại [Bàn giao viết luận](BAN_GIAO_VIET_LUAN.md). Quy tắc nghiên cứu có thẩm
quyền nằm ở [GROUP_PROTOCOL.md](GROUP_PROTOCOL.md) và `config/data.toml`.

## 1 Mở repo và chạy kiểm tra

Python 3.12, terminal tại thư mục gốc repo:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B run_tests.py
.\.venv\Scripts\python.exe -B -X utf8 verify_backend4.py --input-root .
```

Kết quả dự báo đã commit sẵn. Đọc bảng không cần tải lại dữ liệu hoặc fit mô hình.
Các lệnh dưới đây phục vụ tái lập; chỉ chạy bước cần cập nhật:

| Bước | Lệnh từ gốc repo | Tác dụng |
|---|---|---|
| Data | `python -m src.data.run` | Tải/đọc cache, làm sạch, QA và báo cáo dữ liệu |
| QA offline | `python -m src.data.refresh` | Kiểm tra dữ liệu đã có, cập nhật bảng QA |
| Backend 1 | `python -m src.backend1` | Dataset, target/regime, baseline và đánh giá |
| Backend 2 | `python -m src.backend2` | HAR/GARCH/GJR, tổ hợp ba mô hình, diagnostics |
| Backend 3 | `python -m src.backend3` | Elastic Net/XGBoost, ablation, SHAP, tổ hợp bốn |
| Macro riêng | `python -m src.models.macro_sensitivity --analyze-only` | Tổng hợp sensitivity đã chạy, không tải/fit lại |
| Backend 4 | `python -m src.backend4` | VaR/ES, kiểm định, hình và chiến lược RQ5 |
| Bàn giao luận | `python -m src.reporting.build_handoff` | Cập nhật file bàn giao từ kết quả đã có |

Tạo lại thống kê từ forecast có sẵn: `src.evaluation.aggregate`,
`src.models.diagnostics`, `src.models.ml_analysis`, `src.evaluation.robustness`.
Không dùng lệnh fit để chỉ lấy lại bảng đã có.

## 2 Nguồn dữ liệu và phạm vi

Binance spot BTCUSDT/ETHUSDT, nến 5 phút UTC. Raw ZIP chứa CSV gốc; checksum và
metadata đi kèm. Pipeline đọc ZIP, tổng hợp raw Parquet và xuất nến sạch trong
`data/interim/`. Modeling đọc `data/processed/dataset.parquet` hoặc forecast,
không yêu cầu thành viên tự giải nén ZIP bằng tay.

Snapshot kết thúc 17/10/2026 23:55 UTC, không tự cập nhật theo ngày mở repo.
Tháng 12/2018 làm đệm; warmup 2019–2020; evaluation 2021–2025; holdout 2026 dành
cho lượt đánh giá cuối. Quy trình và kết quả holdout hiện tại nằm trong
[HOLDOUT_PROTOCOL.md](HOLDOUT_PROTOCOL.md) và [HOLDOUT_RESULTS.md](HOLDOUT_RESULTS.md).
QA nguồn không đồng nghĩa đã chấm mô hình. Xem [data_quality_report.md](data_quality_report.md),
[data_dictionary.md](data_dictionary.md), [source_log.md](source_log.md) và
[source_log.csv](source_log.csv).

## 3 Feature target và thời điểm

| Biến | Định nghĩa và đơn vị |
|---|---|
| Return 5 phút | `100*ln(close_j/close_(j-1))`, % |
| RV ngày | Tổng bình phương 288 return liên tiếp, %² |
| `rv_d`, `rv_w`, `rv_m` | RV ngày t, trung bình trailing 5/22 ngày lịch |
| `park` | `(100*ln(high/low))²/(4*ln(2))`, chỉ ngày đủ nến |
| `ret_d` | Return log close-to-close của ngày t, % |
| `log_qv` | Log quote volume |
| `log_turn_rel` | Log quote volume/chỉ số trung bình trailing 22 ngày; proxy khối lượng, không phải turnover theo market cap |
| Target h1 | RV(t+1), %² |
| Target h7 | Tổng RV(t+1)…RV(t+7), %²; thiếu một ngày thì target thiếu |
| Volatility | Căn RV/phương sai dự báo, %; không đổi target sang volatility |

Ngày t đủ RV phải có 288 nến và 288 return đúng khoảng 5 phút; return đầu ngày
cần close của ngày trước. Không lấp RV, không nén ngày thiếu, không winsorize.
Các trung bình trailing yêu cầu đủ ngày, nên một ngày thiếu có thể khiến nhiều
ngày feature phía sau thiếu. Return close-to-close vẫn có thể biết khi RV thiếu.

`origin_date=t` ghi ngày thông tin. Forecast cho t+1 có sẵn tại 00:00 UTC ngày
t+1. Target h7 chia giai đoạn theo toàn bộ khoảng, không dùng target băng qua
warmup/evaluation/holdout để chấm riêng từng phần.

## 4 Cửa sổ lịch refit và regime

Rolling 730 ngày lịch, từ refit_origin−729 đến refit_origin. Expanding bắt đầu
01/01/2019. Chọn khoảng lịch trước rồi mới lọc dòng thiếu, không kéo lùi để bù
đủ 730 quan sát. Tối thiểu 365 dòng hợp lệ cho walk-forward.

Refit neo 31/12/2020, cách 5 ngày lịch; vẫn dự báo hằng ngày. Tham số/scaler giữ
nguyên giữa refit, feature và conditional state cập nhật đến origin hiện tại.
Supervised chỉ nhận nhãn đúng horizon đã hoàn tất; GARCH nhận quan sát return.

Regime dùng thông tin tại origin. Crisis khi RV trung bình 22 ngày lớn hơn
phân vị 90% hiệu chuẩn riêng coin trên warmup rồi cố định. Nếu không crisis,
bear khi log return 90 ngày ≤−10%, bull khi ≥10%, còn lại normal. Thiếu lịch sử
gắn unclassified. Thứ tự crisis > bear > bull > normal. Ngưỡng lưu trong
`data/processed/regime_thresholds.json`.

## 5 Mô hình kinh tế lượng và baseline

- `naive_rw`: dự báo `h*RV_t`; `hist_mean`: trung bình target trong train.
- `har_rv`: OLS có intercept, RV ngày, trung bình 5 và 22 ngày. Fit trực tiếp
  riêng target h1 và tổng RV h7, floor phương sai 1e-10 cố định.
- `garch`: GARCH(1,1), constant mean, innovation Student-t chuẩn hóa variance=1.
- `gjr_garch`: thêm bất đối xứng GJR với một bậc. Return đã là %, `rescale=False`.
- GARCH h7 cộng đường 7 conditional variance theo đệ quy, không nhân variance
  ngày đầu với 7. HAR h7 là direct forecast, không lặp HAR một ngày bảy lần.
- Tại refit, lọc trạng thái bằng residual/backcast từ tham số cuối cùng, đối
  chiếu public forecast của `arch`. Giữa refit chỉ cập nhật bằng return đã biết.
- Fit lỗi/hết hội tụ ghi status và NaN, không âm thầm thay bằng naive/fit cũ.
  Một lần retry optimizer dùng khởi tạo từ train theo cấu hình backend2.
- `combo_econ`: trung bình đều variance HAR/GARCH/GJR. `combo_core4`: thêm
  XGBoost. Phải đủ thành phần hợp lệ; không đổi trọng số theo ngày thiếu.

`outputs/diagnostics/` lưu tham số, robust SE, hội tụ, persistence, ν, residual
tests và đối chiếu thư viện. Persistence gần 1 và ν≤4 được giữ, gắn cờ; không
suy ra finite unconditional variance/moment bậc bốn trong trường hợp không đáp
ứng điều kiện. P-value residual là xấp xỉ khi tham số ước lượng và đuôi dày.
KS statistic là mô tả, không dùng p-value chuẩn của phân phối biết tham số.

## 6 Machine learning tuning và SHAP

Core predictors: `log_rv_d`, `log_rv_w`, `log_rv_m`, `log_park`, `ret_d`.
Bản chính thêm `log_qv`, `log_turn_rel`; macro không nằm trong bản chính.

Elastic Net và XGBoost dự báo log RV. Chuyển về variance bằng smearing factor
`mean(exp(log(y_train)-fitted_log_train))`, chỉ tính trong train. Đây là hiệu
chỉnh theo residual train, không đảm bảo hoàn toàn không chệch dưới mọi dạng
heteroskedasticity. Scaler Elastic Net chỉ fit train hiện tại.

Train tuning có target kết thúc đến 30/06/2020; validation trong 01/07–31/12/2020.
Dòng hợp lệ thực tế: h1 có 347 train/132 validation; h7 có 305/126, mỗi coin.
Tuning là một fixed split, không phải mô phỏng lịch refit evaluation. Chọn một
lần theo QLIKE, khóa trong `outputs/model_selection/backend3_locked.json`.
Không dùng evaluation/holdout chọn lại depth, alpha, số cây hoặc smearing.

Ablation volume giữ cùng tham số, cùng dòng train và mẫu test cặp; bản core bỏ
giá trị hai biến volume khỏi predictors. `QLIKE_full_minus_core<0` là bản thêm
volume có loss thấp hơn. Chỉ kết luận ý nghĩa thống kê khi xét DM và điều kiện mẫu.

XGBoost dùng exact TreeSHAP native (`pred_contribs=True`, `approx_contribs=False`)
tại từng origin với estimator đang dùng. Tổng contribution/base khớp raw log
prediction. SHAP giải thích raw log RV, không phải %² hay tác động nhân quả.
Màu percentile trong hình là hậu xử lý mô tả. GRU tùy chọn chưa triển khai.

## 7 Đánh giá và sensitivity

QLIKE chuẩn hóa = y/f−ln(y/f)−1; RMSE/MAE trên variance %². Điểm càng thấp càng tốt.
`model_comparison.csv` là giao ngày hợp lệ của tất cả 9 model theo coin/horizon/window.
Đọc kèm `forecast_coverage.csv`; điểm trên mẫu riêng không dùng để xếp hạng công bằng.

DM-HLN dùng d=loss(model)−loss(HAR), Bartlett HAC theo ngày lịch đến lag h−1,
hiệu chỉnh HLN và p-value Student-t(n−1). DM âm là loss thấp hơn, không tự có
nghĩa thống kê. Mẫu dưới 30 hoặc phương sai sai khác bằng 0 có status riêng.
Dependence dài hơn do refit/regime, nhiều phép so sánh và mẫu crisis nhỏ là hạn chế.

`robustness.csv` so rolling/expanding của cùng model/horizon trên cùng mẫu. H1
và h7 là target khác nhau; không lấy loss h7 trừ loss h1 để kết luận cải thiện.

Sensitivity VIX/USD dùng snapshot ALFRED có vintage và quy tắc availability
bảo thủ, cùng train/test và tham số khóa; xem [macro_sensitivity.md](macro_sensitivity.md).
Không dùng FRED calendar mô tả cũ hay shift một hàng để thay vintage verification.

## 8 VaR ES và thời điểm residual

Risk h1, confidence 95%/99% tương ứng alpha=.05/.01. Return/VaR/ES là % log return,
thường âm; không ép âm trong mọi phân phối. Breach khi return < VaR. ES ≤ VaR.

GARCH/GJR dùng standardized Student-t: scale t thông thường bằng
sigma*sqrt((ν−2)/ν), ν>2. Không dùng sigma trực tiếp làm scale t chưa chuẩn hóa.
Tổng return h7 không có Student-t chính xác theo lập luận này; Backend 4 hiện
chỉ chấm risk h1 theo phạm vi chính, không gắn nhãn risk h7 giả.

Các model khác dùng FHS từ own-model OOS residual `(return−mean_forecast)/sigma`.
Pool tách coin/model/window, mở rộng theo thời gian, tối thiểu 20 residual theo
thiết kế đã có. Return ngày d chỉ biết tại 00:00 UTC d+1. Chỉ dùng residual có
`observable_at <= forecast_available_at` và target trước target đang dự báo.
Timestamp được chuẩn hóa UTC/ns, không trộn số microsecond với nanosecond.
Pool ít quan sát làm 1% tail rất thưa; xem n_fhs_tail trước khi diễn giải ES.

Backend 4 xác minh dataset/protocol và forecast nguồn, dựng lại residual từ
forecast đã xác minh và return chuẩn. Giữ nguyên mọi ngày lịch, ghi status khi
không có forecast hoặc chưa đủ pool. Không gán breach=0 cho ngày chưa chấm được.

## 9 Đọc risk outputs và nối dashboard

Đường dẫn thực dùng theo PCCV Backend 4:
`outputs/risk/{coin}_{model}.parquet`, không đặt risk vào thư mục RV forecast.
Schema đầy đủ tại [forecast_format.md](forecast_format.md).

| File | Cách dùng |
|---|---|
| `outputs/risk/backtest.csv` | Bảng chính trên cùng mẫu 9 model |
| `backtest_available_sample.csv` | Mẫu riêng từng model, không phải bảng xếp hạng cùng mẫu |
| `coverage.csv` | Số ngày lịch/dự báo hợp lệ/ngày chung và lý do thiếu |
| `crisis_breaches.csv` | Hai loại mẫu, May 2021, Luna, FTX; COVID 2020 outside_evaluation |
| `simulation_checks.csv` | Sáu mô phỏng tỷ lệ đuôi biết trước |
| `run_manifest.json` | Hash input/source/output, phạm vi và giới hạn |
| `verification.json`, `test_results.json` | Kết quả đối chiếu và test Backend 4 |
| `outputs/figures/risk/` | 18 hình, mỗi hình gồm cả 95% và 99% |

Dashboard chọn coin/model/window/alpha/date; hiển thị prediction khi status=ok.
Thống kê breach dùng score_valid, so model dùng common_sample. Mỗi ngày có hai
alpha và hai window; không đếm bốn dòng là bốn ngày quan sát độc lập.

Christoffersen chỉ đếm cặp ngày lịch liền nhau; không nối qua khoảng thiếu.
Mẫu chính risk có 6 khoảng ngắt, nên p-value ghi asymptotic_gapped_sample. Mẫu
thiếu biến thiên chuyển trạng thái trả p-value thiếu. Kupiec/Christoffersen là
VaR coverage tests, không chứng minh ES đã qua một kiểm định hiệu chuẩn riêng.

## 10 Chiến lược RQ5

Mục tiêu minh họa 15%/năm, 365 ngày/năm, max weight=1, phí một chiều 5 bps,
lãi tiền mặt 0. Dùng sigma forecast gốc cho đúng target ngày t, không suy sigma
từ VaR hoặc thêm một lag. Log return chuyển thành simple return bằng expm1,
wealth ghép lãi bằng nhân. Phí tính trên traded value so với tỷ trọng đã trôi
theo giá, gồm lệnh mua đầu tiên cho cả chiến lược và buy-and-hold. Max drawdown
tính từ vốn ban đầu 1. Cuối mẫu định giá vị thế đang nắm, không ép thanh lý.

Thiếu sigma giữ nguyên số lượng coin, không giao dịch; thiếu actual return thì
dừng thay vì bỏ ngày hoặc điền P&L=0. Mọi model dùng cùng lịch 1.826 ngày,
nhưng khả năng có forecast và mức tiếp xúc rủi ro khác nhau. Đây là mô phỏng
chưa có slippage/độ trễ khớp lệnh; không gán causal economic value chỉ từ bảng.
Daily paths ở `outputs/risk/strategy_paths/`, summary ở `volatility_targeting.csv`.

## 11 Kiểm tra và lượt holdout cuối

`python run_tests.py` chạy toàn bộ test công thức, data quality, leakage, models
và risk. `verify_backend4.py --input-root .` đối chiếu hash, lịch, cùng mẫu,
ES/VaR, thay đổi residual tương lai và wealth path. Test fixture mô phỏng dùng
để kiểm tra code; số liệu nghiên cứu lấy từ snapshot thật.

Không coi unit test đạt là mọi model vượt benchmark hay coverage được chấp nhận.
Các trạng thái kiểm tra độc lập trước đây không phải chữ ký của thành viên.
Lượt final holdout 2026 dùng thiết kế đã khóa tại `outputs/holdout_plan.json`.
Trạng thái từng bước ở `outputs/final_holdout_pipeline.json`; kết quả và giới hạn
ở [HOLDOUT_RESULTS.md](HOLDOUT_RESULTS.md). Phạm vi là 01/01–17/10/2026.
Luồng chạy thống nhất: `python -m src.final_holdout --prepare`, rồi `--run`;
không chạy lại khi đã có trạng thái completed. Không xóa lock để thử nhiều lần.
Orchestrator chỉ gọi aggregate sau khi toàn bộ model đã có forecast, tránh
trùng khóa khi gọi tuần tự entry point Backend 2 và 3 cũ.
Backend 4 mặc định giữ evaluation 2021–2025; cờ `--final-holdout` dùng thư mục
`outputs/risk_holdout`, kế thừa residual ngoài mẫu riêng model/window trước 2026
và chỉ thêm residual đã quan sát. Xem quy trình khóa và kiểm tra ở tài liệu holdout.

Code risk evaluation lịch sử đã thay phiên bản sau khi bổ sung holdout. Đối chiếu
hash code đã tạo ra kết quả cũ bằng `verify_backend4.py --input-root .
--historical-source-ref e226478 --output-report outputs/holdout_evaluation_compatibility.json`.
Không cập nhật ngược hash manifest cũ thành hash code mới.

QA holdout giữ giới hạn đã biết: ngày 22/02/2026 còn chênh giữa Binance và
CoinGecko chưa rõ nguyên nhân, dù nến Binance 5m khớp dữ liệu 1d cùng sàn.
Giữ nguồn Binance theo protocol; không sửa giá hoặc tune theo chênh lệch này.
Đọc `data_quality_report.md` và phần dữ liệu của bản bàn giao 24/10 khi viết luận.

Đã có hiệu chỉnh riêng sau lượt chấm cho tiêu đề hình bị ghi cố định 2021–2025.
`outputs/holdout_plan_original.json` giữ nguyên plan trước lượt chấm;
`outputs/holdout_plan.json` ghi bổ sung đúng thay đổi trình bày này. Code gốc
ở `outputs/holdout_source_original/aggregate.py`; manifest hiệu chỉnh xác nhận
không fit/tune lại và mọi file số liệu giữ nguyên. `correct_holdout_titles.py`
là công cụ sửa một lần, từ chối ghi đè biên bản đã có. Kiểm tra lại các đầu ra
hiện hành bằng `python -m src.evaluation.verify_holdout`.

## 12 Nguồn phương pháp và code

Implementation cần đọc: `src/features/`, `src/evaluation/`, `src/models/`,
`src/risk/`; các kết quả đã khóa cần giữ nguyên provenance.
Nguồn dữ liệu và availability macro có tại source_log và macro_sensitivity.

- [arch forecasting](https://arch.readthedocs.io/en/latest/univariate/forecasting.html)
- [arch standardized Student-t](https://arch.readthedocs.io/en/latest/univariate/generated/arch.univariate.StudentsT.html)
- [Elastic Net](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html)
- [XGBoost prediction](https://xgboost.readthedocs.io/en/stable/prediction.html)
- [HLN DOI](https://doi.org/10.1016/S0169-2070(96)00719-4)

Tài liệu kỹ thuật này thay các ghi chú Backend 1–4 và checklist review cũ;
các phiên bản trước vẫn tra được trong lịch sử Git.

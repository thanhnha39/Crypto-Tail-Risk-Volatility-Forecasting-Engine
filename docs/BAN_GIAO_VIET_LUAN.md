# Bàn giao số liệu và kết quả để viết luận Crypto Tail Risk

Tài liệu này giúp nhóm viết các phần dữ liệu, phương pháp, kết quả và thảo luận
từ bộ **Data và Backend 1–4 đã tích hợp trên main**. Mỗi bảng có đường dẫn nguồn
và bộ lọc để đối chiếu. Đây là tài liệu bàn giao kết quả, không thay toàn bộ
chương luận hoặc tổng quan tài liệu.

**Phạm vi số liệu:** snapshot Binance kết thúc 17/10/2026; kết quả mô hình và
rủi ro chỉ đánh giá 2021–2025. Ngày lập bàn giao 24/10/2026 không phải ngày cuối
dữ liệu. Holdout 2026 chưa được chấm mô hình; một phần đã được kiểm tra QA và
trước đây đã có thống kê mô tả, nên không viết rằng dữ liệu này chưa từng được xem.

**Đọc theo thứ tự:** mục 1 để nắm kết luận, mục 2 để chia phần viết, mục 3–12
để lấy số liệu, mục 13–15 để lấy hình và kiểm tra cách diễn giải.

## 1 Kết quả chính cần nắm

- **BTCUSDT:** Elastic Net có QLIKE 0.3541 so với HAR-RV 0.3785, thấp hơn 6.45%. DM-HLN p=0.3211: chưa đủ bằng chứng vượt HAR ở mức 5% trong bài toán h1/rolling.

- **ETHUSDT:** Elastic Net có QLIKE 0.3019 so với HAR-RV 0.3424, thấp hơn 11.83%. DM-HLN p=0.1412: chưa đủ bằng chứng vượt HAR ở mức 5% trong bài toán h1/rolling.

- **RQ2:** thêm volume làm QLIKE h1 giảm ở cả hai ML/hai coin nhưng DM đều p>0.05.
  Macro có bằng chứng danh nghĩa ở Elastic Net/ETH với VIX hoặc VIX+USD; không
  suy rộng sang mọi coin/model, không coi là quan hệ nhân quả.
- **RQ3:** kết quả thay đổi theo regime. Elastic Net có QLIKE crisis thấp hơn
  HAR trong bảng h1/rolling, còn XGBoost cao hơn HAR ở crisis của cả hai coin.
  Cần xem số ngày và kiểm định trong từng nhóm.
- **RQ4:** bốn mô hình chính có p-value Kupiec/Christoffersen >0.05 trên mẫu
  chung rolling ở cả 95%/99%. Đây là chưa bác bỏ giả thuyết coverage theo
  kiểm định, không phải chứng minh mô hình đúng hay ES đã được kiểm định hiệu chuẩn.
- **RQ5:** volatility targeting giảm drawdown mạnh trong mô phỏng nhưng CAGR
  thấp hơn buy-and-hold; Sharpe không tăng đồng đều. Không kết luận luôn sinh lời cao hơn.

Các kết luận trên chỉ dùng thiết kế đã khóa. Không chọn lại mô hình, tham số
hay ngưỡng sau khi đọc các bảng để làm đẹp kết quả kiểm định.

## 2 Ai viết phần nào thì đọc file nào

| Phần trong luận | Nội dung cần lấy | Nguồn chính |
|---|---|---|
| Dữ liệu và thống kê mô tả | Nguồn, giai đoạn, số nến, dữ liệu thiếu, đơn vị, đặc tính đuôi | Mục 3–4; data_quality_report và source_log |
| Phương pháp | Feature/target, rolling 730, refit 5, tuning warmup, model, DM, VaR/ES | Mục 5; GROUP_PROTOCOL; TECHNICAL_GUIDE; forecast_format |
| Kết quả dự báo biến động | QLIKE/RMSE/MAE, DM với HAR, SHAP, regime | Mục 6–8; outputs/tables |
| Kết quả quản trị rủi ro | VaR/ES, breach, Kupiec/Christoffersen, stress, chiến lược | Mục 10–12; outputs/risk |
| Robustness và thảo luận | Expanding, h7, thêm/bỏ volume và macro, giới hạn | Mục 9 và 14 |
| Hình và phụ lục | Hình được tính từ dữ liệu thật, bảng tham số khóa, code/provenance | Mục 13 và 15 |

Nếu nhóm dùng chương 3–7 theo PCCV, có thể đặt dữ liệu ở chương 3, phương pháp
ở chương 4, dự báo ở chương 5, rủi ro ở chương 6 và robustness/thảo luận ở
chương 7. Thống nhất đánh số theo đề cương nhóm trước khi chép bảng/hình.

## 3 Dữ liệu và số quan sát

| Coin | Nến 5 phút sạch | Ngày lịch | Ngày đủ RV | Ngày thiếu nến | Nến thiếu | Nến volume 0 | Abs return 5m >10% |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 828050 | 2878 | 2856 | 21 | 814 | 56 | 4 |
| ETHUSDT | 828050 | 2878 | 2856 | 21 | 814 | 56 | 6 |

Nguồn: [outputs/tables/data_quality_summary.json](../outputs/tables/data_quality_summary.json). Bộ lọc: `symbols; toàn snapshot 2018-12-01 đến 2026-10-17`.

Tổng hai coin là **1.656.100 nến**, tính cả tháng 12/2018 làm đệm. Riêng từ
01/01/2019 có **819.122 nến/coin**, tổng **1.638.244**. Đây là số hàng 5 phút,
không phải số quan sát dùng trực tiếp cho mô hình daily. Dataset daily có
**5.756 hàng coin-ngày = 2 × 2.878**, gồm cả đệm và holdout.

Binance spot có 288 nến/ngày khi đầy đủ. ZIP là bản phân phối nén của CSV;
pipeline đọc thành raw Parquet, nến sạch và dataset, nên các backend không
đọc ZIP bằng tay. Raw Parquet giữ token nguồn; nến sạch có timestamp UTC và số.

| Coin | Giai đoạn | Ngày lịch | Ngày đủ RV | Nến thiếu |
|---|---|---|---|---|
| BTCUSDT | evaluation | 1826 | 1819 | 213 |
| BTCUSDT | holdout | 290 | 290 | 0 |
| BTCUSDT | pre_sample | 31 | 30 | 0 |
| BTCUSDT | warmup | 731 | 717 | 601 |
| ETHUSDT | evaluation | 1826 | 1819 | 213 |
| ETHUSDT | holdout | 290 | 290 | 0 |
| ETHUSDT | pre_sample | 31 | 30 | 0 |
| ETHUSDT | warmup | 731 | 717 | 601 |

Nguồn: [outputs/tables/sample_period_summary.csv](../outputs/tables/sample_period_summary.csv). Bộ lọc: `từng coin và sample_segment`.

### Cách xử lý thiếu và đối chiếu nguồn

- Giữ đầy đủ lịch ngày. RV chỉ tính khi đủ 288 nến và 288 return liên tiếp,
  bao gồm close 23:55 của ngày trước cho return 00:00. Không nội suy/điền 0 RV,
  không dùng return qua khoảng 10/15 phút làm return 5 phút.
- Một ngày thiếu làm các feature trailing 5/22 ngày phía sau thiếu. Vì vậy
  số ngày model dự báo nhỏ hơn số ngày có giá close hoặc số ngày có RV.
- Giữ nến volume=0 và return lớn với cờ QA. Cả 10 nến có |return 5m|>10%
  đã khớp OHLC tổng hợp từ 5 nến 1 phút cùng sàn. Không winsorize.
- Có 222 archive dữ liệu chính, 51 archive đối chiếu và 4 nguồn FRED/CoinGecko,
  tổng 277 nguồn/file trong nhật ký ban đầu; ALFRED sensitivity có manifest riêng.
- Ngày 21/12/2020 monthly và daily Binance khác OHLC ở một số timestamp,
  daily thiếu hơn monthly 4 timestamp/coin. Giữ monthly; ngày này không đủ RV.
- CoinGecko chỉ đối chiếu 365 ngày, không xác minh độc lập toàn lịch sử. Ngày
  22/02/2026 chênh giữa nguồn còn chưa rõ nguyên nhân, dù Binance 5m khớp 1d.
  Không sửa giá gốc cho khớp CoinGecko và không dùng vấn đề holdout này để tune.

Chi tiết: [data_quality_report.md](data_quality_report.md),
[source_log.csv](source_log.csv), [source_log.md](source_log.md),
[source_audit_summary.json](../outputs/tables/source_audit_summary.json).

## 4 Thống kê mô tả dùng trong luận

| Coin | Giai đoạn | Biến | N | Mean | Std | Min | Max | Excess kurtosis |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | warmup | Return ngày (%) | 731 | 0.2812 | 3.9159 | -50.2607 | 15.8684 | 39.30 |
| BTCUSDT | warmup | RV ngày (%²) | 717 | 14.9081 | 48.7991 | 0.6135 | 1105.5610 | 362.19 |
| BTCUSDT | warmup | Căn RV (%) | 717 | 3.1320 | 2.2597 | 0.7832 | 33.2500 | 52.91 |
| BTCUSDT | evaluation | Return ngày (%) | 1826 | 0.0607 | 3.0644 | -16.6998 | 17.8449 | 3.79 |
| BTCUSDT | evaluation | RV ngày (%²) | 1819 | 11.2749 | 24.1711 | 0.0829 | 704.3926 | 388.79 |
| BTCUSDT | evaluation | Căn RV (%) | 1819 | 2.8385 | 1.7944 | 0.2880 | 26.5404 | 23.76 |
| ETHUSDT | warmup | Return ngày (%) | 731 | 0.2357 | 4.9225 | -59.0534 | 21.7824 | 30.07 |
| ETHUSDT | warmup | RV ngày (%²) | 717 | 21.6287 | 52.5163 | 1.3890 | 1169.0332 | 329.63 |
| ETHUSDT | warmup | Căn RV (%) | 717 | 3.9968 | 2.3795 | 1.1786 | 34.1911 | 42.54 |
| ETHUSDT | evaluation | Return ngày (%) | 1826 | 0.0764 | 4.1408 | -32.4861 | 23.3750 | 5.44 |
| ETHUSDT | evaluation | RV ngày (%²) | 1819 | 18.8187 | 48.4739 | 0.1308 | 1639.6948 | 696.81 |
| ETHUSDT | evaluation | Căn RV (%) | 1819 | 3.6652 | 2.3213 | 0.3617 | 40.4931 | 42.44 |

Nguồn: [outputs/tables/descriptive_statistics.csv](../outputs/tables/descriptive_statistics.csv). Bộ lọc: `sample_segment=warmup/evaluation; return_daily_pct_qa, rv_reference_pct2, volatility_reference_pct`.

Return close-to-close có thể tính được khi close cuối ngày vẫn quan sát được,
trong khi RV intraday thiếu. Do đó N return evaluation=1826 nhưng N RV=1819.
Std return ngày không phải trung bình căn RV; mean(sqrt(RV)) không bằng sqrt(mean(RV)).
Đuôi dày ở đây là mô tả phân phối mẫu, không thay cho kiểm định phân phối.
Excess kurtosis lớn và RV lệch phải cho thấy sai số bình phương dễ bị vài ngày
stress chi phối; đọc RMSE cùng QLIKE/MAE, không bỏ các ngày lớn cho điểm tốt hơn.

## 5 Phương pháp thực tế đã triển khai

| Hạng mục | Thiết kế đang dùng |
|---|---|
| Return | 100 × log(Pt/Pt−1), % |
| RV | Tổng bình phương return 5 phút, %²; căn RV báo cáo thêm, đơn vị % |
| Forecast horizon | h1 chính; h7 sensitivity là tổng 7 RV tương lai |
| Cửa sổ | Rolling 730 ngày lịch; expanding bắt đầu 2019 là sensitivity |
| Refit | Cách 5 ngày lịch từ origin 31/12/2020; forecast và cập nhật state hằng ngày |
| Warmup | 2019–2020; tuning train đến 30/06/2020, validation 01/07–31/12/2020 |
| Evaluation | 2021–2025, ngoài mẫu theo thời gian; giữ ngày thiếu trên lịch |
| Holdout | 2026, chưa chấm mô hình; snapshot mới đến 17/10/2026 |
| Mô hình chính | HAR-RV, GARCH-t, GJR-GARCH-t, XGBoost |
| Mô hình bổ sung | Elastic Net, naive RV, historical mean, tổ hợp 3 và tổ hợp 4 |
| ML predictors | log RV d/5d/22d, log Parkinson, ret_d, log quote volume, log relative volume |
| ML target | log RV; chuyển về variance bằng train-only smearing |
| Feature bổ sung | Volume ablation; VIX/USD sensitivity riêng, không trong model chính |
| Risk | h1, VaR/ES 95% và 99%; GARCH/GJR Student-t, các model khác FHS |

HAR dùng OLS trên mức RV. GARCH/GJR ước lượng daily return variance rồi so với
RV intraday làm proxy chung; hai đại lượng không đồng nhất chính xác từng ngày.
Tổ hợp lấy trung bình đều **phương sai**, sau đó mới lấy căn để ra sigma.
Không tối ưu trọng số từ evaluation.

LSTM/Transformer/GRU, order book, funding rate và open interest không thuộc
bộ kết quả hiện có. Không viết rằng nhóm đã kiểm tra các mô hình/biến này.
`log_turn_rel` là proxy relative quote volume, không phải volume/market cap.

| Coin | h | ENet alpha | ENet l1_ratio | XGB depth | Learning rate | Boosting rounds |
|---|---|---|---|---|---|---|
| BTCUSDT | 1 | 0.001 | 0.1 | 2 | 0.03 | 250 |
| BTCUSDT | 7 | 0.1 | 0.9 | 2 | 0.03 | 100 |
| ETHUSDT | 1 | 0.01 | 0.5 | 2 | 0.03 | 250 |
| ETHUSDT | 7 | 0.01 | 0.9 | 2 | 0.03 | 100 |

Nguồn: [outputs/model_selection/backend3_locked.json](../outputs/model_selection/backend3_locked.json). Bộ lọc: `selected_parameters; khóa từ warmup`.

Số dòng tuning hợp lệ thực tế mỗi coin: h1 có 347 train và 132 validation;
h7 có 305 và 126. Điều kiện đủ trailing/target làm validation thực tế từ
21/07 đến 29/11/2020; không khẳng định đã dùng đủ mọi ngày của khoảng thiết kế.
Không dùng evaluation chọn lại tham số. Lịch refit evaluation không phải bước
tuning siêu tham số.

Chẩn đoán kinh tế lượng: 2928 fit GARCH/GJR, không có fit thất bại; sai lệch
đệ quy đối chiếu thư viện tối đa 8.53e-14. Hội tụ không đảm bảo đặc tả đúng.

| Coin | Model | Window | Fit thành công | Persistence gần 1 | ν ≤ 4 |
|---|---|---|---|---|---|
| BTCUSDT | GARCH-t | expanding | 366 | 366 | 366 |
| BTCUSDT | GARCH-t | rolling | 366 | 183 | 353 |
| BTCUSDT | GJR-GARCH-t | expanding | 366 | 366 | 366 |
| BTCUSDT | GJR-GARCH-t | rolling | 366 | 199 | 359 |
| ETHUSDT | GARCH-t | expanding | 366 | 94 | 366 |
| ETHUSDT | GARCH-t | rolling | 366 | 104 | 230 |
| ETHUSDT | GJR-GARCH-t | expanding | 366 | 126 | 365 |
| ETHUSDT | GJR-GARCH-t | rolling | 366 | 90 | 230 |

Nguồn: [outputs/diagnostics/garch_diagnostic_summary.csv](../outputs/diagnostics/garch_diagnostic_summary.csv). Bộ lọc: `tất cả 8 nhóm`.

ν≤4 nghĩa là innovation Student-t không có moment bậc bốn hữu hạn.
Persistence gần 1 hạn chế cách diễn giải variance vô điều kiện và residual tests.
Đây là hạn chế cần đưa vào thảo luận, không phải lý do xóa fit theo kết quả test.
Chi tiết chạy code: [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).

## 6 RQ1 Độ chính xác dự báo biến động

### 6.1 Bảng chính h1 và rolling

Mỗi coin dùng **1667 ngày chung của cả 9 model**. RMSE/MAE tính trên RV %²,
QLIKE không có đơn vị; cả ba càng thấp càng tốt. Thập phân dùng dấu chấm như
file CSV gốc. Số trên bảng được làm tròn để đọc, file nguồn giữ độ chính xác.

#### BTCUSDT

| Model | N | QLIKE | RMSE (%²) | MAE (%²) | QLIKE/HAR |
|---|---|---|---|---|---|
| Elastic Net | 1667 | 0.3541 | 20.4055 | 6.4164 | 0.9355 |
| XGBoost | 1667 | 0.3747 | 20.8765 | 6.0896 | 0.9900 |
| HAR-RV | 1667 | 0.3785 | 20.9321 | 6.6033 | 1.0000 |
| Tổ hợp 4 | 1667 | 0.3847 | 20.8015 | 6.6623 | 1.0164 |
| Tổ hợp 3 | 1667 | 0.4066 | 20.9261 | 7.0196 | 1.0744 |
| GARCH-t | 1667 | 0.4288 | 21.3431 | 7.5440 | 1.1330 |
| GJR-GARCH-t | 1667 | 0.4534 | 21.8606 | 7.6532 | 1.1980 |
| Naive RV | 1667 | 0.5381 | 26.0212 | 6.9051 | 1.4216 |
| Historical mean | 1667 | 0.5431 | 22.6458 | 9.3282 | 1.4349 |

#### ETHUSDT

| Model | N | QLIKE | RMSE (%²) | MAE (%²) | QLIKE/HAR |
|---|---|---|---|---|---|
| Elastic Net | 1667 | 0.3019 | 43.0865 | 9.8258 | 0.8817 |
| XGBoost | 1667 | 0.3391 | 44.2391 | 9.7525 | 0.9903 |
| Tổ hợp 4 | 1667 | 0.3415 | 43.5949 | 10.5392 | 0.9972 |
| HAR-RV | 1667 | 0.3424 | 47.0402 | 11.2943 | 1.0000 |
| Tổ hợp 3 | 1667 | 0.3651 | 43.7932 | 11.1187 | 1.0663 |
| GARCH-t | 1667 | 0.4031 | 44.6524 | 11.8974 | 1.1770 |
| GJR-GARCH-t | 1667 | 0.4157 | 44.9438 | 12.1779 | 1.2139 |
| Naive RV | 1667 | 0.4377 | 55.5568 | 11.0236 | 1.2783 |
| Historical mean | 1667 | 0.5625 | 47.1983 | 15.3637 | 1.6427 |

Nguồn: [outputs/tables/model_comparison.csv](../outputs/tables/model_comparison.csv). Bộ lọc: `horizon_days=1; window=rolling; từng symbol; cùng mẫu 9 model`.

Elastic Net có QLIKE/RMSE thấp nhất ở hai coin trong bảng này, nhưng XGBoost
có MAE thấp nhất. Như vậy thứ hạng phụ thuộc loss. QLIKE là thước đo chính đã
chốt trước, không đổi sang MAE chỉ vì một model đứng đầu MAE.

### 6.2 DM so với HAR

d = loss(model) − loss(HAR). D âm là loss thấp hơn HAR. Chỉ khi p<0.05 mới có
bằng chứng danh nghĩa chống giả thuyết loss kỳ vọng bằng nhau, theo giả định
kiểm định đang dùng. P-value nhỏ với d dương là model **kém hơn** HAR.

| Coin | Model | N | Chênh QLIKE với HAR | DM-HLN | p-value |
|---|---|---|---|---|---|
| BTCUSDT | Tổ hợp 4 | 1667 | 0.006202 | 0.7259 | 0.4680 |
| BTCUSDT | Tổ hợp 3 | 1667 | 0.028155 | 3.6571 | 0.0003 |
| BTCUSDT | Elastic Net | 1667 | -0.024427 | -0.9926 | 0.3211 |
| BTCUSDT | GARCH-t | 1667 | 0.050335 | 4.6260 | 4.02e-06 |
| BTCUSDT | GJR-GARCH-t | 1667 | 0.074942 | 5.0773 | 4.26e-07 |
| BTCUSDT | Historical mean | 1667 | 0.164622 | 9.5696 | 3.71e-21 |
| BTCUSDT | Naive RV | 1667 | 0.159566 | 3.3603 | 0.0008 |
| BTCUSDT | XGBoost | 1667 | -0.003771 | -0.1536 | 0.8780 |
| ETHUSDT | Tổ hợp 4 | 1667 | -0.000949 | -0.0711 | 0.9434 |
| ETHUSDT | Tổ hợp 3 | 1667 | 0.022691 | 2.0889 | 0.0369 |
| ETHUSDT | Elastic Net | 1667 | -0.040526 | -1.4719 | 0.1412 |
| ETHUSDT | GARCH-t | 1667 | 0.060623 | 2.5588 | 0.0106 |
| ETHUSDT | GJR-GARCH-t | 1667 | 0.073246 | 3.2455 | 0.0012 |
| ETHUSDT | Historical mean | 1667 | 0.220093 | 9.2617 | 6.00e-20 |
| ETHUSDT | Naive RV | 1667 | 0.095298 | 2.1497 | 0.0317 |
| ETHUSDT | XGBoost | 1667 | -0.003308 | -0.0768 | 0.9388 |

Nguồn: [outputs/tables/dm_vs_benchmark.csv](../outputs/tables/dm_vs_benchmark.csv). Bộ lọc: `window=rolling; horizon_days=1; loss=qlike; benchmark=har_rv`.

**Cách viết kết quả:** “Các mô hình ML có cải thiện QLIKE theo điểm ước lượng
so với HAR-RV trong cấu hình chính, nhưng kiểm định DM-HLN chưa cung cấp bằng
chứng cải thiện có ý nghĩa thống kê ở mức 5%. Elastic Net đạt loss thấp nhất
trong mẫu chung; kết quả không ủng hộ kết luận ML luôn vượt mô hình kinh tế lượng.”

GARCH/GJR có QLIKE cao hơn HAR với p<0.05 ở hai coin trong bảng này. Nếu phân
tích RMSE/MAE, lấy loss=se/ae ở file DM, không dùng p-value QLIKE để chứng minh
ý nghĩa thống kê cho một metric khác. P-value chưa điều chỉnh nhiều phép thử.

### 6.3 Vì sao số ngày của các bảng khác nhau

| Coin | Model | Ngày yêu cầu | Forecast thành công | Target RV hợp lệ | Mẫu chung RV |
|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 1826 | 1673 | 1819 | 1667 |
| BTCUSDT | GARCH-t | 1826 | 1826 | 1819 | 1667 |
| BTCUSDT | GJR-GARCH-t | 1826 | 1826 | 1819 | 1667 |
| BTCUSDT | HAR-RV | 1826 | 1673 | 1819 | 1667 |
| BTCUSDT | XGBoost | 1826 | 1673 | 1819 | 1667 |
| ETHUSDT | Elastic Net | 1826 | 1673 | 1819 | 1667 |
| ETHUSDT | GARCH-t | 1826 | 1826 | 1819 | 1667 |
| ETHUSDT | GJR-GARCH-t | 1826 | 1826 | 1819 | 1667 |
| ETHUSDT | HAR-RV | 1826 | 1673 | 1819 | 1667 |
| ETHUSDT | XGBoost | 1826 | 1673 | 1819 | 1667 |

Nguồn: [outputs/tables/forecast_coverage.csv](../outputs/tables/forecast_coverage.csv). Bộ lọc: `horizon_days=1; window=rolling; core models và Elastic Net`.

Tổng lịch evaluation=1826 ngày/coin. Có 1819 target RV hợp lệ. HAR/ML cần
feature trailing đầy đủ nên có 1673 forecast thành công; giao với target hợp lệ
còn 1667 ngày. Risk chấm return close-to-close, lại cần 20 residual quá khứ cho
FHS, nên mẫu chung risk=1653. Không cộng/trừ hai mẫu như thể cùng một tập ngày.

## 7 RQ2 Biến bổ sung và giải thích dự báo

### 7.1 Có và không có volume

| Coin | ML | N | QLIKE có volume | QLIKE bỏ volume | Chênh có−bỏ | p DM |
|---|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 1667 | 0.3541 | 0.3545 | -0.000413 | 0.9346 |
| ETHUSDT | Elastic Net | 1667 | 0.3019 | 0.3097 | -0.007779 | 0.2978 |
| BTCUSDT | XGBoost | 1667 | 0.3747 | 0.3872 | -0.012445 | 0.2385 |
| ETHUSDT | XGBoost | 1667 | 0.3391 | 0.3486 | -0.009435 | 0.4914 |

Nguồn: [outputs/tables/backend3_volume_ablation.csv](../outputs/tables/backend3_volume_ablation.csv). Bộ lọc: `horizon_days=1; window=rolling`.

Cùng tham số, cùng dòng train và mẫu test cặp; volume gồm log_qv/log_turn_rel.
QLIKE giảm nhẹ ở cả bốn trường hợp nhưng DM p>0.05. Cách viết phù hợp là “chưa
có bằng chứng thống kê rõ về giá trị dự báo gia tăng của volume trong cấu hình
chính”, không viết “volume không ảnh hưởng” hoặc “volume đã chứng minh giúp model tốt hơn”.

### 7.2 Sensitivity VIX và USD

Macro chỉ dùng nhánh sensitivity riêng, có ALFRED vintage. Quy tắc bảo thủ:
available_at = vintage_date + 2 ngày UTC, dùng as-of backward theo thông tin
đã khả dụng; không backfill hay dùng bản FRED hiện tại gán về quá khứ. Giữ nguyên
tham số warmup, cùng dòng train/test của tám biến thể. Baseline macro_base của
thí nghiệm này khác về điều kiện mẫu train so với baseline chính; phải dùng
chênh lệch trong chính bảng macro, không ghép ngang hai bảng một cách tùy ý.

| Coin | ML | Biến thể | N | QLIKE | Chênh với macro_base | p DM |
|---|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | macro_base | 1667 | 0.3541 | 0.000000 | — |
| BTCUSDT | Elastic Net | vix | 1667 | 0.3536 | -0.000450 | 0.8208 |
| BTCUSDT | Elastic Net | usd | 1667 | 0.3551 | 0.001041 | 0.7148 |
| BTCUSDT | Elastic Net | vix_usd | 1667 | 0.3537 | -0.000403 | 0.8874 |
| BTCUSDT | XGBoost | macro_base | 1667 | 0.3749 | 0.000000 | — |
| BTCUSDT | XGBoost | vix | 1667 | 0.3796 | 0.004700 | 0.4897 |
| BTCUSDT | XGBoost | usd | 1667 | 0.3696 | -0.005313 | 0.0859 |
| BTCUSDT | XGBoost | vix_usd | 1667 | 0.3781 | 0.003187 | 0.6268 |
| ETHUSDT | Elastic Net | macro_base | 1667 | 0.3019 | 0.000000 | — |
| ETHUSDT | Elastic Net | vix | 1667 | 0.2978 | -0.004081 | 0.0390 |
| ETHUSDT | Elastic Net | usd | 1667 | 0.3012 | -0.000742 | 0.5686 |
| ETHUSDT | Elastic Net | vix_usd | 1667 | 0.2974 | -0.004486 | 0.0409 |
| ETHUSDT | XGBoost | macro_base | 1667 | 0.3391 | 0.000000 | — |
| ETHUSDT | XGBoost | vix | 1667 | 0.3325 | -0.006560 | 0.1063 |
| ETHUSDT | XGBoost | usd | 1667 | 0.3343 | -0.004826 | 0.3826 |
| ETHUSDT | XGBoost | vix_usd | 1667 | 0.3340 | -0.005053 | 0.1541 |

Nguồn: [outputs/tables/backend3_macro_ablation.csv](../outputs/tables/backend3_macro_ablation.csv). Bộ lọc: `horizon_days=1; window=rolling; cùng mẫu eight variants`.

Ở ETH/Elastic Net, VIX và VIX+USD có p lần lượt khoảng 0.0390 và 0.0409,
chênh QLIKE âm. Đây là bằng chứng **danh nghĩa** chưa điều chỉnh nhiều phép thử;
không đủ để tuyên bố hiệu quả chung cho mọi coin/model. XGBoost/BTC thêm USD
có p≈0.0859, chưa đạt mức 5%. Không đổi macro vào model chính sau khi xem kết quả.

Nguồn phụ: [macro_sensitivity.md](macro_sensitivity.md),
[macro validation](../outputs/sensitivity/macro/validation.json). Bộ này có
1790 vintage VIX, 361 vintage USD, 23360 fit thành công và 16 file forecast;
23 ô có observation_date sau vintage bị loại khỏi bước chọn feature.

### 7.3 SHAP

| Coin | Hạng | Feature | Mean abs SHAP | N origin |
|---|---|---|---|---|
| BTCUSDT | 1 | log_rv_d | 0.2381 | 1673 |
| BTCUSDT | 2 | log_rv_m | 0.1520 | 1673 |
| BTCUSDT | 3 | log_rv_w | 0.1120 | 1673 |
| BTCUSDT | 4 | log_qv | 0.0833 | 1673 |
| BTCUSDT | 5 | log_park | 0.0682 | 1673 |
| BTCUSDT | 6 | ret_d | 0.0506 | 1673 |
| BTCUSDT | 7 | log_turn_rel | 0.0394 | 1673 |
| ETHUSDT | 1 | log_rv_d | 0.2186 | 1673 |
| ETHUSDT | 2 | log_rv_w | 0.1402 | 1673 |
| ETHUSDT | 3 | log_qv | 0.1387 | 1673 |
| ETHUSDT | 4 | log_rv_m | 0.1345 | 1673 |
| ETHUSDT | 5 | log_park | 0.0622 | 1673 |
| ETHUSDT | 6 | ret_d | 0.0446 | 1673 |
| ETHUSDT | 7 | log_turn_rel | 0.0362 | 1673 |

Nguồn: [outputs/tables/backend3_shap_importance.csv](../outputs/tables/backend3_shap_importance.csv). Bộ lọc: `horizon_days=1; window=rolling; XGBoost native exact TreeSHAP`.

log_rv_d có importance cao nhất ở hai coin trong bảng. SHAP là đóng góp vào
raw log RV prediction của nhiều estimator walk-forward, không phải tác động
nhân quả hay số điểm phần trăm volatility. SHAP lớn không thay cho ablation/DM
để khẳng định incremental predictive power. Base value cộng contributions khớp
raw log prediction; train smearing được áp dụng sau bước này.

## 8 RQ3 Kết quả theo trạng thái thị trường

| Coin | Crisis threshold RV22 (%²) | N hiệu chuẩn | Giai đoạn |
|---|---|---|---|
| BTCUSDT | 25.4502 | 487 | 2019–2020, cố định sau warmup |
| ETHUSDT | 35.5017 | 487 | 2019–2020, cố định sau warmup |

Nguồn: [data/processed/regime_thresholds.json](../data/processed/regime_thresholds.json). Bộ lọc: `quantile=0.90; n_calibration=487 mỗi coin`.

Regime gắn tại origin bằng thông tin đã biết: crisis nếu RV22 vượt ngưỡng;
nếu không, bear khi return log 90 ngày ≤−10%, bull khi ≥10%, còn lại normal.
Ưu tiên crisis > bear > bull > normal. Không dùng RV target để gán regime.

| Coin | Regime | N | HAR | GARCH | GJR | XGBoost | Elastic Net |
|---|---|---|---|---|---|---|---|
| BTCUSDT | normal | 433 | 0.4702 | 0.5264 | 0.5243 | 0.5298 | 0.4876 |
| BTCUSDT | bull | 642 | 0.3044 | 0.3457 | 0.3526 | 0.2851 | 0.2897 |
| BTCUSDT | bear | 504 | 0.3939 | 0.4446 | 0.4848 | 0.3508 | 0.3284 |
| BTCUSDT | crisis | 88 | 0.3788 | 0.4649 | 0.6608 | 0.4028 | 0.3135 |
| ETHUSDT | normal | 332 | 0.4661 | 0.5489 | 0.6088 | 0.5497 | 0.4560 |
| ETHUSDT | bull | 691 | 0.2995 | 0.3588 | 0.3772 | 0.2907 | 0.2713 |
| ETHUSDT | bear | 546 | 0.3100 | 0.3432 | 0.3173 | 0.2487 | 0.2392 |
| ETHUSDT | crisis | 98 | 0.4068 | 0.5546 | 0.5805 | 0.4713 | 0.3453 |

Nguồn: [outputs/tables/regime_performance.csv](../outputs/tables/regime_performance.csv). Bộ lọc: `horizon_days=1; window=rolling; QLIKE; cùng ngày theo từng regime`.

Bảng cho thấy không có lợi thế ML đồng đều: XGBoost có QLIKE cao hơn HAR ở
normal và crisis của cả hai coin, dù toàn mẫu h1 có QLIKE hơi thấp hơn HAR.
Elastic Net có điểm QLIKE crisis thấp hơn HAR, với chỉ 88 ngày BTC và 98 ngày ETH.
Muốn viết “khác biệt có ý nghĩa”, tra [dm_by_regime.csv](../outputs/tables/dm_by_regime.csv)
đúng coin/horizon/window/regime/model/loss. Không lấy p-value toàn mẫu cho crisis.
Named stress windows ở mục 10 không đồng nhất với regime crisis hiệu chuẩn này.

## 9 Robustness cửa sổ và horizon

| Coin | h | Model | N cặp | QLIKE rolling | QLIKE expanding | Chênh exp−roll | p DM exp/roll |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 1 | HAR-RV | 1667 | 0.3785 | 0.3852 | 0.006750 | 0.1581 |
| BTCUSDT | 1 | GARCH-t | 1667 | 0.4288 | 0.4289 | 0.000083 | 0.9893 |
| BTCUSDT | 1 | GJR-GARCH-t | 1667 | 0.4534 | 0.4472 | -0.006198 | 0.3684 |
| BTCUSDT | 1 | XGBoost | 1667 | 0.3747 | 0.3762 | 0.001462 | 0.8959 |
| BTCUSDT | 1 | Elastic Net | 1667 | 0.3541 | 0.3496 | -0.004479 | 0.1525 |
| BTCUSDT | 7 | HAR-RV | 1631 | 0.2271 | 0.2296 | 0.002451 | 0.6569 |
| BTCUSDT | 7 | GARCH-t | 1631 | 0.2638 | 0.2604 | -0.003339 | 0.6659 |
| BTCUSDT | 7 | GJR-GARCH-t | 1631 | 0.2856 | 0.2611 | -0.024448 | 0.0090 |
| BTCUSDT | 7 | XGBoost | 1631 | 0.2142 | 0.2122 | -0.001997 | 0.8192 |
| BTCUSDT | 7 | Elastic Net | 1631 | 0.2193 | 0.2213 | 0.001999 | 0.6441 |
| ETHUSDT | 1 | HAR-RV | 1667 | 0.3424 | 0.3606 | 0.018159 | 0.0020 |
| ETHUSDT | 1 | GARCH-t | 1667 | 0.4031 | 0.3882 | -0.014880 | 0.4942 |
| ETHUSDT | 1 | GJR-GARCH-t | 1667 | 0.4157 | 0.3926 | -0.023062 | 0.2245 |
| ETHUSDT | 1 | XGBoost | 1667 | 0.3391 | 0.3347 | -0.004465 | 0.4427 |
| ETHUSDT | 1 | Elastic Net | 1667 | 0.3019 | 0.3031 | 0.001175 | 0.8353 |
| ETHUSDT | 7 | HAR-RV | 1631 | 0.2452 | 0.2457 | 0.000487 | 0.9501 |
| ETHUSDT | 7 | GARCH-t | 1631 | 0.2619 | 0.2730 | 0.011078 | 0.4587 |
| ETHUSDT | 7 | GJR-GARCH-t | 1631 | 0.2815 | 0.2724 | -0.009096 | 0.5270 |
| ETHUSDT | 7 | XGBoost | 1631 | 0.2187 | 0.2127 | -0.006091 | 0.3906 |
| ETHUSDT | 7 | Elastic Net | 1631 | 0.2088 | 0.2096 | 0.000800 | 0.9124 |

Nguồn: [outputs/tables/robustness.csv](../outputs/tables/robustness.csv). Bộ lọc: `core models và Elastic Net; so cùng model/horizon, giao mẫu windows và models`.

H7 là tổng RV 7 ngày, không phải RV trung bình và không phải bài toán risk
7 ngày. Không kết luận h7 “tốt hơn h1” chỉ vì QLIKE/RMSE có giá trị khác.
H1 có N=1667, h7 có N=1631; target h7 cần đủ cả bảy ngày và kết thúc trong evaluation.
Các p-value trên so expanding với rolling, không so model với HAR.

Ví dụ ETH/HAR h1 expanding có QLIKE cao hơn rolling, p≈0.0020; BTC/GJR h7
expanding có QLIKE thấp hơn rolling, p≈0.0090. Các dấu hiệu phụ thuộc model/horizon,
không ủng hộ tuyên bố một loại cửa sổ luôn thắng. Giữ rolling làm kết quả chính
theo thiết kế, không chọn lại cửa sổ sau khi xem bảng.

## 10 RQ4 VaR ES và backtesting

### 10.1 Quy ước và phạm vi

VaR/ES là lower-tail **return**, đơn vị % log return. Alpha=.05/.01 tương ứng
confidence 95%/99%. Ví dụ VaR=-5% nghĩa là ngưỡng đuôi trái của log return,
không phải dự báo lợi nhuận chắc chắn hay loss dương 5%. Breach khi actual return
< VaR. ES là kỳ vọng đuôi và phải ≤VaR theo cùng quy ước.

GARCH/GJR dùng Student-t chuẩn hóa. Các model còn lại dùng FHS từ residual ngoài
mẫu của đúng coin/model/window, chỉ sau khi return đã quan sát; tối thiểu 20
residual. Không dùng residual 2021–2025 của tương lai để tính VaR ngày đầu.
Đầu FHS có tail 1% rất ít điểm, thể hiện ở n_fhs_tail; ES có thể kém ổn định.
Mẫu chung risk bắt đầu 06/02/2021 và có 1653 ngày, không phải toàn bộ 1826 ngày.

| Coin | Model | Ngày lịch | Risk khả dụng | Ngày chung | Ngày risk đầu |
|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 1826 | 1653 | 1653 | 2021-02-06 |
| BTCUSDT | GARCH-t | 1826 | 1826 | 1653 | 2021-01-01 |
| BTCUSDT | GJR-GARCH-t | 1826 | 1826 | 1653 | 2021-01-01 |
| BTCUSDT | HAR-RV | 1826 | 1653 | 1653 | 2021-02-06 |
| BTCUSDT | XGBoost | 1826 | 1653 | 1653 | 2021-02-06 |
| ETHUSDT | Elastic Net | 1826 | 1653 | 1653 | 2021-02-06 |
| ETHUSDT | GARCH-t | 1826 | 1826 | 1653 | 2021-01-01 |
| ETHUSDT | GJR-GARCH-t | 1826 | 1826 | 1653 | 2021-01-01 |
| ETHUSDT | HAR-RV | 1826 | 1653 | 1653 | 2021-02-06 |
| ETHUSDT | XGBoost | 1826 | 1653 | 1653 | 2021-02-06 |

Nguồn: [outputs/risk/coverage.csv](../outputs/risk/coverage.csv). Bộ lọc: `window=rolling; alpha=0.05; core models và Elastic Net`.

### 10.2 Coverage và quantile loss trên cùng mẫu

Cả hai bảng dưới dùng 1653 ngày/model/coin. Kỳ vọng khoảng 82.65 breach ở mức
95%, và 16.53 breach ở mức 99%; không yêu cầu observed count bằng chính xác kỳ vọng.
QLoss là pinball/quantile loss, càng thấp càng tốt. Không xếp hạng theo p-value
lớn nhất. P-value >0.05 là chưa bác bỏ theo kiểm định, không chứng minh đúng.

#### Confidence 95%

| Coin | Model | Breach/N | Breach rate | p Kupiec | p Christoffersen | QLoss |
|---|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 88/1653 | 5.32% | 0.5500 | 0.6953 | 0.3395 |
| BTCUSDT | GARCH-t | 92/1653 | 5.57% | 0.2996 | 0.2688 | 0.3421 |
| BTCUSDT | GJR-GARCH-t | 92/1653 | 5.57% | 0.2996 | 0.1500 | 0.3457 |
| BTCUSDT | HAR-RV | 85/1653 | 5.14% | 0.7918 | 0.4588 | 0.3413 |
| BTCUSDT | XGBoost | 90/1653 | 5.44% | 0.4132 | 0.6317 | 0.3395 |
| ETHUSDT | Elastic Net | 90/1653 | 5.44% | 0.4132 | 0.7150 | 0.4606 |
| ETHUSDT | GARCH-t | 96/1653 | 5.81% | 0.1414 | 0.1242 | 0.4598 |
| ETHUSDT | GJR-GARCH-t | 100/1653 | 6.05% | 0.0577 | 0.1201 | 0.4578 |
| ETHUSDT | HAR-RV | 92/1653 | 5.57% | 0.2996 | 0.2688 | 0.4580 |
| ETHUSDT | XGBoost | 89/1653 | 5.38% | 0.4788 | 0.5040 | 0.4624 |

#### Confidence 99%

| Coin | Model | Breach/N | Breach rate | p Kupiec | p Christoffersen | QLoss |
|---|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 16/1653 | 0.97% | 0.8952 | 0.8473 | 0.1037 |
| BTCUSDT | GARCH-t | 15/1653 | 0.91% | 0.7008 | 0.2860 | 0.1067 |
| BTCUSDT | GJR-GARCH-t | 17/1653 | 1.03% | 0.9079 | 0.3817 | 0.1094 |
| BTCUSDT | HAR-RV | 13/1653 | 0.79% | 0.3647 | 0.5979 | 0.1021 |
| BTCUSDT | XGBoost | 17/1653 | 1.03% | 0.9079 | 0.8319 | 0.1051 |
| ETHUSDT | Elastic Net | 16/1653 | 0.97% | 0.8952 | 0.8473 | 0.1427 |
| ETHUSDT | GARCH-t | 19/1653 | 1.15% | 0.5509 | 0.3877 | 0.1454 |
| ETHUSDT | GJR-GARCH-t | 17/1653 | 1.03% | 0.9079 | 0.3817 | 0.1443 |
| ETHUSDT | HAR-RV | 10/1653 | 0.60% | 0.0815 | 0.2063 | 0.1416 |
| ETHUSDT | XGBoost | 14/1653 | 0.85% | 0.5207 | 0.7215 | 0.1481 |

Nguồn: [outputs/risk/backtest.csv](../outputs/risk/backtest.csv). Bộ lọc: `window=rolling; sample=common_all_9_models; alpha=0.05/0.01; core và Elastic Net`.

Christoffersen chỉ đếm cặp ngày lịch liền nhau: 1646 cặp, 6 khoảng ngắt
trên mẫu chung này. File ghi `asymptotic_gapped_sample`; p-value là chẩn đoán
tiệm cận chịu ảnh hưởng của mẫu thiếu. Không nén khoảng thiếu rồi coi hai dòng
còn lại là hai ngày liên tiếp.

Kết quả volatility không tự chuyển thành thứ hạng risk: HAR có QLoss VaR 99%
thấp hơn XGBoost ở hai coin trong bảng, dù XGBoost có QLIKE RV thấp hơn HAR.
Chưa có kiểm định sai khác QLoss risk trong bảng này, nên chỉ so điểm ước lượng.

### 10.3 Một ví dụ VaR và ES thực tế

Lấy cố định target **31/12/2025**, window=rolling, forecast có sẵn từ 00:00 UTC
ngày đó dựa trên dữ liệu đến hết 30/12/2025. Đây là ví dụ đọc file, không dùng
một ngày để kết luận hiệu quả cả mô hình.

| Coin | Model | VaR95 (%) | ES95 (%) | VaR99 (%) | ES99 (%) | Return thực tế (%) |
|---|---|---|---|---|---|---|
| BTCUSDT | HAR-RV | -3.2681 | -4.8332 | -5.7627 | -7.1325 | -0.9507 |
| BTCUSDT | GARCH-t | -2.8348 | -4.2850 | -5.0247 | -7.0090 | -0.9507 |
| BTCUSDT | GJR-GARCH-t | -2.8161 | -4.2615 | -4.9953 | -6.9856 | -0.9507 |
| BTCUSDT | XGBoost | -3.6249 | -5.4427 | -6.4950 | -8.3274 | -0.9507 |
| BTCUSDT | Elastic Net | -3.1620 | -4.7406 | -5.5885 | -7.1961 | -0.9507 |
| ETHUSDT | HAR-RV | -4.9922 | -7.1457 | -8.5151 | -10.4929 | -0.0690 |
| ETHUSDT | GARCH-t | -4.8385 | -7.5855 | -8.8997 | -12.9714 | -0.0690 |
| ETHUSDT | GJR-GARCH-t | -4.7607 | -7.4129 | -8.6916 | -12.5890 | -0.0690 |
| ETHUSDT | XGBoost | -4.2273 | -6.2419 | -7.4378 | -9.4511 | -0.0690 |
| ETHUSDT | Elastic Net | -4.2866 | -6.4243 | -7.5093 | -9.4565 | -0.0690 |

Nguồn: từng [file risk Parquet](../outputs/risk/), `date=2025-12-31; window=rolling; alpha=.05/.01`.

ES trong toàn bộ mẫu có các thống kê mô tả observed_es_pct và
mean_es_on_breach_pct tại backtest.csv. Hai thống kê này không phải kiểm định
hiệu chuẩn ES. Kupiec và Christoffersen đánh giá **VaR coverage**. Không viết
“ES đã vượt qua Kupiec/Christoffersen”.

### 10.4 Named stress windows

Bảng ghi **số breach**, mẫu chung của 9 model, không phải phần trăm. Các cửa sổ
được định trước theo ngày lịch; không đồng nhất với nhãn regime ở mục 8.

#### Breach confidence 95%

| Coin | Stress window | N | HAR | GARCH | GJR | XGBoost |
|---|---|---|---|---|---|---|
| BTCUSDT | 01–31/05/2021 | 14 | 1.0 | 1.0 | 2.0 | 1.0 |
| BTCUSDT | 07–13/05/2022 | 7 | 1.0 | 1.0 | 2.0 | 1.0 |
| BTCUSDT | 06–14/11/2022 | 9 | 2.0 | 2.0 | 2.0 | 2.0 |
| ETHUSDT | 01–31/05/2021 | 14 | 1.0 | 1.0 | 1.0 | 2.0 |
| ETHUSDT | 07–13/05/2022 | 7 | 2.0 | 2.0 | 2.0 | 2.0 |
| ETHUSDT | 06–14/11/2022 | 9 | 2.0 | 2.0 | 2.0 | 2.0 |

#### Breach confidence 99%

| Coin | Stress window | N | HAR | GARCH | GJR | XGBoost |
|---|---|---|---|---|---|---|
| BTCUSDT | 01–31/05/2021 | 14 | 1.0 | 1.0 | 1.0 | 1.0 |
| BTCUSDT | 07–13/05/2022 | 7 | 1.0 | 1.0 | 1.0 | 1.0 |
| BTCUSDT | 06–14/11/2022 | 9 | 1.0 | 2.0 | 2.0 | 1.0 |
| ETHUSDT | 01–31/05/2021 | 14 | 1.0 | 1.0 | 1.0 | 1.0 |
| ETHUSDT | 07–13/05/2022 | 7 | 0.0 | 1.0 | 1.0 | 1.0 |
| ETHUSDT | 06–14/11/2022 | 9 | 1.0 | 2.0 | 2.0 | 1.0 |

Nguồn: [outputs/risk/crisis_breaches.csv](../outputs/risk/crisis_breaches.csv). Bộ lọc: `window=rolling; sample=common_all_9_models; ba crisis trong evaluation`.

COVID 12–16/03/2020 nằm trong warmup, không có evaluation forecast. File
ghi outside_evaluation, n=0 và breach để thiếu; không được viết “không có breach
COVID” từ các ô này. Các cửa sổ 7/9 ngày quá nhỏ để khẳng định calibration tốt
chỉ từ vài breach. Dùng để mô tả hành vi stress và đọc cùng toàn mẫu.

## 11 RQ5 Volatility targeting và ý nghĩa kinh tế

Mô phỏng cố định: mục tiêu volatility 15%/năm, 365 ngày/năm, max weight=1,
phí một chiều 5 bps, lãi tiền mặt=0. Chuyển log return thành simple return rồi
ghép wealth; phí trên turnover gồm lệnh mua ban đầu của cả chiến lược và
buy-and-hold. Dùng sigma forecast gốc của đúng ngày, không suy từ VaR.

Thiếu sigma thì giữ nguyên số lượng coin, không giao dịch; không bỏ ngày.
Định giá vị thế đang giữ tại cuối mẫu, không bắt buộc bán cuối kỳ. Mẫu chiến
lược là đủ 1826 ngày, khác mẫu chung RV/risk. HAR/ML có 153 ngày thiếu forecast;
GARCH/GJR có đủ forecast. Vì vậy mức tiếp xúc và chính sách khi thiếu cũng ảnh
hưởng kết quả kinh tế, không chỉ độ chính xác dự báo.

| Coin | Model | CAGR chiến lược (%) | CAGR B&H (%) | Sharpe chiến lược | Sharpe B&H | MDD chiến lược (%) | MDD B&H (%) |
|---|---|---|---|---|---|---|---|
| BTCUSDT | Elastic Net | 7.47 | 24.80 | 0.572 | 0.671 | -26.28 | -76.63 |
| BTCUSDT | GARCH-t | 8.40 | 24.80 | 0.672 | 0.671 | -25.94 | -76.63 |
| BTCUSDT | GJR-GARCH-t | 8.16 | 24.80 | 0.649 | 0.671 | -26.79 | -76.63 |
| BTCUSDT | HAR-RV | 7.69 | 24.80 | 0.603 | 0.671 | -25.83 | -76.63 |
| BTCUSDT | XGBoost | 8.19 | 24.80 | 0.589 | 0.671 | -26.47 | -76.63 |
| ETHUSDT | Elastic Net | 6.72 | 32.15 | 0.502 | 0.747 | -23.03 | -79.30 |
| ETHUSDT | GARCH-t | 9.35 | 32.15 | 0.694 | 0.747 | -21.09 | -79.30 |
| ETHUSDT | GJR-GARCH-t | 9.61 | 32.15 | 0.704 | 0.747 | -21.10 | -79.30 |
| ETHUSDT | HAR-RV | 8.13 | 32.15 | 0.601 | 0.747 | -21.69 | -79.30 |
| ETHUSDT | XGBoost | 7.34 | 32.15 | 0.518 | 0.747 | -25.09 | -79.30 |

Nguồn: [outputs/risk/volatility_targeting.csv](../outputs/risk/volatility_targeting.csv). Bộ lọc: `window=rolling; core models và Elastic Net; 2021–2025`.

MDD là số âm; gần 0 hơn nghĩa là ít sụt giảm hơn. Sharpe dùng simple return,
lãi phi rủi ro giả định 0, annualize sqrt(365). CAGR là tăng trưởng vốn ghép lãi,
không phải mean log return nhân 365. MDD có tính vốn ban đầu bằng 1.

**Cách diễn giải:** chiến lược giữ phần vốn trong cash làm giảm drawdown, đồng
thời giảm mức tăng vốn khi thị trường đi lên. Kết quả không chứng minh dự báo
ML tạo lợi nhuận vượt buy-and-hold. Chưa mô hình slippage, độ trễ khớp lệnh hay
lãi tiền mặt. Daily paths nằm ở [strategy_paths](../outputs/risk/strategy_paths/)
để tái tạo wealth và xem các ngày phí/giao dịch; không dùng tổng số dòng risk
làm số ngày chiến lược.

## 12 Kiểm tra kỹ thuật và trạng thái bàn giao

| Bằng chứng | Kết quả | Nguồn |
|---|---|---|
| Dataset chính | 5756 hàng coin-ngày; input hash được giữ nguyên | data/processed/dataset_meta.json |
| Kinh tế lượng | 2928 fit GARCH/GJR; lỗi 0 | outputs/diagnostics/backend2_validation.json |
| Macro sensitivity | 23360 fit; lỗi 0; 64 dòng so sánh | outputs/sensitivity/macro/validation.json |
| Backend 4 | 47 kiểm thử đạt; checksum/lịch/future-mutation passed | outputs/risk/verification.json |
| File risk | 18 file; 131472 dòng lịch; 124176 dòng chấm được | outputs/risk/run_manifest.json |
| Mẫu risk | 119016 dòng tổng có cờ common; 1653 ngày/coin/model/window/alpha | outputs/risk/coverage.csv |
| RQ5 | 36 paths; 2 coin × 9 model × 2 window | outputs/risk/strategy_paths/ |
| Holdout mô hình | Chưa đánh giá | holdout_evaluated=false / holdout_scored=false |

Dòng risk đếm theo coin × model × window × alpha × ngày, **không phải**
số ngày độc lập hay số nến gốc. 47 là số test riêng Backend 4; số test toàn repo
được kiểm tra riêng khi tích hợp. Unit test đạt không chứng minh dự báo vượt
benchmark, không thay residual diagnostics hay review độc lập của con người.

Kiểm tra tích hợp toàn repo: **100 kiểm thử đạt**, [repository_validation.json](../outputs/reporting/repository_validation.json). Đây là kiểm tra code, không phải kết luận mô hình đạt ý nghĩa thống kê.

## 13 Hình và bảng để đưa vào luận

| Phần | Hình để tải | Chú thích cần giữ |
|---|---|---|
| Dữ liệu | [figure_3_1_prices.png](../outputs/figures/figure_3_1_prices.png) | Giá BTC và ETH, mẫu mô tả 2019–2025, USDT |
| Dữ liệu | [figure_3_2_rv.png](../outputs/figures/figure_3_2_rv.png) | RV ngày %², giữ khoảng thiếu |
| Dữ liệu | [figure_3_3_acf_rv.png](../outputs/figures/figure_3_3_acf_rv.png) | ACF trên đoạn liên tục dài nhất trong warmup; N ở acf_rv.csv |
| Dự báo | [backend1_BTCUSDT_rolling_h1_forecast_vs_actual.png](../outputs/figures/backend1_BTCUSDT_rolling_h1_forecast_vs_actual.png) | Actual/forecast RV và căn RV, kết quả chính |
| Dự báo | [backend1_BTCUSDT_rolling_h1_rolling_qlike.png](../outputs/figures/backend1_BTCUSDT_rolling_h1_rolling_qlike.png) | QLIKE trung bình cửa sổ 90 ngày lịch |
| Regime | [backend1_BTCUSDT_rolling_h1_regimes.png](../outputs/figures/backend1_BTCUSDT_rolling_h1_regimes.png) | Kết quả theo nhãn tại origin |
| SHAP | [backend3_BTCUSDT_rolling_h1_shap.png](../outputs/figures/backend3_BTCUSDT_rolling_h1_shap.png) | Contributions vào raw log RV; không phải causal effect |
| Risk | [BTCUSDT_har_rv_var_breaches.png](../outputs/figures/risk/BTCUSDT_har_rv_var_breaches.png) | HAR: return, VaR, ES và breach; cả 95%/99% |
| Risk | [BTCUSDT_xgboost_var_breaches.png](../outputs/figures/risk/BTCUSDT_xgboost_var_breaches.png) | XGBoost: return, VaR, ES và breach; cả 95%/99% |
| Dự báo | [backend1_ETHUSDT_rolling_h1_forecast_vs_actual.png](../outputs/figures/backend1_ETHUSDT_rolling_h1_forecast_vs_actual.png) | Actual/forecast RV và căn RV, kết quả chính |
| Dự báo | [backend1_ETHUSDT_rolling_h1_rolling_qlike.png](../outputs/figures/backend1_ETHUSDT_rolling_h1_rolling_qlike.png) | QLIKE trung bình cửa sổ 90 ngày lịch |
| Regime | [backend1_ETHUSDT_rolling_h1_regimes.png](../outputs/figures/backend1_ETHUSDT_rolling_h1_regimes.png) | Kết quả theo nhãn tại origin |
| SHAP | [backend3_ETHUSDT_rolling_h1_shap.png](../outputs/figures/backend3_ETHUSDT_rolling_h1_shap.png) | Contributions vào raw log RV; không phải causal effect |
| Risk | [ETHUSDT_har_rv_var_breaches.png](../outputs/figures/risk/ETHUSDT_har_rv_var_breaches.png) | HAR: return, VaR, ES và breach; cả 95%/99% |
| Risk | [ETHUSDT_xgboost_var_breaches.png](../outputs/figures/risk/ETHUSDT_xgboost_var_breaches.png) | XGBoost: return, VaR, ES và breach; cả 95%/99% |

Prefix backend1 trong tên hình là tên module tổng hợp chung, không có nghĩa
hình chỉ chứa output của giai đoạn Backend 1. Hình đã lấy từ forecast thật hiện
có; tra bảng đi kèm để biết N và phạm vi. Khi trích, ghi “Nguồn: tính toán của
nhóm từ Binance spot, snapshot 18/10/2026; evaluation 2021–2025” và bổ sung macro
ALFRED khi hình/bảng sử dụng sensitivity. Không ghi nguồn một paper cho số nhóm tính.

Không dùng hình mô tả 2019–2025 để gọi là OOS forecast, hoặc hình ACF warmup để
gọi là toàn mẫu 2019–2026. Các hình stress thể hiện forecast/breach, không phải
khuyến nghị giao dịch. Tất cả hình model chính ở đây không chấm holdout.

## 14 Những câu cần viết đúng và giới hạn cần giữ

| Có thể viết | Câu cần tránh |
|---|---|
| Elastic Net có QLIKE h1/rolling thấp nhất theo điểm ước lượng | ML đã chứng minh luôn vượt HAR vì QLIKE nhỏ hơn |
| DM QLIKE chưa đạt 5% cho ENet/XGB so với HAR trong cấu hình chính | p>0.05 chứng minh hai model giống hệt nhau |
| Volume giảm loss theo điểm, chưa có bằng chứng thống kê rõ trong h1/rolling | Volume không có tác động hoặc đã chứng minh hữu ích |
| Macro có bằng chứng danh nghĩa theo từng thiết kế | VIX/USD luôn giúp dự báo crypto hoặc có tác động nhân quả |
| Một số risk tests chưa bác bỏ coverage, kèm N và giả định | P-value cao chứng minh model đúng hoặc ES đã pass Kupiec |
| Còn thiếu nến thật, giữ NaN để bảo toàn cách đo RV | Dữ liệu sạch nghĩa là không còn bất kỳ khoảng thiếu nào |
| Backtest chiến lược có phí giả định và mức tiếp xúc thấp | Đây là lợi nhuận có thể thực hiện chắc chắn trên thị trường |
| Snapshot nguồn đến 17/10/2026, evaluation 2021–2025 | Đã chấm mô hình bằng dữ liệu đến hôm nay hoặc cả năm 2026 |

Các giới hạn phải được giữ trong phần thảo luận:

1. Hai tài sản, một sàn spot và đồng định giá USDT; không tự suy rộng toàn bộ crypto.
2. RV là proxy từ 5 phút; có khoảng thiếu, một ngày nguồn Binance bất đồng và
   đối chiếu CoinGecko chỉ bao phủ một phần. Không khẳng định nguồn đã xác minh tuyệt đối.
3. Mẫu chung loại ngày thiếu feature/target; kết quả có thể khác mẫu riêng.
4. GARCH daily return variance và RV intraday là hai cách đo không trùng từng ngày.
5. Chỉ một thiết kế warmup validation; không tối ưu riêng macro. Nhiều phép thử
   DM/chia regime chưa có điều chỉnh multiple testing và có dependence vượt h−1.
6. Regime crisis có ít ngày. Named windows 7/9 ngày chủ yếu mô tả stress.
7. FHS pool đầu ngắn, tail 99% thưa; ES chưa có một kiểm định hiệu chuẩn riêng.
8. ALFRED chỉ có vintage theo ngày, dùng availability bảo thủ; không có timestamp
   công bố chính xác trong ngày, dữ liệu observations cũ không thay vintage.
9. RQ5 chưa slippage/latency/cash yield; thiếu forecast dùng chính sách giữ vị thế.
10. Holdout 2026 chưa chấm; dashboard và phần viết luận cần hoàn thiện riêng.

Đây là ghi nhận phạm vi nghiên cứu hiện tại, không bổ sung thí nghiệm hoặc tự
đổi cấu hình để đáp ứng một kết luận mong muốn.

## 15 Tra nguồn và cập nhật tài liệu

Mọi bảng trên đọc từ file kết quả đã có, không fit/tune lại. Chạy từ gốc repo:

```powershell
python -m src.reporting.build_handoff
```

File này được sinh lại cùng `outputs/reporting/handoff_manifest.json`, ghi
SHA256 các input và SHA256 của tài liệu. Nếu thay snapshot/forecast, tạo lại
toàn bộ kết quả liên quan trước khi sinh lại bàn giao; không sửa số trong bảng
Markdown bằng tay. Manifest nguồn model và lock warmup vẫn cần giữ để tái lập.

- [Quy định nhóm](GROUP_PROTOCOL.md)
- [Hướng dẫn kỹ thuật](TECHNICAL_GUIDE.md)
- [Từ điển dữ liệu](data_dictionary.md)
- [Chất lượng dữ liệu](data_quality_report.md)
- [Nhật ký nguồn](source_log.md) và [bảng nguồn](source_log.csv)
- [Schema forecast và risk](forecast_format.md)
- [Availability macro](macro_sensitivity.md)
- [Các bảng gốc](../outputs/tables/) và [kết quả risk](../outputs/risk/)

Khi viết tổng quan nghiên cứu, nhóm vẫn cần đọc và trích các paper gốc theo
chuẩn tham khảo của môn. Tài liệu này cung cấp kết quả tính của nhóm và hướng
dẫn đối chiếu, không xác thực thay nội dung mọi tài liệu tham khảo trong brief.

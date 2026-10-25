# Kết quả đánh giá cuối trên holdout 2026



Phạm vi **2026-01-01 đến 2026-10-17 UTC**, BTCUSDT và ETHUSDT. Đây là mẫu một phần năm 2026, không đại diện cho trọn năm.

Thiết kế và siêu tham số đã khóa trước lượt chấm này. Mô hình được refit theo lịch 5 ngày với dữ liệu đã quan sát; không chọn lại siêu tham số. Dữ liệu 2026 từng được xem cho QA và mô tả trước đây, không gọi là dữ liệu chưa từng được nhìn thấy.



## 1 Kết luận từ cấu hình chính



- **BTCUSDT:** enet có QLIKE thấp nhất 0.2278; HAR-RV 0.2670; mức giảm 14.70%, trên 290 ngày chung. DM QLIKE so với HAR: p=0.0011, p Holm=0.0110. Có bằng chứng khác biệt sau điều chỉnh trong họ kiểm định chính.

- **ETHUSDT:** enet có QLIKE thấp nhất 0.2376; HAR-RV 0.2895; mức giảm 17.92%, trên 290 ngày chung. DM QLIKE so với HAR: p=0.0430, p Holm=0.2151. Chưa đủ bằng chứng khác biệt ở mức 5% sau điều chỉnh.



Thứ hạng theo điểm là mô tả kết quả holdout. Không dùng bảng này để sửa thiết kế rồi chấm lại cùng mẫu.



## 2 Dự báo variance trên cùng mẫu



| symbol | model | n | QLIKE | RMSE | MAE | QLIKE_relative_to_har |
|---|---|---|---|---|---|---|
| BTCUSDT | combo_core4 | 290.0000 | 0.2516 | 4.5960 | 2.7715 | 0.9423 |
| BTCUSDT | combo_econ | 290.0000 | 0.2706 | 4.9615 | 2.9964 | 1.0136 |
| BTCUSDT | enet | 290.0000 | 0.2278 | 4.0736 | 2.3810 | 0.8530 |
| BTCUSDT | garch | 290.0000 | 0.2913 | 5.4656 | 3.2488 | 1.0911 |
| BTCUSDT | gjr_garch | 290.0000 | 0.2716 | 5.7305 | 3.2069 | 1.0172 |
| BTCUSDT | har_rv | 290.0000 | 0.2670 | 4.5138 | 2.6998 | 1.0000 |
| BTCUSDT | hist_mean | 290.0000 | 0.4056 | 5.7655 | 3.8222 | 1.5189 |
| BTCUSDT | naive_rw | 290.0000 | 0.3969 | 4.3769 | 2.5726 | 1.4865 |
| BTCUSDT | xgboost | 290.0000 | 0.2293 | 4.2994 | 2.3882 | 0.8587 |
| ETHUSDT | combo_core4 | 290.0000 | 0.3110 | 8.0588 | 5.8945 | 1.0743 |
| ETHUSDT | combo_econ | 290.0000 | 0.3465 | 8.6653 | 6.6638 | 1.1971 |
| ETHUSDT | enet | 290.0000 | 0.2376 | 6.9515 | 4.1545 | 0.8208 |
| ETHUSDT | garch | 290.0000 | 0.3970 | 10.1006 | 7.9630 | 1.3716 |
| ETHUSDT | gjr_garch | 290.0000 | 0.3679 | 9.3457 | 7.2763 | 1.2708 |
| ETHUSDT | har_rv | 290.0000 | 0.2895 | 7.8067 | 5.3209 | 1.0000 |
| ETHUSDT | hist_mean | 290.0000 | 0.4346 | 10.5046 | 7.8125 | 1.5014 |
| ETHUSDT | naive_rw | 290.0000 | 0.4002 | 7.3745 | 4.4661 | 1.3825 |
| ETHUSDT | xgboost | 290.0000 | 0.2688 | 7.4073 | 4.2202 | 0.9285 |


Nguồn: [model_comparison.csv](../outputs/holdout_tables/model_comparison.csv). QLIKE, RMSE, MAE càng thấp càng tốt. RV dùng %².



## 3 Kiểm định so với HAR RV



| symbol | model | n | mean_diff | p_value | p_holm_primary_family | status |
|---|---|---|---|---|---|---|
| BTCUSDT | combo_core4 | 290 | -0.0154 | 0.0018 | 0.0160 | ok |
| BTCUSDT | combo_econ | 290 | 0.0036 | 0.4892 | 1.0000 | ok |
| BTCUSDT | enet | 290 | -0.0393 | 0.0011 | 0.0110 | ok |
| BTCUSDT | garch | 290 | 0.0243 | 0.0057 | 0.0345 | ok |
| BTCUSDT | gjr_garch | 290 | 0.0046 | 0.6231 | 1.0000 | ok |
| BTCUSDT | hist_mean | 290 | 0.1386 | 0.0000 | 0.0000 | ok |
| BTCUSDT | naive_rw | 290 | 0.1299 | 0.0020 | 0.0160 | ok |
| BTCUSDT | xgboost | 290 | -0.0377 | 0.0049 | 0.0344 | ok |
| ETHUSDT | combo_core4 | 290 | 0.0215 | 0.0001 | 0.0009 | ok |
| ETHUSDT | combo_econ | 290 | 0.0570 | 0.0000 | 0.0000 | ok |
| ETHUSDT | enet | 290 | -0.0519 | 0.0430 | 0.2151 | ok |
| ETHUSDT | garch | 290 | 0.1076 | 0.0000 | 0.0000 | ok |
| ETHUSDT | gjr_garch | 290 | 0.0784 | 0.0000 | 0.0000 | ok |
| ETHUSDT | hist_mean | 290 | 0.1451 | 0.0000 | 0.0000 | ok |
| ETHUSDT | naive_rw | 290 | 0.1107 | 0.0685 | 0.2741 | ok |
| ETHUSDT | xgboost | 290 | -0.0207 | 0.6896 | 1.0000 | ok |


Chênh loss = model − HAR, âm có lợi cho model. Holm điều chỉnh chung tất cả so sánh QLIKE rolling h1 của hai coin trong bảng này; các metric/horizon/regime khác là phân tích bổ sung với p danh nghĩa. Không kết luận hai model tương đương chỉ vì p>0.05.



## 4 Đối chiếu evaluation và holdout



| symbol | model | n_evaluation | n_holdout | QLIKE_evaluation | QLIKE_holdout | QLIKE_change_pct |
|---|---|---|---|---|---|---|
| BTCUSDT | combo_core4 | 1667.0000 | 290.0000 | 0.3847 | 0.2516 | -34.5970 |
| BTCUSDT | combo_econ | 1667.0000 | 290.0000 | 0.4066 | 0.2706 | -33.4442 |
| BTCUSDT | enet | 1667.0000 | 290.0000 | 0.3541 | 0.2278 | -35.6741 |
| BTCUSDT | garch | 1667.0000 | 290.0000 | 0.4288 | 0.2913 | -32.0602 |
| BTCUSDT | gjr_garch | 1667.0000 | 290.0000 | 0.4534 | 0.2716 | -40.0988 |
| BTCUSDT | har_rv | 1667.0000 | 290.0000 | 0.3785 | 0.2670 | -29.4548 |
| BTCUSDT | hist_mean | 1667.0000 | 290.0000 | 0.5431 | 0.4056 | -25.3263 |
| BTCUSDT | naive_rw | 1667.0000 | 290.0000 | 0.5381 | 0.3969 | -26.2331 |
| BTCUSDT | xgboost | 1667.0000 | 290.0000 | 0.3747 | 0.2293 | -38.8151 |
| ETHUSDT | combo_core4 | 1667.0000 | 290.0000 | 0.3415 | 0.3110 | -8.9341 |
| ETHUSDT | combo_econ | 1667.0000 | 290.0000 | 0.3651 | 0.3465 | -5.0946 |
| ETHUSDT | enet | 1667.0000 | 290.0000 | 0.3019 | 0.2376 | -21.3043 |
| ETHUSDT | garch | 1667.0000 | 290.0000 | 0.4031 | 0.3970 | -1.4955 |
| ETHUSDT | gjr_garch | 1667.0000 | 290.0000 | 0.4157 | 0.3679 | -11.5024 |
| ETHUSDT | har_rv | 1667.0000 | 290.0000 | 0.3424 | 0.2895 | -15.4660 |
| ETHUSDT | hist_mean | 1667.0000 | 290.0000 | 0.5625 | 0.4346 | -22.7385 |
| ETHUSDT | naive_rw | 1667.0000 | 290.0000 | 0.4377 | 0.4002 | -8.5782 |
| ETHUSDT | xgboost | 1667.0000 | 290.0000 | 0.3391 | 0.2688 | -20.7480 |


Hai giai đoạn có độ dài và điều kiện thị trường khác nhau. Chênh QLIKE giữa hai giai đoạn là mô tả, không phải kiểm định trực tiếp về độ suy giảm. Nguồn: [evaluation_vs_holdout.csv](../outputs/holdout_tables/evaluation_vs_holdout.csv).



## 5 VaR và ES



| coin | model | alpha | n | n_breach | expected_breaches | breach_pct | kupiec_p | christoffersen_p | quantile_loss |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | combo_core4 | 0.0100 | 290 | 4 | 2.9000 | 1.3793 | 0.5393 | 0.7830 | 0.0866 |
| BTCUSDT | combo_core4 | 0.0500 | 290 | 13 | 14.5000 | 4.4828 | 0.6810 | 0.8024 | 0.2484 |
| BTCUSDT | combo_econ | 0.0100 | 290 | 4 | 2.9000 | 1.3793 | 0.5393 | 0.7830 | 0.0891 |
| BTCUSDT | combo_econ | 0.0500 | 290 | 13 | 14.5000 | 4.4828 | 0.6810 | 0.2725 | 0.2490 |
| BTCUSDT | enet | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.0801 |
| BTCUSDT | enet | 0.0500 | 290 | 13 | 14.5000 | 4.4828 | 0.6810 | 0.8024 | 0.2527 |
| BTCUSDT | garch | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.0947 |
| BTCUSDT | garch | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.0507 | 0.2581 |
| BTCUSDT | gjr_garch | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.0858 |
| BTCUSDT | gjr_garch | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.2796 | 0.2510 |
| BTCUSDT | har_rv | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.0860 |
| BTCUSDT | har_rv | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.0507 | 0.2470 |
| BTCUSDT | hist_mean | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.0957 |
| BTCUSDT | hist_mean | 0.0500 | 290 | 11 | 14.5000 | 3.7931 | 0.3255 | 0.4467 | 0.2566 |
| BTCUSDT | naive_rw | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.0777 |
| BTCUSDT | naive_rw | 0.0500 | 290 | 15 | 14.5000 | 5.1724 | 0.8934 | 0.9594 | 0.2666 |
| BTCUSDT | xgboost | 0.0100 | 290 | 4 | 2.9000 | 1.3793 | 0.5393 | 0.7830 | 0.0785 |
| BTCUSDT | xgboost | 0.0500 | 290 | 12 | 14.5000 | 4.1379 | 0.4881 | 0.6326 | 0.2537 |
| ETHUSDT | combo_core4 | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.1051 |
| ETHUSDT | combo_core4 | 0.0500 | 290 | 9 | 14.5000 | 3.1034 | 0.1121 | 0.2119 | 0.3582 |
| ETHUSDT | combo_econ | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.1087 |
| ETHUSDT | combo_econ | 0.0500 | 290 | 9 | 14.5000 | 3.1034 | 0.1121 | 0.2119 | 0.3618 |
| ETHUSDT | enet | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.0889 |
| ETHUSDT | enet | 0.0500 | 290 | 12 | 14.5000 | 4.1379 | 0.4881 | 0.4675 | 0.3477 |
| ETHUSDT | garch | 0.0100 | 290 | 2 | 2.9000 | 0.6897 | 0.5737 | 0.8418 | 0.1192 |
| ETHUSDT | garch | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.3075 | 0.3624 |
| ETHUSDT | gjr_garch | 0.0100 | 290 | 1 | 2.9000 | 0.3448 | 0.1945 | 0.4295 | 0.1098 |
| ETHUSDT | gjr_garch | 0.0500 | 290 | 11 | 14.5000 | 3.7931 | 0.3255 | 0.3990 | 0.3567 |
| ETHUSDT | har_rv | 0.0100 | 290 | 1 | 2.9000 | 0.3448 | 0.1945 | 0.4295 | 0.0957 |
| ETHUSDT | har_rv | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.2796 | 0.3483 |
| ETHUSDT | hist_mean | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.1256 |
| ETHUSDT | hist_mean | 0.0500 | 290 | 8 | 14.5000 | 2.7586 | 0.0565 | 0.0721 | 0.3659 |
| ETHUSDT | naive_rw | 0.0100 | 290 | 1 | 2.9000 | 0.3448 | 0.1945 | 0.4295 | 0.1060 |
| ETHUSDT | naive_rw | 0.0500 | 290 | 16 | 14.5000 | 5.5172 | 0.6908 | 0.3615 | 0.3398 |
| ETHUSDT | xgboost | 0.0100 | 290 | 3 | 2.9000 | 1.0345 | 0.9532 | 0.9674 | 0.0962 |
| ETHUSDT | xgboost | 0.0500 | 290 | 10 | 14.5000 | 3.4483 | 0.2001 | 0.3075 | 0.3510 |


VaR/ES dùng % log return; breach khi return < VaR. FHS kế thừa residual ngoài mẫu 2021–2025, rồi bổ sung residual 2026 chỉ khi đã quan sát; không khởi tạo lại pool ở đầu năm.

Kupiec và Christoffersen chỉ kiểm tra VaR coverage. ES chưa có kiểm định hiệu chuẩn riêng. Với tối đa 290 ngày, kỳ vọng chỉ 2,9 vi phạm ở 99% và 14,5 ở 95%; dùng số ngày thực tế trong bảng. Các p-value rủi ro là danh nghĩa, mẫu ngắn có công suất kiểm định hạn chế; không diễn giải p cao là chứng minh model đúng.

Các stress window 2020–2022 trong file crisis_breaches được đánh dấu ngoài mẫu holdout. Không chọn sự kiện mới năm 2026 sau khi nhìn kết quả.



## 6 Kết quả bổ sung và hình



- [Expanding và h7](../outputs/holdout_tables/model_comparison.csv): lọc window/horizon; target h7 phải nằm trọn trong holdout và đã quan sát đủ.

- [Regime](../outputs/holdout_tables/regime_performance.csv), [số ngày mỗi regime](../outputs/holdout_tables/regime_counts.csv): regime biết tại origin, ngưỡng giữ từ warmup; nhóm ít ngày chỉ diễn giải mô tả.

- [Volume ablation](../outputs/holdout_tables/backend3_volume_ablation.csv), [SHAP](../outputs/holdout_tables/backend3_shap_importance.csv). Macro sensitivity mới năm 2026 không nằm trong lượt chấm chính.

- [Coverage RV](../outputs/holdout_tables/forecast_coverage.csv), [coverage risk](../outputs/risk_holdout/coverage.csv). Ngày thiếu giữ trạng thái, không thay bằng rủi ro bằng 0.

- [Chiến lược có phí](../outputs/risk_holdout/volatility_targeting.csv): mục bổ sung, giữ target 15%/năm, trần tỷ trọng 1, phí 5 bps. Bắt đầu flat ở đầu holdout, tính phí khởi tạo; không nối vốn từ 2025. Chưa có slippage/latency/cash yield.

- Thư mục hình: [holdout_figures](../outputs/holdout_figures), [VaR và ES](../outputs/holdout_figures/risk).



## 7 Kiểm tra và truy vết



Đã đối chiếu 18 file forecast, 20664 hàng dự báo, 20880 hàng rủi ro, 72 hàng backtest và 36 đường vốn. 14 kiểm tra thay đổi residual tương lai không làm đổi dự báo quá khứ.

Toàn bộ giá trị VaR/ES đã được tính lại để đối chiếu; lịch dự báo, cutoff, pool FHS, breach, cùng mẫu, hash nguồn và đường vốn được kiểm tra. Kết quả evaluation cũ giữ nguyên theo hash đã đóng băng.

- [Kế hoạch khóa trước lượt chấm](../outputs/holdout_plan.json)

- [Kiểm tra holdout](../outputs/holdout_verification.json)

- [Trạng thái toàn pipeline](../outputs/final_holdout_pipeline.json)

- [Manifest rủi ro](../outputs/risk_holdout/run_manifest.json)



## 8 Cách sử dụng trong luận



Giữ kết quả 2021–2025 trong chương thực nghiệm chính và thêm mục “Đánh giá cuối trên holdout 2026”. Trình bày cả trường hợp mô hình giữ được lợi thế và mất lợi thế. Báo cáo p-value, số ngày, phạm vi thời gian và giới hạn ES; không tuyên bố mô hình chắc chắn thắng trong tương lai.

# Backend 3 — Elastic Net, XGBoost và giải thích dự báo

## Phạm vi và cách chạy

Phần bắt buộc: Elastic Net dự báo log RV, XGBoost, SHAP, ablation volume và tổ hợp cùng HAR/GARCH/GJR. Theo lựa chọn của Huân, chưa làm GRU tùy chọn. Không tạo chương báo cáo học thuật. VaR/ES và backtesting risk thuộc Backend 4.

Nhánh này kế thừa dataset, quy định và dự báo Backend 2. Dùng Python 3.12, mở terminal ở gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.backend3
```

Luồng: xác minh dataset và đầu ra Backend 2 → chọn/reuse cấu hình warmup → ML walk-forward → ablation và tổ hợp → đánh giá chung → SHAP và kiểm tra bàn giao. Lệnh mặc định chỉ chạy evaluation 2021–2025. Không chạy lại GARCH/GJR.

## Những file cần nhận

| File/thư mục | Công dụng |
|---|---|
| `config/backend3.toml` | Feature, seed, lưới tune và quy tắc chuyển log về RV |
| `outputs/model_selection/backend3_locked.json` | Cấu hình được chọn, thời gian và fingerprint warmup; lưu cố định |
| `outputs/model_selection/backend3_tuning_scores.csv` | Điểm QLIKE trên validation cho tất cả cấu hình đã thử |
| `outputs/forecasts/{symbol}_enet.parquet`, `{symbol}_xgboost.parquet` | Dự báo ML chính, cả h1/h7 và rolling/expanding |
| `outputs/forecasts/{symbol}_combo_core4.parquet` | Trung bình đều phương sai HAR/GARCH/GJR/XGBoost |
| `outputs/volatility/` | σ và quy ước mean=0 cho ML, bàn giao cho FHS ở Backend 4 |
| `outputs/ablation/forecasts/` | Dự báo biến thể không volume, tách khỏi so sánh model chính |
| `outputs/diagnostics/backend3/fit_diagnostics.csv` | Số dòng, hash dòng train, hệ số/scaler Elastic Net, smearing và trạng thái từng fit |
| `outputs/diagnostics/backend3/oos_shap.parquet` | TreeSHAP tại từng origin dự báo XGBoost thành công |
| `outputs/diagnostics/backend3/oos_standardized_residuals.parquet` | Residual ngoài mẫu với thời điểm được phép quan sát |
| `outputs/diagnostics/backend3/validation.json` | Kiểm tra hash, forecast, σ, ablation và SHAP |
| `outputs/tables/backend3_volume_ablation.csv` | QLIKE/RMSE/MAE và DM-HLN khi thêm/bỏ volume |
| `outputs/tables/backend3_scope_status.csv` | Trạng thái volume, VIX/USD và GRU |
| `outputs/tables/backend3_shap_importance.csv` | Mean absolute SHAP, theo coin/window/horizon |
| `outputs/figures/backend3_*` | SHAP và ablation; các hình so sánh chung giữ prefix backend1 |

Tên model thống nhất: `enet`, `xgboost`, `combo_core4`. `combo_econ` ba thành phần từ Backend 2 vẫn được giữ như một kết quả riêng. Các biến thể `enet_core`, `xgboost_core` chỉ thuộc ablation. Không lưu hai tên `xgb` và `xgboost` cho cùng một mô hình trong thư mục dự báo chính.

## Warmup, tuning và chống leakage

- Train tuning: target từ đầu 2019 đến 30/06/2020. Validation: toàn bộ target nằm trong 01/07–31/12/2020. Nhãn h7 phải kết thúc trong phần tương ứng; không trộn target sang 2021.
- Với điều kiện dữ liệu hiện tại, mỗi coin có 347 dòng train h1 và 305 dòng train h7; validation có 132/126 dòng. Ngày hợp lệ thực tế nhỏ hơn khoảng thiết kế và được ghi trong manifest. Warmup tuning yêu cầu tối thiểu 300 dòng; walk-forward evaluation vẫn dùng tối thiểu 365 dòng theo khung chung.
- Tuning dùng một lần fit trước validation và chọn cấu hình theo QLIKE trên variance đã chuyển về mức. Không shuffle, không cross-validation ngẫu nhiên, không dùng evaluation hay holdout chọn cấu hình. Đây là split validation cố định; không phải mô phỏng refit 5 ngày trong giai đoạn tune.
- Elastic Net thử alpha và l1_ratio; XGBoost thử depth, learning rate và số boosting rounds. Lưới, seed và các tham số còn lại được ghi trong cấu hình. Không early-stop hay chọn số cây bằng loss evaluation.
- Manifest được reuse nếu hash và fingerprint khớp; thay nguồn/cấu hình thì báo lỗi. Không xóa manifest rồi tune lại sau khi xem test. Quyết định nghiên cứu mới cần được quản lý thành một phiên bản/thí nghiệm mới và giữ nguyên holdout.
- Evaluation dùng cùng lịch rolling 730 ngày, expanding sensitivity, refit 5 ngày và h1/h7 của nhóm. Giữa các refit, ML dùng feature mới với estimator/scaler đang giữ nguyên.
- Scaler Elastic Net chỉ fit trên predictors của train hiện tại. XGBoost dùng cây và không cần scaler. Dữ liệu thiếu không được điền để tăng số mẫu. Cả hai dự báo trực tiếp log RV h1 hoặc log tổng RV h7.

## Feature và chuyển log về phương sai

Core gồm `log_rv_d`, `log_rv_w`, `log_rv_m`, `log_park`, `ret_d`. Bản chính thêm `log_qv`, `log_turn_rel`. `log_turn_rel` là proxy khối lượng tương đối, không phải turnover theo vốn hóa.

Estimator học log RV. Tại mỗi fit, tính smearing factor bằng trung bình `exp(log(y_train) - fitted_log_train)`. Đầu ra variance là `exp(predicted_log) * smearing_factor`, đơn vị %²; σ là căn của variance. Không nhân thêm 100 hoặc 10.000. Floor 1e-10 là quy tắc số cố định. Lỗi số/fit thất bại ghi status và NaN, không có model thay thế ngầm.

Smearing dùng residual trong train nên không leakage. Nó là một hiệu chỉnh dựa trên giả định về residual, không bảo đảm dự báo conditional mean không chệch khi phân phối sai số thay đổi theo feature hoặc có overfitting. Không chọn lại cách hiệu chỉnh dựa trên điểm evaluation.

## Ablation RQ2

So sánh bản chính với bản core bỏ hai biến volume. Hai bản có **cùng tham số đã chọn, cùng lịch, cùng tập dòng train và cùng mẫu test khi chấm cặp**. Trong code, `features` khai báo tập điều kiện đủ dữ liệu, còn `predictors` là các cột thực sự đi vào estimator; bản core dùng điều kiện đủ dữ liệu như bản chính nhưng không học từ giá trị volume. Hash dòng train được đối chiếu tự động.

`QLIKE_full_minus_core < 0` nghĩa là thêm volume có loss thấp hơn trên mẫu cặp đó. DM-HLN là kiểm tra loss cặp theo ngày lịch, không chứng minh quan hệ nhân quả và không được dùng để tune lại. Nếu fit một bản thất bại thì điểm cặp dùng những ngày cả hai thành công; coverage cần được đọc kèm.

**VIX/USD chưa được chạy ablation.** Data backend mới có calendar mô tả và chưa xác minh release/vintage lịch sử. Theo GROUP_PROTOCOL, macro bị loại khỏi model chính và chỉ chạy sensitivity sau khi xác minh point-in-time. Bảng scope ghi `blocked_unverified_point_in_time`; không tạo kết quả giả hoặc coi lag một ngày là đủ xác minh. Do đó hiện chỉ trả lời phần incremental predictive power của volume, chưa trả lời đầy đủ RQ2 với macro.

## SHAP

Dùng exact TreeSHAP tích hợp trong XGBoost (`pred_contribs=True`, `approx_contribs=False`), không lấy gain importance thay SHAP. Mỗi origin được giải thích bằng chính estimator của refit đang dùng tại origin đó. Tổng contribution và base value phải khớp raw log prediction. Smearing là dịch chuyển intercept riêng sau đó; SHAP trên hình giải thích raw log RV, không phải đơn vị %² hoặc một quan hệ nhân quả.

Hình tổng hợp là thống kê các local explanations từ nhiều estimator walk-forward. Màu feature percentile chỉ dùng mô tả hình sau dự báo, không được đưa vào quá trình train. Bảng SHAP không chứa target tương lai làm input.

## Bàn giao và giới hạn

Snapshot evaluation đã kiểm tra: 47 tests qua; 11.680 fit cho hai model và hai biến thể feature, không có lỗi fit; 13.360 local SHAP explanations. Độ lệch tái tạo raw log prediction tối đa 5,67×10⁻⁶. Validator xác nhận đủ lịch dự báo, đơn vị σ²=variance, cùng dòng train khi ablation và nguyên trạng đầu vào Backend 2. Chi tiết máy đọc ở validation.json; đây là kiểm tra kỹ thuật, chưa thay review độc lập.

Đọc `docs/forecast_format.md` khi thêm model và `docs/GROUP_PROTOCOL.md` để giữ quy tắc nghiên cứu. ML xuất mean=0 theo quy ước FHS; không khẳng định return có phân phối Student-t. Residual ngoài mẫu chỉ dùng được sau `observable_at`; không dùng toàn bộ residual 2021–2025 làm pool cho mọi origin.

Chỉ tạo lại bảng/hình từ các dự báo đã có:

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.aggregate
.\.venv\Scripts\python.exe -m src.models.ml_analysis
```

Holdout 2026 chưa chạy trong bàn giao mặc định. `--final-holdout` chỉ dùng trong lượt tích hợp cuối khi các model đã khóa và đã có các file holdout từ backend trước; nó có lock riêng. Review độc lập của thành viên nhóm vẫn là `pending_team_review`. Tests và validation kỹ thuật không chứng minh mô hình vượt benchmark hay risk calibration tốt.

Nguồn triển khai: [Elastic Net](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html), [scikit-learn leakage](https://scikit-learn.org/stable/common_pitfalls.html), [XGBoost prediction và SHAP](https://xgboost.readthedocs.io/en/stable/python/python_api.html), [XGBoost prediction conventions](https://xgboost.readthedocs.io/en/stable/prediction.html).

"""python -m src.evaluation.make_report -> paper/chapter5_results.md
Số liệu, bảng, câu mô tả định lượng được SINH TỰ ĐỘNG từ outputs/tables => chạy lại là cập nhật.
Các mục [TODO-NHÓM] là phần diễn giải kinh tế cần người viết, không tự sinh.
"""
import json
import pandas as pd

from src.utils.config import load_config, ROOT

T = ROOT / "outputs/tables"


def md(df, floatfmt=".3f"):
    return df.to_markdown(index=False, floatfmt=floatfmt)


def best_lines(comp, bench):
    out = []
    for (a, h), g in comp.groupby(["asset", "horizon"]):
        q = g.loc[g["QLIKE"].idxmin()]
        r = g.loc[g["RMSE"].idxmin()]
        s = (f"- **{a}, h={h}**: QLIKE thấp nhất là `{q['model']}` ({q['QLIKE']:.4f}, bằng {q['QLIKE_rel']:.2f}× {bench}); "
             f"RMSE thấp nhất là `{r['model']}` ({r['RMSE']:.3f}, bằng {r['RMSE_rel']:.3f}× {bench}).")
        out.append(s)
    return "\n".join(out)


def main():
    cfg = load_config()
    ev, bench = cfg["evaluation"], cfg["evaluation"]["benchmark"]
    meta = json.loads((ROOT / "data/processed/dataset_meta.json").read_text())
    comp = pd.read_csv(T / "model_comparison.csv")
    dm = pd.read_csv(T / "dm_vs_benchmark.csv")
    reg = pd.read_csv(T / "regime_performance.csv")
    cnt = pd.read_csv(T / "regime_counts.csv")
    r = cfg["regimes"]

    banner = ""
    if meta["data_source"] != "binance":
        banner = ("> **CẢNH BÁO – KẾT QUẢ TRÊN DỮ LIỆU MÔ PHỎNG (`data_source = %s`).** Mọi con số/hình dưới đây chỉ kiểm tra "
                  "pipeline, KHÔNG phản ánh thị trường BTC/ETH thật. Chạy lại toàn bộ pipeline trên dữ liệu Binance rồi sinh lại chương này "
                  "(`make report`) trước khi nộp.\n\n" % meta["data_source"])

    c = comp.copy()
    c["n"] = c["n"].astype(int)
    t_main = md(c[["asset", "horizon", "model", "RMSE", "MAE", "QLIKE", "RMSE_rel", "MAE_rel", "QLIKE_rel", "n"]]
                .rename(columns={"RMSE_rel": f"RMSE/{bench}", "MAE_rel": f"MAE/{bench}", "QLIKE_rel": f"QLIKE/{bench}"}))
    d = dm.copy()
    for k in ("qlike", "se"):
        d[f"DM({k.upper()})"] = d[f"DM_{k}"].map("{:.2f}".format) + d[f"sig_{k}"].fillna("")
    t_dm = md(d[["asset", "horizon", "model", "DM(QLIKE)", "DM(SE)", "n"]])

    rr = reg[reg.model != bench].copy()
    rr = rr[rr.regime.isin(["normal", "bull", "bear", "crisis"])]
    rr["DM(QLIKE)"] = rr["DM_qlike"].map("{:.2f}".format) + rr["sig_qlike"].fillna("") if "DM_qlike" in rr else ""
    rr["n"] = rr["n"].astype(int)
    t_reg = md(rr[["asset", "horizon", "regime", "model", "n", "QLIKE", "QLIKE_rel", "DM(QLIKE)"]]
               .rename(columns={"QLIKE_rel": f"QLIKE/{bench}"}))
    cnt_p = cnt.pivot_table(index=["asset", "horizon"], columns="regime", values="n_days", fill_value=0).reset_index()
    t_cnt = md(cnt_p, ".0f")

    figs = "\n\n".join(f"![{a} h={h}](../outputs/figures/forecast_vs_actual_{a}_h{h}.png)\n*Hình: {a}, dự báo vs thực tế, h={h}.*"
                       for a in cfg["assets"] for h in cfg["horizons"])
    figr = "\n\n".join(f"![{a} h={h}](../outputs/figures/regime_qlike_ratio_{a}_h{h}.png)" for a in cfg["assets"] for h in cfg["horizons"])
    figq = "\n\n".join(f"![{a} h={h}](../outputs/figures/rolling_qlike_{a}_h{h}.png)" for a in cfg["assets"] for h in [cfg["horizons"][0]])

    txt = f"""# Chương 5. Kết quả dự báo biến động thực hiện (Realized Volatility)

{banner}## 5.1. Thiết lập đánh giá

**Dữ liệu và biến mục tiêu.** Dữ liệu {', '.join(cfg['assets'])} tần suất 5 phút (UTC), nguồn: `{meta['data_source']}`, giai đoạn
{meta['date_min']} – {meta['date_max']}. Return 5 phút là log return nhân 100; realized variance ngày
$RV_t=\\sum_j r_{{t,j}}^2$ trên {cfg['intraday']['bars_per_day']} khoảng/ngày (ngày có dưới {cfg['intraday']['min_bar_coverage']:.0%}
return hợp lệ bị loại, không backfill). Biến mục tiêu ở horizon $h$ là trung bình $RV_{{t+1}},\\dots,RV_{{t+h}}$
(h = {', '.join(map(str, cfg['horizons']))} ngày); ML dùng log của biến này.

**Biến đầu vào chung (point-in-time).** $RV_t$, trung bình RV {cfg['features']['har_windows']['week']} và {cfg['features']['har_windows']['month']} ngày,
phương sai Parkinson, log return, log turnover (quote volume), VIX và chỉ số USD trễ {cfg['features']['macro_lag_days']} ngày.
Tính đúng đắn point-in-time được kiểm chứng bằng `tests/test_leakage.py` (phá hỏng toàn bộ dữ liệu sau ngày T không làm đổi feature/dự báo tại các ngày ≤ T).

**Quy trình out-of-sample.** Cửa sổ **{ev['scheme']}**, tối thiểu {ev['min_train']} quan sát huấn luyện, refit mỗi {ev['refit_every']} ngày,
mẫu kiểm tra từ {ev['test_start']}. Tại origin $t$ chỉ huấn luyện trên các quan sát $t' \\le t-h$ (nhãn $h$ bước chỉ biết sau $t'+h$).
Mọi mô hình được so sánh trên **cùng tập origin**.

**Thước đo.** RMSE, MAE và QLIKE $=\\frac{{y}}{{\\hat y}}-\\ln\\frac{{y}}{{\\hat y}}-1$ (trên RV level; QLIKE là thước đo chính vì bền với nhiễu
trong proxy RV, Patton 2011). So sánh dự báo bằng kiểm định Diebold–Mariano với hiệu chỉnh Harvey–Leybourne–Newbold; phương sai dài hạn dùng
autocovariance tới lag $h-1$ do dự báo $h$ bước chồng lấn. Benchmark: **{bench}**. Khung được kiểm tra bằng mô hình naive
($\\hat{{RV}}_{{t+h}}=RV_t$), hist-mean và oracle (loss = 0).

## 5.2. Độ chính xác dự báo (RQ1)

{t_main}

*Giá trị `/{bench}` < 1 nghĩa là tốt hơn benchmark.*

{best_lines(comp, bench)}

### Kiểm định Diebold–Mariano so với {bench}

{t_dm}

*DM < 0: mô hình có loss thấp hơn {bench}; DM > 0: kém hơn. Dấu * / ** / ***: p < 0,10 / 0,05 / 0,01 (hai phía, t(n−1), HLN).*

### Dự báo so với thực tế

{figs}

### QLIKE trượt theo thời gian

{figq}

[TODO-NHÓM] Nhận xét: mô hình ML/DL (khi có) cải thiện so với HAR-RV ở những giai đoạn nào; lợi thế có bền qua thời gian không (rolling QLIKE)?

## 5.3. Phân tích theo regime (RQ3)

**Định nghĩa regime** (point-in-time, tại cuối ngày $t$; tham số trong `config/config.yaml`):
*crisis* nếu RV trung bình 22 ngày vượt phân vị {r['crisis_quantile']:.0%} expanding của chính nó (cần ≥ {r['min_history']} ngày lịch sử);
nếu không, *bear* khi return log {r['trend_window']} ngày ≤ {r['bear_threshold']:.0f}%, *bull* khi ≥ +{r['bull_threshold']:.0f}%, còn lại *normal*.
Ưu tiên crisis > bear > bull > normal. Dự báo được xếp vào regime của **origin**, không phải của ngày được dự báo.

Số ngày kiểm tra theo regime:

{t_cnt}

{t_reg}

*Chỉ báo DM khi regime có ≥ {ev['min_n_dm']} ngày; regime ít quan sát cần đọc thận trọng, và các quan sát trong cùng regime tự tương quan mạnh nên p-value có xu hướng quá lạc quan.*

{figr}

[TODO-NHÓM] Diễn giải kinh tế: vì sao lợi thế/bất lợi của từng mô hình thay đổi giữa các regime (đặc biệt crisis)?

## 5.4. Hạn chế và kiểm tra độ vững

- Proxy RV từ 5 phút chịu nhiễu vi cấu trúc; nên kiểm tra thêm với 15 phút / RV-subsampled.
- Regime là định nghĩa ngưỡng cứng; nên thử ngưỡng khác (sensitivity).
- Dự báo nhiều bước dùng biến mục tiêu trung bình chồng lấn; DM đã hiệu chỉnh nhưng mẫu hiệu dụng nhỏ hơn n.
- Kết quả đo độ chính xác thống kê; ý nghĩa kinh tế (RQ5) và VaR/ES (RQ4) nằm ở các chương sau.
"""
    (ROOT / "paper").mkdir(exist_ok=True)
    (ROOT / "paper/chapter5_results.md").write_text(txt, encoding="utf-8")
    print("wrote paper/chapter5_results.md", len(txt), "chars")


if __name__ == "__main__":
    main()

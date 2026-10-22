"""Create descriptive tables, figures and a self-contained data handoff report."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import tomllib

from .download import ROOT, save_json

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def md_table(headers, rows):
    def cell(x):
        return str(x).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                      "| " + " | ".join(["---"] * len(headers)) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def descriptive(frames):
    records = []
    for symbol, frame in frames.items():
        for segment in ("warmup", "evaluation"):
            subset = frame.loc[frame["sample_segment"].eq(segment)]
            for col, unit in (("close", "USDT"), ("return_daily_pct_qa", "%"),
                              ("rv_reference_pct2", "%²"), ("volatility_reference_pct", "%"),
                              ("quote_volume", "USDT/day")):
                values = subset[col].dropna()
                records.append({"symbol": symbol, "sample_segment": segment, "variable": col, "unit": unit,
                                "n": len(values), "mean": values.mean(), "std": values.std(ddof=1),
                                "min": values.min(), "p01": values.quantile(.01), "median": values.median(),
                                "p99": values.quantile(.99), "max": values.max(), "skew": values.skew(),
                                "excess_kurtosis": values.kurt()})
    result = pd.DataFrame(records)
    result.to_csv(ROOT / "outputs/tables/descriptive_statistics.csv", index=False)
    return result


def make_figures(frames):
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 180, "figure.facecolor": "white"})
    output = ROOT / "outputs/figures"
    colors = {"BTCUSDT": "#1D4ED8", "ETHUSDT": "#B45309"}
    for column, filename, label in (
        ("close", "figure_3_1_prices.png", "Giá đóng cửa (USDT)"),
        ("rv_reference_pct2", "figure_3_2_rv.png", "RV tham chiếu QA (%²)"),
    ):
        fig, axes = plt.subplots(2, 1, figsize=(10, 6.8), sharex=True, layout="constrained")
        for ax, (symbol, frame) in zip(axes, frames.items()):
            selected = frame.loc[frame["sample_segment"].isin(["warmup", "evaluation"])]
            ax.plot(selected["date"], selected[column], color=colors[symbol], linewidth=.8)
            ax.set_title(symbol, loc="left", fontweight="bold")
            ax.set_ylabel(label)
            ax.grid(alpha=.2)
        axes[-1].set_xlabel("Ngày UTC · mẫu mô tả 2019–2025")
        fig.savefig(output / filename)
        plt.close(fig)
    acf_records = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), layout="constrained")
    for ax, (symbol, frame) in zip(axes, frames.items()):
        series = frame.loc[frame["sample_segment"].eq("warmup")].set_index("date")["rv_reference_pct2"]
        valid = series.notna()
        groups = valid.ne(valid.shift(fill_value=False)).cumsum()
        runs = [part for _, part in series.loc[valid].groupby(groups.loc[valid])]
        longest = max(runs, key=len)
        x = longest.to_numpy()
        centered = x - x.mean()
        denominator = centered @ centered
        max_lag = min(30, len(x)-1)
        acf = [1.0] + [float(centered[k:] @ centered[:-k] / denominator) if denominator else np.nan
                       for k in range(1, max_lag+1)]
        ax.vlines(range(max_lag+1), 0, acf, color=colors[symbol], linewidth=1.3)
        ax.plot(range(max_lag+1), acf, "o", color=colors[symbol], markersize=3)
        limit = 1.96 / np.sqrt(len(x))
        ax.axhline(limit, linestyle="--", color="#64748B", linewidth=.7)
        ax.axhline(-limit, linestyle="--", color="#64748B", linewidth=.7)
        ax.axhline(0, color="black", linewidth=.6)
        ax.set_title(f"{symbol} · N={len(x)}", loc="left", fontweight="bold")
        ax.set_xlabel("Độ trễ (ngày lịch)")
        ax.set_ylabel("ACF RV")
        ax.grid(alpha=.15)
        for lag, value in enumerate(acf):
            acf_records.append({"symbol": symbol, "lag_days": lag, "acf": value, "n_contiguous_days": len(x),
                                "segment_start": longest.index[0], "segment_end": longest.index[-1],
                                "method": "longest_contiguous_complete_rv_segment_biased_sample_acf"})
    fig.savefig(output / "figure_3_3_acf_rv.png")
    plt.close(fig)
    pd.DataFrame(acf_records).to_csv(ROOT / "outputs/tables/acf_rv.csv", index=False)
    return acf_records


def dictionary():
    rows = [
        ["symbol", "string", "Mã cặp spot", "BTCUSDT/ETHUSDT"],
        ["open_time", "timestamp UTC", "Đầu nến 5 phút; khóa cùng symbol", "datetime64 UTC, không phải giờ VN"],
        ["open/high/low/close", "float64", "Giá OHLC", "USDT/coin"],
        ["volume", "float64", "Khối lượng giao dịch", "coin"],
        ["quote_volume", "float64", "Khối lượng theo đồng định giá", "USDT; không phải tỷ lệ turnover"],
        ["n_trades", "int64", "Số giao dịch", "count"],
        ["taker_buy_base/quote", "float64", "Khối lượng mua chủ động", "coin / USDT"],
        ["source_file", "string", "Đường dẫn archive gốc", "relative path"],
        ["timestamp_unit", "string", "Đơn vị timestamp gốc đã nhận diện", "ms/us"],
        ["quality_flag", "string", "ok hoặc cờ cần xem xét", "Không đồng nghĩa đã xác minh nguyên nhân"],
        ["zero_volume", "bool", "Nến volume bằng 0; giữ và gắn cờ", "Không tự xóa"],
        ["return_5m_pct_qa", "float64", "100*ln(close/close trước), chỉ khi cách đúng 5 phút", "% log return; NaN sau khoảng thiếu"],
        ["return_gap_before", "bool", "Không có nến liền trước cách đúng 5 phút", "Bao gồm quan sát đầu snapshot"],
        ["large_return_review", "bool", "|return 5 phút| > 10%", "Cờ xem xét, không tự winsorize"],
        ["eligible_rv", "bool", "Đủ 288 nến hợp lệ và 288 return liền nhau", "Baseline RV đầy đủ"],
        ["rv_reference_pct2", "float64", "Tổng bình phương 288 return 5 phút hợp lệ", "%²; chỉ là tham chiếu QA"],
        ["volatility_reference_pct", "float64", "Căn RV tham chiếu", "%/ngày; không annualize"],
        ["return_daily_pct_qa", "float64", "100*ln(close cuối ngày/close cuối ngày trước)", "% log return; giữ lưới ngày"],
        ["sample_segment", "string", "pre_sample / warmup / evaluation / holdout", "12/2018 / 2019–2020 / 2021–2025 / 2026; theo ngày quan sát"],
        ["quarantine_reason", "string", "Lý do loại khỏi nến sạch", "Raw vẫn giữ nguyên"],
        ["observation_date", "timestamp UTC", "Ngày quan sát FRED", "Không phải ngày công bố"],
        ["available_at", "timestamp UTC", "Thời điểm lịch sử có thể dùng", "Để NaT khi chưa xác minh; không dùng predict"],
        ["retrieved_at_utc", "timestamp UTC", "Thời điểm tải snapshot", "Không gán thay cho historical availability"],
        ["descriptive_ffill_value", "float64", "Giá trị lấp tiếp theo ngày quan sát", "CHỈ MÔ TẢ; predictive_use_allowed=False"],
    ]
    text = "# Từ điển dữ liệu bàn giao của Huân\n\n"
    text += "Schema nến sạch dùng chung ở data/interim. Raw ZIP là bản nguồn nguyên gốc; raw Parquet tổng hợp giữ token gốc dưới dạng chuỗi để tránh làm tròn và giữ dấu vết. Nhãn giai đoạn đã theo quy định nhóm trong config/data.toml; dataset có feature/target sẽ được xây ở bước sau.\n\n"
    text += md_table(["Cột", "Kiểu", "Định nghĩa", "Đơn vị / lưu ý"], rows)
    text += "\n\nRV được tính bằng return đã nhân 100, nên phương sai có đơn vị %². Không so với variance từ return dạng số thập phân nếu chưa đổi đơn vị. Ngày chứa nến mở 00:00–23:55 UTC; nến cuối kết thúc tại biên 00:00 ngày sau.\n"
    text += "\nCoinGecko có giá USD tại 00:00 UTC, được ghép với close Binance của NGÀY TRƯỚC; bỏ điểm cập nhật intraday cuối chuỗi. Chênh lệch còn phản ánh USDT/USD và giá tổng hợp nhiều sàn.\n"
    (ROOT / "docs/data_dictionary.md").write_text(text, encoding="utf-8")
    return rows


def report():
    summary = json.loads((ROOT / "outputs/tables/data_quality_summary.json").read_text(encoding="utf-8"))
    frames = {x["symbol"]: pd.read_parquet(ROOT / f"data/interim/{x['symbol']}_daily_reference_qa.parquet")
              for x in summary["symbols"]}
    config = tomllib.loads((ROOT / "config/data.toml").read_text(encoding="utf-8"))
    study = config["study"]
    regime = study["regime"]
    agreement_rows = [
        ["Cửa sổ", f"{study['window_days']} ngày lịch; t−729 đến t; giữ ngày thiếu"],
        ["Refit", f"Mỗi {study['refit_every_days']} ngày lịch; neo ngày dự báo {study['refit_anchor_target_date']}; dự báo hằng ngày"],
        ["Target 7 ngày", "Tổng RV(t+1)...RV(t+7), %²; yêu cầu đủ 7 RV; chỉ fit target đã quan sát đầy đủ"],
        ["Crisis", f"Phân vị {regime['crisis_quantile']:.0%} của RV trung bình {regime['rv_average_days']} ngày; hiệu chuẩn warmup riêng coin rồi cố định; chỉ dùng thông tin đến origin"],
    ]
    period_rows = [dict(symbol=item["symbol"], **row)
                   for item in summary["symbols"] for row in item["daily_quality_by_segment"]]
    pd.DataFrame(period_rows).to_csv(ROOT / "outputs/tables/sample_period_summary.csv", index=False)
    stats = descriptive(frames)
    acf = make_figures(frames)
    fields = dictionary()
    symbol_rows = [[x["symbol"], f"{x['raw_rows']:,}", f"{x['clean_rows']:,}", x["quarantined_rows"],
                    x["incomplete_days"], f"{x['missing_bars']:,}", x["zero_volume_bars"], x["large_return_bars"]]
                   for x in summary["symbols"]]
    source_log = pd.read_csv(ROOT / "docs/source_log.csv")
    audit_path = ROOT / "outputs/tables/source_audit_summary.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else None
    verified = (source_log["checksum_status"].eq("verified") & ~source_log["dataset_id"].astype(str).str.startswith("audit_")).sum()
    verified_total = source_log["checksum_status"].eq("verified").sum()
    comparison_rows = [[x["symbol"], x.get("matched_days", 0),
                        f"{x.get('median_absolute_difference_pct', float('nan')):.4f}%",
                        f"{x.get('max_absolute_difference_pct', float('nan')):.4f}%",
                        x.get("days_above_review_threshold", 0)] for x in summary["crosscheck"]]
    macro_rows = [[x["series_id"], x.get("rows", 0), x.get("nonmissing_values", 0),
                   x.get("last_observation_with_value", "unavailable")] for x in summary["macro"]]
    md = "# Báo cáo chất lượng dữ liệu và bàn giao thống nhất\n\n"
    md += f"Người chuẩn bị: Huân. Snapshot {summary['snapshot_id']}; tạo báo cáo {summary['generated_at_utc']}.\n\n"
    md += "## Phạm vi và tình trạng\n\nBTCUSDT và ETHUSDT spot 5 phút, 01/12/2018–17/10/2026 UTC. Tháng 12/2018 là dữ liệu đệm (pre_sample); warmup 2019–2020; đánh giá 2021–2025; holdout 2026. Snapshot hiện chỉ đến 17/10/2026. Các thống kê giá/return/RV và hình mô tả không dùng holdout; kiểm tra chất lượng nguồn vẫn bao phủ toàn bộ snapshot. Đã tải VIXCLS, DTWEXBGS và giá CoinGecko trong phạm vi 365 ngày được API cung cấp. Không thu thập order-book/phái sinh và không chạy mô hình.\n\n"
    md += f"Archive Binance đã khớp SHA256 từ nguồn: **{verified}**. Số nguồn/file tải lỗi: **{len(summary['download_failures'])}**. Mỗi archive có URL, thời điểm tải, hash và row count trong source_log.csv.\n\n"
    md += "## Kết quả kiểm tra nến\n\n" + md_table(["Coin", "Raw rows", "Clean rows", "Quarantine", "Ngày thiếu", "Nến thiếu", "Volume 0", "Return >10%"], symbol_rows)
    md += "\n\nNgày đủ nến nhưng thiếu close liền trước cũng không đủ điều kiện RV; kiểm tra eligible_rv trong daily_quality. Các ngày thiếu được giữ trên lưới ngày; RV tham chiếu để NaN. Không ghép return qua khoảng trống, không nội suy hoặc backfill. Nến zero-volume và return lớn được giữ, gắn cờ và có bảng riêng; cờ không khẳng định đó là lỗi dữ liệu.\n\n"
    if audit:
        md += f"Đối chiếu bổ sung: {audit['archives_ok']}/{audit['archives_requested']} archive tải/khớp checksum; {audit['gap_days_matching_daily_source']}/{audit['gap_days_checked']} ngày thiếu trùng khớp giữa monthly và daily; {audit['large_return_bars_ohlc_confirmed']}/{audit['large_return_bars_checked']} nến return lớn có OHLC khớp tổng hợp từ 5 nến 1 phút cùng sàn. Đây là đối chiếu hai độ phân giải của cùng nguồn, không phải xác minh độc lập toàn thị trường. Chi tiết tại gap_source_audit.csv và large_return_source_audit.csv.\n\n"
        md += f"Có {audit.get('gap_days_daily_subset_monthly_priority', 0)} trường hợp daily là tập con của monthly: bảng gap_source_audit ghi các timestamp khác biệt. Giữ monthly làm nguồn chính, không bỏ nến monthly chỉ vì daily thiếu hơn; cả ngày vẫn được đánh dấu không đủ điều kiện RV. Các OHLC ở timestamp chung được đối chiếu riêng.\n\n"
        unresolved = [x for x in audit.get("gap_archive_disagreements", []) if x["status"] == "archive_disagreement_review"]
        if unresolved:
            md += f"**Còn {len(unresolved)} trường hợp archive khác biệt chưa xác định nguyên nhân**, gồm " + "; ".join(f"{x['symbol']} ngày {str(x['date'])[:10]}" for x in unresolved) + f". Giữ monthly làm nguồn chính; {audit.get('shared_bar_ohlc_disagreement_count', 0)} nến có OHLC khác nhau được ghi ở gap_archive_ohlc_differences.csv. Không kết luận dữ liệu hai archive đồng nhất; ngày này đã bị loại khỏi RV baseline do thiếu nến.\n\n"
    md += "## Đối chiếu CoinGecko\n\n" + md_table(["Coin", "Ngày khớp", "Median lệch tuyệt đối", "Max lệch tuyệt đối", "Ngày >2%"], comparison_rows)
    md += "\n\nGhép sample CoinGecko 00:00 UTC với close Binance của ngày vừa kết thúc; bỏ điểm intraday. USD khác USDT và giá tổng hợp khác giá một sàn, nên không yêu cầu lệch bằng 0. Giới hạn một năm khiến việc đối chiếu không bao phủ toàn mẫu. Chi tiết tại *_coingecko_crosscheck.csv.\n\n"
    if audit:
        md += "Ngày lệch trên 2% đã được đối chiếu thêm với archive Binance 1 ngày. Xem crosscheck_source_audit.csv: nếu close 1d khớp close tổng hợp 5m, ghi nhận chênh lệch giữa nguồn vẫn chưa có kết luận nguyên nhân; giữ giá gốc, không thay giá Binance bằng CoinGecko.\n\n"
    md += "## Dữ liệu vĩ mô và tính khả dụng\n\n" + md_table(["Chuỗi", "Dòng quan sát", "Giá trị không thiếu", "Ngày cuối có giá trị"], macro_rows)
    md += "\n\n**Đã thu thập, chưa đủ xác minh point-in-time để đưa vào feature dự báo.** FRED tải hiện tại có thể chứa sửa đổi; ngày quan sát không phải thời điểm công bố. H.10/USD được công bố theo tuần, vì vậy shift một ngày đơn thuần chưa đủ. Bảng observations để available_at trống và point_in_time_verified=False. Bản calendar forward-fill chỉ dành cho mô tả, tên file DESCRIPTIVE_ONLY và predictive_use_allowed=False; không backfill đầu chuỗi. Khi có lịch release/vintage kiểm chứng được, Châu/Huân mới ghép as-of để làm feature. Theo quy định nhóm, macro bị loại khỏi mô hình chính; chỉ dùng kiểm tra độ nhạy sau khi xác minh release/vintage.\n\n"
    md += "## Bốn quy ước đã thống nhất\n\n" + md_table(["Hạng mục", "Quy ước"], agreement_rows) + "\n\nChi tiết: docs/GROUP_PROTOCOL.md. Mới ghi quy định bàn giao; backend, target 7 ngày và ngưỡng crisis chưa được triển khai.\n\n"
    md += "## Bảng và hình dùng cho chương 3\n\nBảng nguồn: source_log.csv; từ điển biến: docs/data_dictionary.md; thống kê: descriptive_statistics.csv. Hình 3.1 giá và Hình 3.2 RV dùng mẫu mô tả 2019–2025. Hình 3.3 ACF chỉ tính trên đoạn lịch liên tục dài nhất có RV đủ điều kiện trong warmup 2019–2020 của từng coin, không nối qua ngày thiếu; đoạn và N nằm trong acf_rv.csv. Dải ±1.96/sqrt(N) chỉ là tham chiếu xấp xỉ dưới giả định nhiễu trắng. Các hình là kết quả tính từ dữ liệu thật, không phải hình minh họa trong brief.\n\n"
    md += "## Bộ bàn giao và bước tiếp theo\n\nNhận *_5m_clean.parquet, *_daily_quality.parquet, *_quarantine.parquet, QA daily reference, source log, dictionary, bảng thiếu/outlier và báo cáo này. Huân phụ trách tiếp phần chuẩn bị feature của Châu ở bước sau. Giữ ngày thiếu trên lịch, tạo feature đến hết ngày t UTC và target t+1; gán split của dataset mô hình theo target_date bằng cùng cấu hình giai đoạn. QA reference đã có nhãn ngày quan sát, chưa phải dataset feature/target và không có lệnh train. Quy định nhóm: HAR-RV, GARCH(1,1), GJR-GARCH, XGBoost; rolling 730 ngày, expanding để kiểm tra độ nhạy; ước lượng lại mỗi 5 ngày; horizon chính 1 ngày và kiểm tra độ nhạy 7 ngày; chỉ chọn siêu tham số XGBoost trên warmup. Xem docs/GROUP_PROTOCOL.md. Phần Huân còn lại là robustness và chương 3/7 theo tiến độ nhóm, sau khi có output mô hình.\n\n"
    md += "## Nguồn và giới hạn\n\nBinance Public Data: https://github.com/binance/binance-public-data\n\nFRED: https://fred.stlouisfed.org/series/VIXCLS và https://fred.stlouisfed.org/series/DTWEXBGS\n\nFed H.10: https://www.federalreserve.gov/releases/h10/about.htm\n\nCoinGecko API: https://docs.coingecko.com/demo/reference/coins-id-market-chart\n\nSố liệu trong báo cáo do nhóm tính từ các snapshot có hash; không khẳng định lịch sử Binance là toàn thị trường. Outlier chưa có bằng chứng độc lập không bị tự loại. Macro chưa được chứng minh availability/vintage nên bị chặn khỏi predictive core.\n"
    (ROOT / "docs/data_quality_report.md").write_text(md, encoding="utf-8")
    (ROOT / "docs/source_log.md").write_text(
        "# Nhật ký nguồn dữ liệu\n\nBản máy đọc đầy đủ: source_log.csv (mỗi file/nguồn một dòng). "
        f"Snapshot {summary['snapshot_id']}; {len(source_log)} nguồn/file, {verified_total} Binance ZIP gồm phần chính và đối chiếu bổ sung khớp checksum. "
        "Raw archives giữ nguyên, metadata SHA256 và retrieved_at lưu bên cạnh. Raw Parquet là bảng tổng hợp token nguồn, có thể tái tạo từ archive. "
        "Độ phủ, row count, timestamp unit và local_path nằm trong CSV; status unavailable nếu tải thất bại.\n", encoding="utf-8")
    def html_table(headers, rows):
        return "<table><thead><tr>" + "".join(f"<th>{escape(str(x))}</th>" for x in headers) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in row) + "</tr>" for row in rows) + "</tbody></table>"
    content = """<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bàn giao dữ liệu BTC ETH của Huân</title><style>
    body{font-family:'Times New Roman',serif;font-size:13pt;line-height:1.5;max-width:1050px;margin:40px auto;padding:0 24px;color:#172033}p{text-align:justify}h1{font-size:23pt;color:#101828}h2{font-size:17pt;margin-top:30px}table{border-collapse:collapse;width:100%;font-size:11pt;margin:16px 0}td,th{border:1px solid #d9d9d9;padding:8px;text-align:left}th{background:#e9eef5}tbody tr:nth-child(even){background:#f7f9fc}img{width:100%;height:auto}code{font-size:11pt}small{color:#475569}.note{font-weight:bold} @media print{body{margin:0;font-size:13pt}h2{break-after:avoid}img,table{break-inside:avoid}}
    </style><body><h1>Báo cáo dữ liệu và quy định thống nhất</h1>"""
    content += f"<p>Huân · Snapshot {summary['snapshot_id']} · BTCUSDT / ETHUSDT spot 5 phút · UTC</p>"
    content += "<p>Đã tải và chuẩn hóa dữ liệu từ 01/12/2018 đến 17/10/2026. Tháng 12/2018 là dữ liệu đệm; warmup 2019–2020; đánh giá 2021–2025; holdout 2026 hiện đến 17/10/2026. Chưa tạo dataset có feature/target hay chạy mô hình. Báo cáo mô tả giá/return/RV chỉ dùng 2019–2025, thống kê tách warmup và evaluation. Cấu hình thống nhất nằm ở config/data.toml và docs/GROUP_PROTOCOL.md.</p>"
    content += f"<p><b>{verified} archive Binance khớp SHA256; {len(summary['download_failures'])} file/nguồn tải lỗi.</b> Bản gốc và metadata được giữ trong data/raw; dữ liệu sạch trong data/interim.</p>"
    content += "<h2>Bốn quy ước đã thống nhất</h2>" + html_table(["Hạng mục", "Quy ước"], agreement_rows)
    content += "<p>Chi tiết: docs/GROUP_PROTOCOL.md. Bảng này ghi quy định cho bước tiếp theo; chưa có dataset target 7 ngày, ngưỡng crisis hay backend.</p>"
    content += "<h2>1. Chất lượng dữ liệu</h2>" + html_table(["Coin", "Raw", "Clean", "Quarantine", "Ngày thiếu", "Nến thiếu", "Volume 0", "Return >10%"], symbol_rows)
    content += "<p>Ngày thiếu giữ nguyên trên lịch. RV chỉ được tính làm tham chiếu QA khi có đủ 288 nến hợp lệ và 288 return liền nhau. Không nội suy/backfill, không dùng chênh lệch qua khoảng trống như return 5 phút. Các nến cần xem xét vẫn được giữ và gắn cờ, có bảng chi tiết.</p>"
    if audit:
        content += f"<p>Đã đối chiếu thêm {audit['archives_ok']}/{audit['archives_requested']} archive: {audit['gap_days_matching_daily_source']}/{audit['gap_days_checked']} ngày thiếu khớp giữa monthly/daily; {audit['large_return_bars_ohlc_confirmed']}/{audit['large_return_bars_checked']} nến return lớn khớp OHLC tổng hợp từ 5 nến 1 phút cùng sàn. Dữ liệu lớn không bị tự động cắt hoặc winsorize.</p>"
        content += f"<p>{audit.get('gap_days_daily_subset_monthly_priority', 0)} trường hợp daily thiếu hơn monthly, OHLC ở các timestamp chung khớp; giữ monthly làm nguồn chính và ghi timestamp chênh trong gap_source_audit.csv. Những ngày đó vẫn không đủ điều kiện RV.</p>"
        unresolved = [x for x in audit.get("gap_archive_disagreements", []) if x["status"] == "archive_disagreement_review"]
        if unresolved:
            names = "; ".join(f"{x['symbol']} ngày {str(x['date'])[:10]}" for x in unresolved)
            content += f"<p class='note'>Còn khác biệt archive chưa xác định nguyên nhân: {escape(names)}. Giữ monthly làm nguồn chính, lưu chi tiết OHLC khác nhau ở gap_archive_ohlc_differences.csv. Ngày này đã không đủ điều kiện RV vì thiếu nến.</p>"
    content += "<h2>2. Đối chiếu giá độc lập</h2>" + html_table(["Coin", "Ngày khớp", "Median lệch", "Max lệch", "Ngày vượt 2%"], comparison_rows)
    content += "<p>CoinGecko cung cấp phạm vi 365 ngày; đối chiếu không bao phủ toàn lịch sử. Sample 00:00 UTC được ghép với close Binance của ngày trước, bỏ cập nhật intraday. Chênh lệch còn phản ánh USDT/USD và phương pháp giá tổng hợp.</p>"
    if audit:
        content += "<p>Ngày lệch trên 2% được đối chiếu thêm với archive Binance 1 ngày. Chênh lệch giữa nguồn được lưu để xem xét, chưa khẳng định nguyên nhân và không thay giá gốc. Bảng crosscheck_source_audit.csv ghi kết quả cụ thể.</p>"
    content += "<h2>3. Vĩ mô và giới hạn dùng cho dự báo</h2>" + html_table(["Chuỗi", "Dòng", "Giá trị hợp lệ", "Ngày cuối có giá trị"], macro_rows)
    content += "<p class='note'>Theo quy định nhóm, VIX/USD chỉ dành cho kiểm tra độ nhạy, không đưa vào mô hình chính. Hiện chưa xác minh lịch công bố/vintage nên vẫn bị chặn dùng dự báo.</p><p>H.10/USD công bố theo tuần; shift một ngày không bảo đảm đúng thông tin lúc dự báo. File observations để available_at trống. File macro calendar có forward-fill theo ngày quan sát chỉ dành cho mô tả, được gắn DESCRIPTIVE_ONLY và predictive_use_allowed=False.</p>"
    content += "<h2>4. Thống kê mô tả: warmup 2019–2020 và đánh giá 2021–2025</h2>"
    mainstats = stats.loc[stats["sample_segment"].isin(["warmup", "evaluation"]) & stats["variable"].isin(["return_daily_pct_qa", "rv_reference_pct2"])]
    content += html_table(["Coin", "Giai đoạn", "Biến", "N", "Mean", "Std", "Min", "Max"],
                          [[r.symbol, r.sample_segment, r.variable, r.n, f"{r.mean:.4f}", f"{r.std:.4f}", f"{r.min:.4f}", f"{r.max:.4f}"] for r in mainstats.itertuples()])
    for filename, title, note in [
        ("figure_3_1_prices.png", "Hình 3.1 Giá BTC và ETH", "Đơn vị USDT. Giá cuối ngày tại biên UTC."),
        ("figure_3_2_rv.png", "Hình 3.2 RV tham chiếu QA", "Đơn vị %²; RV của ngày không đủ điều kiện để trống, không lấp bằng 0."),
        ("figure_3_3_acf_rv.png", "Hình 3.3 ACF của RV", "Chỉ dùng warmup 2019–2020, trên đoạn ngày liên tục dài nhất có RV hợp lệ mỗi coin; sample cụ thể nằm trong acf_rv.csv. Dải xấp xỉ chỉ là tham chiếu nhiễu trắng."),
    ]:
        encoded = base64.b64encode((ROOT / "outputs/figures" / filename).read_bytes()).decode("ascii")
        content += f"<h2>{title}</h2><img src='data:image/png;base64,{encoded}' alt='{title}'><p><small>Nguồn: tính toán từ snapshot Binance spot của nhóm. {note}</small></p>"
    content += "<h2>5. Bộ bàn giao và bước tiếp theo</h2><p>Huân đã nhận tiếp phần chuẩn bị feature của Châu. Bộ dữ liệu hiện gồm nến sạch, daily quality, daily reference QA và tài liệu; nhãn ngày quan sát đã theo quy định nhóm. Bước tiếp theo mới tạo feature, target t+1 và split theo target_date, kiểm tra leakage, triển khai backend và mô hình theo docs/GROUP_PROTOCOL.md. Báo cáo này chưa có dự báo hay kết quả robustness.</p>"
    content += "<p>Chạy lại: <code>.venv\\Scripts\\python.exe -m src.data.run</code> từ thư mục gốc của repo. README có hướng dẫn môi trường và từng bước. Raw cache được tái sử dụng sau kiểm tra hash.</p>"
    content += "<h2>6. Nguồn</h2><p><a href='https://github.com/binance/binance-public-data'>Binance Public Data</a>; <a href='https://fred.stlouisfed.org/series/VIXCLS'>FRED VIXCLS</a>; <a href='https://fred.stlouisfed.org/series/DTWEXBGS'>FRED DTWEXBGS</a>; <a href='https://www.federalreserve.gov/releases/h10/about.htm'>Fed H.10</a>; <a href='https://docs.coingecko.com/demo/reference/coins-id-market-chart'>CoinGecko Demo API</a>.</p><p><small>Chi tiết kiểm tra và giới hạn: docs/data_quality_report.md. Đây là dữ liệu và tính toán mô tả, chưa có dự báo hoặc kết quả kiểm định mô hình.</small></p></body></html>"
    (ROOT / "outputs/BAN_GIAO_DU_LIEU_HUAN.html").write_text(content, encoding="utf-8")
    print("Report, source log, dictionary, descriptive tables and 3 figures written.", flush=True)


if __name__ == "__main__":
    report()

"""Build the final holdout handoff from verified, saved numbers without refitting."""
import json
import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from src.utils.config import ROOT
from src.final_holdout import PLAN, save, sha

def table(frame):
    def fmt(x):
        if isinstance(x,(float,np.floating)):return f'{x:.4f}' if np.isfinite(x) else '—'
        return str(x)
    return '\n'.join(['| '+' | '.join(frame.columns)+' |','|'+'|'.join(['---']*len(frame.columns))+'|']+
        ['| '+' | '.join(fmt(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None)])+'\n'

def build():
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    verification=json.loads((ROOT/'outputs/holdout_verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='passed'
    folder=ROOT/'outputs/holdout_tables'
    scores=pd.read_csv(folder/'model_comparison.csv')
    old=pd.read_csv(ROOT/'outputs/tables/model_comparison.csv')
    dm=pd.read_csv(folder/'dm_vs_benchmark.csv')
    main=lambda d:d.loc[d.window.eq('rolling')&d.horizon_days.eq(1)].copy()
    primary=main(scores);tests=main(dm);tests=tests.loc[tests.loss.eq('qlike')].copy()
    finite=np.isfinite(tests.p_value)
    tests['p_holm_primary_family']=np.nan
    tests.loc[finite,'p_holm_primary_family']=multipletests(tests.loc[finite,'p_value'],method='holm')[1]
    tests.to_csv(folder/'primary_dm_holm.csv',index=False)
    comparison=main(old).merge(primary,on=['symbol','model','horizon_days','window'],suffixes=('_evaluation','_holdout'),validate='one_to_one')
    comparison['QLIKE_change_pct']=100*(comparison.QLIKE_holdout/comparison.QLIKE_evaluation-1)
    comparison.to_csv(folder/'evaluation_vs_holdout.csv',index=False)
    risk=pd.read_csv(ROOT/'outputs/risk_holdout/backtest.csv');risk=risk.loc[risk.window.eq('rolling')].copy()
    risk['expected_breaches']=risk.n*risk.alpha
    risk['breach_pct']=100*risk.breach_rate
    risk.to_csv(folder/'risk_primary_with_expected_breaches.csv',index=False)
    lines=['# Kết quả đánh giá cuối trên holdout 2026','',
        f"Phạm vi **{plan['start']} đến {plan['end']} UTC**, BTCUSDT và ETHUSDT. Đây là mẫu một phần năm 2026, không đại diện cho trọn năm.",
        'Thiết kế và siêu tham số đã khóa trước lượt chấm này. Mô hình được refit theo lịch 5 ngày với dữ liệu đã quan sát; không chọn lại siêu tham số. Dữ liệu 2026 từng được xem cho QA và mô tả trước đây, không gọi là dữ liệu chưa từng được nhìn thấy.',
        '', '## 1 Kết luận từ cấu hình chính','']
    for coin,part in primary.groupby('symbol'):
        ranked=part.sort_values('QLIKE');best=ranked.iloc[0];har=part.loc[part.model.eq('har_rv')].iloc[0]
        gain=100*(1-best.QLIKE/har.QLIKE)
        row=tests.loc[tests.symbol.eq(coin)&tests.model.eq(best.model)]
        suffix='HAR-RV cũng đứng đầu theo QLIKE.' if row.empty else (
            f"DM QLIKE so với HAR: p={row.p_value.iloc[0]:.4f}, p Holm={row.p_holm_primary_family.iloc[0]:.4f}. "
            +('Có bằng chứng khác biệt sau điều chỉnh trong họ kiểm định chính.' if row.p_holm_primary_family.iloc[0]<.05 else 'Chưa đủ bằng chứng khác biệt ở mức 5% sau điều chỉnh.'))
        lines += [f"- **{coin}:** {best.model} có QLIKE thấp nhất {best.QLIKE:.4f}; HAR-RV {har.QLIKE:.4f}; mức giảm {gain:.2f}%, trên {int(best.n)} ngày chung. {suffix}"]
    lines += ['', 'Thứ hạng theo điểm là mô tả kết quả holdout. Không dùng bảng này để sửa thiết kế rồi chấm lại cùng mẫu.',
        '', '## 2 Dự báo variance trên cùng mẫu','',
        table(primary[['symbol','model','n','QLIKE','RMSE','MAE','QLIKE_relative_to_har']]),
        'Nguồn: [model_comparison.csv](../outputs/holdout_tables/model_comparison.csv). QLIKE, RMSE, MAE càng thấp càng tốt. RV dùng %².',
        '', '## 3 Kiểm định so với HAR RV','',
        table(tests[['symbol','model','n','mean_diff','p_value','p_holm_primary_family','status']]),
        'Chênh loss = model − HAR, âm có lợi cho model. Holm điều chỉnh chung tất cả so sánh QLIKE rolling h1 của hai coin trong bảng này; các metric/horizon/regime khác là phân tích bổ sung với p danh nghĩa. Không kết luận hai model tương đương chỉ vì p>0.05.',
        '', '## 4 Đối chiếu evaluation và holdout','',
        table(comparison[['symbol','model','n_evaluation','n_holdout','QLIKE_evaluation','QLIKE_holdout','QLIKE_change_pct']]),
        'Hai giai đoạn có độ dài và điều kiện thị trường khác nhau. Chênh QLIKE giữa hai giai đoạn là mô tả, không phải kiểm định trực tiếp về độ suy giảm. Nguồn: [evaluation_vs_holdout.csv](../outputs/holdout_tables/evaluation_vs_holdout.csv).',
        '', '## 5 VaR và ES','',
        table(risk[['coin','model','alpha','n','n_breach','expected_breaches','breach_pct','kupiec_p','christoffersen_p','quantile_loss']]),
        'VaR/ES dùng % log return; breach khi return < VaR. FHS kế thừa residual ngoài mẫu 2021–2025, rồi bổ sung residual 2026 chỉ khi đã quan sát; không khởi tạo lại pool ở đầu năm.',
        'Kupiec và Christoffersen chỉ kiểm tra VaR coverage. ES chưa có kiểm định hiệu chuẩn riêng. Với tối đa 290 ngày, kỳ vọng chỉ 2,9 vi phạm ở 99% và 14,5 ở 95%; dùng số ngày thực tế trong bảng. Các p-value rủi ro là danh nghĩa, mẫu ngắn có công suất kiểm định hạn chế; không diễn giải p cao là chứng minh model đúng.',
        'Các stress window 2020–2022 trong file crisis_breaches được đánh dấu ngoài mẫu holdout. Không chọn sự kiện mới năm 2026 sau khi nhìn kết quả.',
        '', '## 6 Kết quả bổ sung và hình','',
        '- [Expanding và h7](../outputs/holdout_tables/model_comparison.csv): lọc window/horizon; target h7 phải nằm trọn trong holdout và đã quan sát đủ.',
        '- [Regime](../outputs/holdout_tables/regime_performance.csv), [số ngày mỗi regime](../outputs/holdout_tables/regime_counts.csv): regime biết tại origin, ngưỡng giữ từ warmup; nhóm ít ngày chỉ diễn giải mô tả.',
        '- [Volume ablation](../outputs/holdout_tables/backend3_volume_ablation.csv), [SHAP](../outputs/holdout_tables/backend3_shap_importance.csv). Macro sensitivity mới năm 2026 không nằm trong lượt chấm chính.',
        '- [Coverage RV](../outputs/holdout_tables/forecast_coverage.csv), [coverage risk](../outputs/risk_holdout/coverage.csv). Ngày thiếu giữ trạng thái, không thay bằng rủi ro bằng 0.',
        '- [Chiến lược có phí](../outputs/risk_holdout/volatility_targeting.csv): mục bổ sung, giữ target 15%/năm, trần tỷ trọng 1, phí 5 bps. Bắt đầu flat ở đầu holdout, tính phí khởi tạo; không nối vốn từ 2025. Chưa có slippage/latency/cash yield.',
        '- Thư mục hình: [holdout_figures](../outputs/holdout_figures), [VaR và ES](../outputs/holdout_figures/risk).',
        '', '## 7 Kiểm tra và truy vết','',
        f"Đã đối chiếu {verification['forecast_files']} file forecast, {verification['forecast_rows']} hàng dự báo, {verification['risk_rows']} hàng rủi ro, 72 hàng backtest và 36 đường vốn. {verification['future_residual_mutation_checks']} kiểm tra thay đổi residual tương lai không làm đổi dự báo quá khứ.",
        'Toàn bộ giá trị VaR/ES đã được tính lại để đối chiếu; lịch dự báo, cutoff, pool FHS, breach, cùng mẫu, hash nguồn và đường vốn được kiểm tra. Kết quả evaluation cũ giữ nguyên theo hash đã đóng băng.',
        '- [Kế hoạch khóa trước lượt chấm](../outputs/holdout_plan.json)',
        '- [Kiểm tra holdout](../outputs/holdout_verification.json)',
        '- [Trạng thái toàn pipeline](../outputs/final_holdout_pipeline.json)',
        '- [Manifest rủi ro](../outputs/risk_holdout/run_manifest.json)',
        '', '## 8 Cách sử dụng trong luận','',
        'Giữ kết quả 2021–2025 trong chương thực nghiệm chính và thêm mục “Đánh giá cuối trên holdout 2026”. Trình bày cả trường hợp mô hình giữ được lợi thế và mất lợi thế. Báo cáo p-value, số ngày, phạm vi thời gian và giới hạn ES; không tuyên bố mô hình chắc chắn thắng trong tương lai.']
    (ROOT/'docs/HOLDOUT_RESULTS.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    save(ROOT/'outputs/holdout_report_manifest.json',dict(plan_sha256=sha(PLAN),
         report_sha256=sha(ROOT/'docs/HOLDOUT_RESULTS.md'),
         inputs_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in
            [folder/'model_comparison.csv',folder/'dm_vs_benchmark.csv',ROOT/'outputs/tables/model_comparison.csv',
             ROOT/'outputs/risk_holdout/backtest.csv',ROOT/'outputs/holdout_verification.json']}))
    print('Created docs/HOLDOUT_RESULTS.md',flush=True)

if __name__=='__main__':build()

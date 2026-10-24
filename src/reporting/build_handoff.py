"""Build a Vietnamese thesis handoff without fitting models or evaluating holdout."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CORE=('har_rv','garch','gjr_garch','xgboost')
NAMES={'har_rv':'HAR-RV','garch':'GARCH-t','gjr_garch':'GJR-GARCH-t','xgboost':'XGBoost',
       'enet':'Elastic Net','naive_rw':'Naive RV','hist_mean':'Historical mean',
       'combo_econ':'Tổ hợp 3','combo_core4':'Tổ hợp 4'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(root=ROOT,snapshot=None):
    root=Path(root).resolve();used={};hash_modes={}
    def text(rel):
        p=root/rel;content=p.read_text(encoding='utf-8-sig')
        used[rel]=hashlib.sha256(content.encode('utf-8')).hexdigest()
        hash_modes[rel]='UTF-8 text, BOM removed, LF line endings'
        return content
    def js(rel):return json.loads(text(rel))
    def rows(rel):return list(csv.DictReader(text(rel).splitlines()))
    def main(rows):return [r for r in rows if r.get('window')=='rolling' and r.get('horizon_days','1')=='1']
    def num(v,digits=4):
        try:x=float(v)
        except (ValueError,TypeError):return '—'
        return f'{x:.{digits}f}' if math.isfinite(x) else '—'
    def integer(v):return str(int(float(v)))
    def pvalue(v):
        try:x=float(v)
        except (ValueError,TypeError):return '—'
        if not math.isfinite(x):return '—'
        return f'{x:.2e}' if 0<x<.0001 else f'{x:.4f}'
    def pct(v,digits=2):return num(float(v)*100,digits)+'%'
    def table(headers,data):
        clean=lambda x:str(x).replace('|','/').replace('\n',' ')
        return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                         ['| '+' | '.join(clean(x) for x in row)+' |' for row in data])+'\n'
    def src(rel,filters):return f'Nguồn: [{rel}](../{rel}). Bộ lọc: `{filters}`.\n'
    def one(data,**kwargs):
        selected=[r for r in data if all(str(r[k])==str(v) for k,v in kwargs.items())]
        if len(selected)!=1:raise ValueError(f'Expected one row for {kwargs}, got {len(selected)}')
        return selected[0]

    quality=js('outputs/tables/data_quality_summary.json')
    periods=rows('outputs/tables/sample_period_summary.csv')
    desc=rows('outputs/tables/descriptive_statistics.csv')
    metrics=rows('outputs/tables/model_comparison.csv');primary=main(metrics)
    dm=main(rows('outputs/tables/dm_vs_benchmark.csv'))
    coverage=main(rows('outputs/tables/forecast_coverage.csv'))
    regime=main(rows('outputs/tables/regime_performance.csv'))
    volume=main(rows('outputs/tables/backend3_volume_ablation.csv'))
    macro=main(rows('outputs/tables/backend3_macro_ablation.csv'))
    shap=main(rows('outputs/tables/backend3_shap_importance.csv'))
    robust=rows('outputs/tables/robustness.csv')
    risk=[r for r in rows('outputs/risk/backtest.csv') if r['window']=='rolling']
    risk_coverage=[r for r in rows('outputs/risk/coverage.csv') if r['window']=='rolling' and r['alpha']=='0.05']
    crises=[r for r in rows('outputs/risk/crisis_breaches.csv') if r['window']=='rolling' and r['sample']=='common_all_9_models']
    strategy=[r for r in rows('outputs/risk/volatility_targeting.csv') if r['window']=='rolling']
    lock=js('outputs/model_selection/backend3_locked.json')
    thresholds=js('data/processed/regime_thresholds.json')
    b2=js('outputs/diagnostics/backend2_validation.json')
    b3=js('outputs/diagnostics/backend3/validation.json')
    mv=js('outputs/sensitivity/macro/validation.json')
    rm=js('outputs/risk/run_manifest.json')
    rv=js('outputs/risk/verification.json')
    meta=js('data/processed/dataset_meta.json')
    if meta['dataset_sha256']!='2025bf54f52f9bad444c8474cf3df3c7ca434c6884b06017c443d575cbbf4edd':
        raise ValueError('New dataset snapshot: update scope and fixed explanatory text before regenerating this handoff')
    diagnostics=rows('outputs/diagnostics/garch_diagnostic_summary.csv')
    coins=('BTCUSDT','ETHUSDT')
    for coin in coins:
        if len({r['n'] for r in primary if r['symbol']==coin})!=1:raise ValueError('Unequal volatility comparison samples')
        if len({r['n'] for r in risk if r['coin']==coin})!=1:raise ValueError('Unequal risk comparison samples')
        part=[r for r in primary if r['symbol']==coin]
        if min(part,key=lambda r:float(r['QLIKE']))['model']!='enet':
            raise ValueError('QLIKE ranking changed: review explanatory conclusions before publication')
        if float(one(dm,symbol=coin,model='enet',loss='qlike')['p_value'])<.05:
            raise ValueError('DM conclusion changed: update narrative')
    if not all(float(r['dm_p_value'])>.05 and float(r['QLIKE_full_minus_core'])<0 for r in volume):
        raise ValueError('Volume-ablation conclusion changed: update narrative')
    if not all(float(r['kupiec_p'])>.05 and float(r['christoffersen_p'])>.05 for r in risk if r['model'] in CORE):
        raise ValueError('Core-model coverage conclusion changed: update narrative')
    if any(r['holdout_scored'] for r in (b2,b3,mv)) or rm['holdout_evaluated']:
        raise ValueError('This handoff assumes the final holdout has not been scored')
    if sha(root/'data/processed/dataset.parquet')!=meta['dataset_sha256']:raise ValueError('Dataset hash mismatch')

    # Optional JSON intermediate lets a bundled runtime without a Parquet reader author the document.
    if snapshot:
        example=json.loads(Path(snapshot).read_text(encoding='utf-8'))
        for rel,digest in example['source_sha256'].items():
            if sha(root/rel)!=digest:raise ValueError(f'Snapshot source changed: {rel}')
        example_rows=example['rows']
    else:
        import pandas as pd
        example_rows=[]
        for coin in coins:
            for model in CORE+('enet',):
                rel=f'outputs/risk/{coin}_{model}.parquet'
                used[rel]=sha(root/rel);hash_modes[rel]='raw file bytes'
                frame=pd.read_parquet(root/rel)
                part=frame.loc[frame['window'].eq('rolling')&frame['date'].eq(pd.Timestamp('2025-12-31',tz='UTC'))]
                for r in part.to_dict('records'):
                    example_rows.append({k:r[k] for k in ('coin','model','alpha','var','es','return','status')})
    for coin in coins:
        for model in CORE+('enet',):
            rel=f'outputs/risk/{coin}_{model}.parquet';used[rel]=sha(root/rel);hash_modes[rel]='raw file bytes'

    out=[]
    def add(s):out.append(s.strip()+'\n')
    add('''# Bàn giao số liệu và kết quả để viết luận Crypto Tail Risk

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
''')
    for coin in coins:
        e=one(primary,symbol=coin,model='enet');h=one(primary,symbol=coin,model='har_rv')
        d=one(dm,symbol=coin,model='enet',loss='qlike')
        add(f'- **{coin}:** Elastic Net có QLIKE {num(e["QLIKE"])} so với HAR-RV {num(h["QLIKE"])}, '
            f'thấp hơn {num(100*(1-float(e["QLIKE"])/float(h["QLIKE"])),2)}%. '
            f'DM-HLN p={pvalue(d["p_value"])}: chưa đủ bằng chứng vượt HAR ở mức 5% trong bài toán h1/rolling.')
    add('''- **RQ2:** thêm volume làm QLIKE h1 giảm ở cả hai ML/hai coin nhưng DM đều p>0.05.
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
''')
    add('''## 2 Ai viết phần nào thì đọc file nào

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
''')
    add('## 3 Dữ liệu và số quan sát')
    add(table(['Coin','Nến 5 phút sạch','Ngày lịch','Ngày đủ RV','Ngày thiếu nến','Nến thiếu','Nến volume 0','Abs return 5m >10%'],
        [[q['symbol'],q['clean_rows'],q['expected_days'],q['days_eligible_rv'],q['incomplete_days'],q['missing_bars'],q['zero_volume_bars'],q['large_return_bars']] for q in quality['symbols']]))
    add(src('outputs/tables/data_quality_summary.json','symbols; toàn snapshot 2018-12-01 đến 2026-10-17'))
    add('''Tổng hai coin là **1.656.100 nến**, tính cả tháng 12/2018 làm đệm. Riêng từ
01/01/2019 có **819.122 nến/coin**, tổng **1.638.244**. Đây là số hàng 5 phút,
không phải số quan sát dùng trực tiếp cho mô hình daily. Dataset daily có
**5.756 hàng coin-ngày = 2 × 2.878**, gồm cả đệm và holdout.

Binance spot có 288 nến/ngày khi đầy đủ. ZIP là bản phân phối nén của CSV;
pipeline đọc thành raw Parquet, nến sạch và dataset, nên các backend không
đọc ZIP bằng tay. Raw Parquet giữ token nguồn; nến sạch có timestamp UTC và số.
''')
    add(table(['Coin','Giai đoạn','Ngày lịch','Ngày đủ RV','Nến thiếu'],
        [[r['symbol'],r['sample_segment'],r['days'],r['eligible_rv'],r['missing_bars']] for r in periods]))
    add(src('outputs/tables/sample_period_summary.csv','từng coin và sample_segment'))
    add('''### Cách xử lý thiếu và đối chiếu nguồn

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
''')
    add('## 4 Thống kê mô tả dùng trong luận')
    variables={'return_daily_pct_qa':'Return ngày (%)','rv_reference_pct2':'RV ngày (%²)','volatility_reference_pct':'Căn RV (%)'}
    add(table(['Coin','Giai đoạn','Biến','N','Mean','Std','Min','Max','Excess kurtosis'],
        [[r['symbol'],r['sample_segment'],variables[r['variable']],r['n'],num(r['mean']),num(r['std']),num(r['min']),num(r['max']),num(r['excess_kurtosis'],2)]
         for r in desc if r['variable'] in variables and r['sample_segment'] in ('warmup','evaluation')]))
    add(src('outputs/tables/descriptive_statistics.csv','sample_segment=warmup/evaluation; return_daily_pct_qa, rv_reference_pct2, volatility_reference_pct'))
    add('''Return close-to-close có thể tính được khi close cuối ngày vẫn quan sát được,
trong khi RV intraday thiếu. Do đó N return evaluation=1826 nhưng N RV=1819.
Std return ngày không phải trung bình căn RV; mean(sqrt(RV)) không bằng sqrt(mean(RV)).
Đuôi dày ở đây là mô tả phân phối mẫu, không thay cho kiểm định phân phối.
Excess kurtosis lớn và RV lệch phải cho thấy sai số bình phương dễ bị vài ngày
stress chi phối; đọc RMSE cùng QLIKE/MAE, không bỏ các ngày lớn cho điểm tốt hơn.
''')
    add('''## 5 Phương pháp thực tế đã triển khai

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
''')
    params=[]
    for coin,horizons in lock['selected_parameters'].items():
        for h,models in horizons.items():
            e=models['enet'];x=models['xgboost']
            params.append([coin,h,e['alpha'],e['l1_ratio'],x['max_depth'],x['learning_rate'],x['num_boost_round']])
    add(table(['Coin','h','ENet alpha','ENet l1_ratio','XGB depth','Learning rate','Boosting rounds'],params))
    add(src('outputs/model_selection/backend3_locked.json','selected_parameters; khóa từ warmup'))
    add('''Số dòng tuning hợp lệ thực tế mỗi coin: h1 có 347 train và 132 validation;
h7 có 305 và 126. Điều kiện đủ trailing/target làm validation thực tế từ
21/07 đến 29/11/2020; không khẳng định đã dùng đủ mọi ngày của khoảng thiết kế.
Không dùng evaluation chọn lại tham số. Lịch refit evaluation không phải bước
tuning siêu tham số.

Chẩn đoán kinh tế lượng: 2928 fit GARCH/GJR, không có fit thất bại; sai lệch
đệ quy đối chiếu thư viện tối đa 8.53e-14. Hội tụ không đảm bảo đặc tả đúng.
''')
    add(table(['Coin','Model','Window','Fit thành công','Persistence gần 1','ν ≤ 4'],
        [[r['symbol'],NAMES[r['model']],r['window'],r['refits_successful'],r['near_integrated_fits'],r['nu_le_4_fits']] for r in diagnostics]))
    add(src('outputs/diagnostics/garch_diagnostic_summary.csv','tất cả 8 nhóm'))
    add('''ν≤4 nghĩa là innovation Student-t không có moment bậc bốn hữu hạn.
Persistence gần 1 hạn chế cách diễn giải variance vô điều kiện và residual tests.
Đây là hạn chế cần đưa vào thảo luận, không phải lý do xóa fit theo kết quả test.
Chi tiết chạy code: [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md).
''')
    add('## 6 RQ1 Độ chính xác dự báo biến động')
    add('''### 6.1 Bảng chính h1 và rolling

Mỗi coin dùng **1667 ngày chung của cả 9 model**. RMSE/MAE tính trên RV %²,
QLIKE không có đơn vị; cả ba càng thấp càng tốt. Thập phân dùng dấu chấm như
file CSV gốc. Số trên bảng được làm tròn để đọc, file nguồn giữ độ chính xác.
''')
    for coin in coins:
        part=sorted([r for r in primary if r['symbol']==coin],key=lambda r:float(r['QLIKE']))
        add(f'#### {coin}')
        add(table(['Model','N','QLIKE','RMSE (%²)','MAE (%²)','QLIKE/HAR'],
            [[NAMES[r['model']],integer(r['n']),num(r['QLIKE']),num(r['RMSE']),num(r['MAE']),num(r['QLIKE_relative_to_har'])] for r in part]))
    add(src('outputs/tables/model_comparison.csv','horizon_days=1; window=rolling; từng symbol; cùng mẫu 9 model'))
    add('''Elastic Net có QLIKE/RMSE thấp nhất ở hai coin trong bảng này, nhưng XGBoost
có MAE thấp nhất. Như vậy thứ hạng phụ thuộc loss. QLIKE là thước đo chính đã
chốt trước, không đổi sang MAE chỉ vì một model đứng đầu MAE.

### 6.2 DM so với HAR

d = loss(model) − loss(HAR). D âm là loss thấp hơn HAR. Chỉ khi p<0.05 mới có
bằng chứng danh nghĩa chống giả thuyết loss kỳ vọng bằng nhau, theo giả định
kiểm định đang dùng. P-value nhỏ với d dương là model **kém hơn** HAR.
''')
    qdm=[r for r in dm if r['loss']=='qlike']
    add(table(['Coin','Model','N','Chênh QLIKE với HAR','DM-HLN','p-value'],
        [[r['symbol'],NAMES[r['model']],r['n'],num(r['mean_diff'],6),num(r['stat']),pvalue(r['p_value'])] for r in qdm]))
    add(src('outputs/tables/dm_vs_benchmark.csv','window=rolling; horizon_days=1; loss=qlike; benchmark=har_rv'))
    add('''**Cách viết kết quả:** “Các mô hình ML có cải thiện QLIKE theo điểm ước lượng
so với HAR-RV trong cấu hình chính, nhưng kiểm định DM-HLN chưa cung cấp bằng
chứng cải thiện có ý nghĩa thống kê ở mức 5%. Elastic Net đạt loss thấp nhất
trong mẫu chung; kết quả không ủng hộ kết luận ML luôn vượt mô hình kinh tế lượng.”

GARCH/GJR có QLIKE cao hơn HAR với p<0.05 ở hai coin trong bảng này. Nếu phân
tích RMSE/MAE, lấy loss=se/ae ở file DM, không dùng p-value QLIKE để chứng minh
ý nghĩa thống kê cho một metric khác. P-value chưa điều chỉnh nhiều phép thử.

### 6.3 Vì sao số ngày của các bảng khác nhau
''')
    add(table(['Coin','Model','Ngày yêu cầu','Forecast thành công','Target RV hợp lệ','Mẫu chung RV'],
        [[r['symbol'],NAMES[r['model']],r['n_requested'],r['n_success'],r['n_valid_target'],r['n_common']] for r in coverage if r['model'] in CORE+('enet',)]))
    add(src('outputs/tables/forecast_coverage.csv','horizon_days=1; window=rolling; core models và Elastic Net'))
    add('''Tổng lịch evaluation=1826 ngày/coin. Có 1819 target RV hợp lệ. HAR/ML cần
feature trailing đầy đủ nên có 1673 forecast thành công; giao với target hợp lệ
còn 1667 ngày. Risk chấm return close-to-close, lại cần 20 residual quá khứ cho
FHS, nên mẫu chung risk=1653. Không cộng/trừ hai mẫu như thể cùng một tập ngày.
''')
    add('## 7 RQ2 Biến bổ sung và giải thích dự báo')
    add('### 7.1 Có và không có volume')
    add(table(['Coin','ML','N','QLIKE có volume','QLIKE bỏ volume','Chênh có−bỏ','p DM'],
        [[r['symbol'],NAMES[r['model']],r['n_common'],num(r['QLIKE_full']),num(r['QLIKE_core']),num(r['QLIKE_full_minus_core'],6),pvalue(r['dm_p_value'])] for r in volume]))
    add(src('outputs/tables/backend3_volume_ablation.csv','horizon_days=1; window=rolling'))
    add('''Cùng tham số, cùng dòng train và mẫu test cặp; volume gồm log_qv/log_turn_rel.
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
''')
    add(table(['Coin','ML','Biến thể','N','QLIKE','Chênh với macro_base','p DM'],
        [[r['symbol'],NAMES[r['model']],r['feature_set'],integer(r['n']),num(r['QLIKE']),num(r['QLIKE_minus_without_macro'],6),pvalue(r['dm_p_value'])] for r in macro]))
    add(src('outputs/tables/backend3_macro_ablation.csv','horizon_days=1; window=rolling; cùng mẫu eight variants'))
    add('''Ở ETH/Elastic Net, VIX và VIX+USD có p lần lượt khoảng 0.0390 và 0.0409,
chênh QLIKE âm. Đây là bằng chứng **danh nghĩa** chưa điều chỉnh nhiều phép thử;
không đủ để tuyên bố hiệu quả chung cho mọi coin/model. XGBoost/BTC thêm USD
có p≈0.0859, chưa đạt mức 5%. Không đổi macro vào model chính sau khi xem kết quả.

Nguồn phụ: [macro_sensitivity.md](macro_sensitivity.md),
[macro validation](../outputs/sensitivity/macro/validation.json). Bộ này có
1790 vintage VIX, 361 vintage USD, 23360 fit thành công và 16 file forecast;
23 ô có observation_date sau vintage bị loại khỏi bước chọn feature.

### 7.3 SHAP
''')
    add(table(['Coin','Hạng','Feature','Mean abs SHAP','N origin'],
        [[coin,i+1,r['feature'],num(r['mean_abs_shap']),r['n_origins']] for coin in coins
         for i,r in enumerate(sorted([r for r in shap if r['symbol']==coin],key=lambda r:-float(r['mean_abs_shap'])))]))
    add(src('outputs/tables/backend3_shap_importance.csv','horizon_days=1; window=rolling; XGBoost native exact TreeSHAP'))
    add('''log_rv_d có importance cao nhất ở hai coin trong bảng. SHAP là đóng góp vào
raw log RV prediction của nhiều estimator walk-forward, không phải tác động
nhân quả hay số điểm phần trăm volatility. SHAP lớn không thay cho ablation/DM
để khẳng định incremental predictive power. Base value cộng contributions khớp
raw log prediction; train smearing được áp dụng sau bước này.
''')
    add('## 8 RQ3 Kết quả theo trạng thái thị trường')
    add(table(['Coin','Crisis threshold RV22 (%²)','N hiệu chuẩn','Giai đoạn'],
        [[r['symbol'],num(r['crisis_threshold_pct2']),r['n_calibration'],'2019–2020, cố định sau warmup'] for r in thresholds]))
    add(src('data/processed/regime_thresholds.json','quantile=0.90; n_calibration=487 mỗi coin'))
    add('''Regime gắn tại origin bằng thông tin đã biết: crisis nếu RV22 vượt ngưỡng;
nếu không, bear khi return log 90 ngày ≤−10%, bull khi ≥10%, còn lại normal.
Ưu tiên crisis > bear > bull > normal. Không dùng RV target để gán regime.
''')
    rr=[]
    for coin in coins:
        for state in ('normal','bull','bear','crisis'):
            part=[r for r in regime if r['symbol']==coin and r['regime']==state]
            rr.append([coin,state,integer(part[0]['n'])]+[num(one(part,model=m)['QLIKE']) for m in CORE+('enet',)])
    add(table(['Coin','Regime','N','HAR','GARCH','GJR','XGBoost','Elastic Net'],rr))
    add(src('outputs/tables/regime_performance.csv','horizon_days=1; window=rolling; QLIKE; cùng ngày theo từng regime'))
    add('''Bảng cho thấy không có lợi thế ML đồng đều: XGBoost có QLIKE cao hơn HAR ở
normal và crisis của cả hai coin, dù toàn mẫu h1 có QLIKE hơi thấp hơn HAR.
Elastic Net có điểm QLIKE crisis thấp hơn HAR, với chỉ 88 ngày BTC và 98 ngày ETH.
Muốn viết “khác biệt có ý nghĩa”, tra [dm_by_regime.csv](../outputs/tables/dm_by_regime.csv)
đúng coin/horizon/window/regime/model/loss. Không lấy p-value toàn mẫu cho crisis.
Named stress windows ở mục 10 không đồng nhất với regime crisis hiệu chuẩn này.
''')
    add('## 9 Robustness cửa sổ và horizon')
    rb=[]
    for coin in coins:
        for h in ('1','7'):
            for model in CORE+('enet',):
                a=one(robust,symbol=coin,horizon_days=h,window='rolling',model=model)
                b=one(robust,symbol=coin,horizon_days=h,window='expanding',model=model)
                rb.append([coin,h,NAMES[model],integer(a['n']),num(a['QLIKE']),num(b['QLIKE']),
                           num(b['QLIKE_minus_rolling_same_horizon'],6),pvalue(b['dm_vs_rolling_p_value'])])
    add(table(['Coin','h','Model','N cặp','QLIKE rolling','QLIKE expanding','Chênh exp−roll','p DM exp/roll'],rb))
    add(src('outputs/tables/robustness.csv','core models và Elastic Net; so cùng model/horizon, giao mẫu windows và models'))
    add('''H7 là tổng RV 7 ngày, không phải RV trung bình và không phải bài toán risk
7 ngày. Không kết luận h7 “tốt hơn h1” chỉ vì QLIKE/RMSE có giá trị khác.
H1 có N=1667, h7 có N=1631; target h7 cần đủ cả bảy ngày và kết thúc trong evaluation.
Các p-value trên so expanding với rolling, không so model với HAR.

Ví dụ ETH/HAR h1 expanding có QLIKE cao hơn rolling, p≈0.0020; BTC/GJR h7
expanding có QLIKE thấp hơn rolling, p≈0.0090. Các dấu hiệu phụ thuộc model/horizon,
không ủng hộ tuyên bố một loại cửa sổ luôn thắng. Giữ rolling làm kết quả chính
theo thiết kế, không chọn lại cửa sổ sau khi xem bảng.
''')
    add('## 10 RQ4 VaR ES và backtesting')
    add('''### 10.1 Quy ước và phạm vi

VaR/ES là lower-tail **return**, đơn vị % log return. Alpha=.05/.01 tương ứng
confidence 95%/99%. Ví dụ VaR=-5% nghĩa là ngưỡng đuôi trái của log return,
không phải dự báo lợi nhuận chắc chắn hay loss dương 5%. Breach khi actual return
< VaR. ES là kỳ vọng đuôi và phải ≤VaR theo cùng quy ước.

GARCH/GJR dùng Student-t chuẩn hóa. Các model còn lại dùng FHS từ residual ngoài
mẫu của đúng coin/model/window, chỉ sau khi return đã quan sát; tối thiểu 20
residual. Không dùng residual 2021–2025 của tương lai để tính VaR ngày đầu.
Đầu FHS có tail 1% rất ít điểm, thể hiện ở n_fhs_tail; ES có thể kém ổn định.
Mẫu chung risk bắt đầu 06/02/2021 và có 1653 ngày, không phải toàn bộ 1826 ngày.
''')
    add(table(['Coin','Model','Ngày lịch','Risk khả dụng','Ngày chung','Ngày risk đầu'],
        [[r['coin'],NAMES[r['model']],r['n_scheduled'],r['n_available'],r['n_common'],r['first_available'][:10]]
         for r in risk_coverage if r['model'] in CORE+('enet',)]))
    add(src('outputs/risk/coverage.csv','window=rolling; alpha=0.05; core models và Elastic Net'))
    add('''### 10.2 Coverage và quantile loss trên cùng mẫu

Cả hai bảng dưới dùng 1653 ngày/model/coin. Kỳ vọng khoảng 82.65 breach ở mức
95%, và 16.53 breach ở mức 99%; không yêu cầu observed count bằng chính xác kỳ vọng.
QLoss là pinball/quantile loss, càng thấp càng tốt. Không xếp hạng theo p-value
lớn nhất. P-value >0.05 là chưa bác bỏ theo kiểm định, không chứng minh đúng.
''')
    for alpha in ('0.05','0.01'):
        add(f'#### Confidence {int(round((1-float(alpha))*100))}%')
        add(table(['Coin','Model','Breach/N','Breach rate','p Kupiec','p Christoffersen','QLoss'],
            [[r['coin'],NAMES[r['model']],r['n_breach']+'/'+r['n'],pct(r['breach_rate']),pvalue(r['kupiec_p']),
              pvalue(r['christoffersen_p']),num(r['quantile_loss'])] for r in risk
             if r['alpha']==alpha and r['model'] in CORE+('enet',)]))
    add(src('outputs/risk/backtest.csv','window=rolling; sample=common_all_9_models; alpha=0.05/0.01; core và Elastic Net'))
    add('''Christoffersen chỉ đếm cặp ngày lịch liền nhau: 1646 cặp, 6 khoảng ngắt
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
''')
    examples=[]
    for coin in coins:
        for model in CORE+('enet',):
            a=one(example_rows,coin=coin,model=model,alpha=.05);b=one(example_rows,coin=coin,model=model,alpha=.01)
            if a['status']!='ok' or b['status']!='ok':raise ValueError('Example date unavailable')
            examples.append([coin,NAMES[model],num(a['var']),num(a['es']),num(b['var']),num(b['es']),num(a['return'])])
    add(table(['Coin','Model','VaR95 (%)','ES95 (%)','VaR99 (%)','ES99 (%)','Return thực tế (%)'],examples))
    add('Nguồn: từng [file risk Parquet](../outputs/risk/), `date=2025-12-31; window=rolling; alpha=.05/.01`.')
    add('''ES trong toàn bộ mẫu có các thống kê mô tả observed_es_pct và
mean_es_on_breach_pct tại backtest.csv. Hai thống kê này không phải kiểm định
hiệu chuẩn ES. Kupiec và Christoffersen đánh giá **VaR coverage**. Không viết
“ES đã vượt qua Kupiec/Christoffersen”.

### 10.4 Named stress windows

Bảng ghi **số breach**, mẫu chung của 9 model, không phải phần trăm. Các cửa sổ
được định trước theo ngày lịch; không đồng nhất với nhãn regime ở mục 8.
''')
    labels={'may_2021_selloff':'01–31/05/2021','luna_collapse_2022':'07–13/05/2022','ftx_collapse_2022':'06–14/11/2022'}
    for alpha in ('0.05','0.01'):
        cr=[]
        for coin in coins:
            for name,label in labels.items():
                part=[r for r in crises if r['coin']==coin and r['crisis']==name and r['alpha']==alpha]
                cr.append([coin,label,part[0]['n']]+[one(part,model=m)['n_breach'] for m in CORE])
        add(f'#### Breach confidence {int(round((1-float(alpha))*100))}%')
        add(table(['Coin','Stress window','N','HAR','GARCH','GJR','XGBoost'],cr))
    add(src('outputs/risk/crisis_breaches.csv','window=rolling; sample=common_all_9_models; ba crisis trong evaluation'))
    add('''COVID 12–16/03/2020 nằm trong warmup, không có evaluation forecast. File
ghi outside_evaluation, n=0 và breach để thiếu; không được viết “không có breach
COVID” từ các ô này. Các cửa sổ 7/9 ngày quá nhỏ để khẳng định calibration tốt
chỉ từ vài breach. Dùng để mô tả hành vi stress và đọc cùng toàn mẫu.
''')
    add('## 11 RQ5 Volatility targeting và ý nghĩa kinh tế')
    add('''Mô phỏng cố định: mục tiêu volatility 15%/năm, 365 ngày/năm, max weight=1,
phí một chiều 5 bps, lãi tiền mặt=0. Chuyển log return thành simple return rồi
ghép wealth; phí trên turnover gồm lệnh mua ban đầu của cả chiến lược và
buy-and-hold. Dùng sigma forecast gốc của đúng ngày, không suy từ VaR.

Thiếu sigma thì giữ nguyên số lượng coin, không giao dịch; không bỏ ngày.
Định giá vị thế đang giữ tại cuối mẫu, không bắt buộc bán cuối kỳ. Mẫu chiến
lược là đủ 1826 ngày, khác mẫu chung RV/risk. HAR/ML có 153 ngày thiếu forecast;
GARCH/GJR có đủ forecast. Vì vậy mức tiếp xúc và chính sách khi thiếu cũng ảnh
hưởng kết quả kinh tế, không chỉ độ chính xác dự báo.
''')
    add(table(['Coin','Model','CAGR chiến lược (%)','CAGR B&H (%)','Sharpe chiến lược','Sharpe B&H','MDD chiến lược (%)','MDD B&H (%)'],
        [[r['coin'],NAMES[r['model']],num(r['strategy_ann_return_pct'],2),num(r['bh_ann_return_pct'],2),
          num(r['strategy_sharpe'],3),num(r['bh_sharpe'],3),num(r['strategy_max_drawdown_pct'],2),num(r['bh_max_drawdown_pct'],2)]
         for r in strategy if r['model'] in CORE+('enet',)]))
    add(src('outputs/risk/volatility_targeting.csv','window=rolling; core models và Elastic Net; 2021–2025'))
    add('''MDD là số âm; gần 0 hơn nghĩa là ít sụt giảm hơn. Sharpe dùng simple return,
lãi phi rủi ro giả định 0, annualize sqrt(365). CAGR là tăng trưởng vốn ghép lãi,
không phải mean log return nhân 365. MDD có tính vốn ban đầu bằng 1.

**Cách diễn giải:** chiến lược giữ phần vốn trong cash làm giảm drawdown, đồng
thời giảm mức tăng vốn khi thị trường đi lên. Kết quả không chứng minh dự báo
ML tạo lợi nhuận vượt buy-and-hold. Chưa mô hình slippage, độ trễ khớp lệnh hay
lãi tiền mặt. Daily paths nằm ở [strategy_paths](../outputs/risk/strategy_paths/)
để tái tạo wealth và xem các ngày phí/giao dịch; không dùng tổng số dòng risk
làm số ngày chiến lược.
''')
    add('## 12 Kiểm tra kỹ thuật và trạng thái bàn giao')
    add(table(['Bằng chứng','Kết quả','Nguồn'],[
        ['Dataset chính',str(meta['rows'])+' hàng coin-ngày; input hash được giữ nguyên','data/processed/dataset_meta.json'],
        ['Kinh tế lượng',str(b2['garch_unique_fits'])+' fit GARCH/GJR; lỗi '+str(b2['garch_failed_fits']),'outputs/diagnostics/backend2_validation.json'],
        ['Macro sensitivity',str(mv['fit_count'])+' fit; lỗi '+str(mv['fit_failures'])+'; '+str(mv['comparison_rows'])+' dòng so sánh','outputs/sensitivity/macro/validation.json'],
        ['Backend 4',str(rv['unit_tests']['tests'])+' kiểm thử đạt; checksum/lịch/future-mutation passed','outputs/risk/verification.json'],
        ['File risk',str(rv['risk_files'])+' file; '+str(rv['scheduled_risk_rows'])+' dòng lịch; '+str(rv['valid_risk_rows'])+' dòng chấm được','outputs/risk/run_manifest.json'],
        ['Mẫu risk',str(rv['common_risk_rows'])+' dòng tổng có cờ common; 1653 ngày/coin/model/window/alpha','outputs/risk/coverage.csv'],
        ['RQ5',str(rv['strategy_paths'])+' paths; 2 coin × 9 model × 2 window','outputs/risk/strategy_paths/'],
        ['Holdout mô hình','Chưa đánh giá','holdout_evaluated=false / holdout_scored=false']]))
    add('''Dòng risk đếm theo coin × model × window × alpha × ngày, **không phải**
số ngày độc lập hay số nến gốc. 47 là số test riêng Backend 4; số test toàn repo
được kiểm tra riêng khi tích hợp. Unit test đạt không chứng minh dự báo vượt
benchmark, không thay residual diagnostics hay review độc lập của con người.
''')
    if (root/'outputs/reporting/repository_validation.json').exists():
        gate=js('outputs/reporting/repository_validation.json')
        if not gate['passed']:raise ValueError('Repository integration check did not pass')
        add(f'Kiểm tra tích hợp toàn repo: **{gate["tests"]} kiểm thử đạt**, '
            '[repository_validation.json](../outputs/reporting/repository_validation.json). '
            'Đây là kiểm tra code, không phải kết luận mô hình đạt ý nghĩa thống kê.')
    add('## 13 Hình và bảng để đưa vào luận')
    figures=[
        ('Dữ liệu','outputs/figures/figure_3_1_prices.png','Giá BTC và ETH, mẫu mô tả 2019–2025, USDT'),
        ('Dữ liệu','outputs/figures/figure_3_2_rv.png','RV ngày %², giữ khoảng thiếu'),
        ('Dữ liệu','outputs/figures/figure_3_3_acf_rv.png','ACF trên đoạn liên tục dài nhất trong warmup; N ở acf_rv.csv'),
    ]
    for coin in coins:
        figures.extend([
            ('Dự báo',f'outputs/figures/backend1_{coin}_rolling_h1_forecast_vs_actual.png','Actual/forecast RV và căn RV, kết quả chính'),
            ('Dự báo',f'outputs/figures/backend1_{coin}_rolling_h1_rolling_qlike.png','QLIKE trung bình cửa sổ 90 ngày lịch'),
            ('Regime',f'outputs/figures/backend1_{coin}_rolling_h1_regimes.png','Kết quả theo nhãn tại origin'),
            ('SHAP',f'outputs/figures/backend3_{coin}_rolling_h1_shap.png','Contributions vào raw log RV; không phải causal effect'),
            ('Risk',f'outputs/figures/risk/{coin}_har_rv_var_breaches.png','HAR: return, VaR, ES và breach; cả 95%/99%'),
            ('Risk',f'outputs/figures/risk/{coin}_xgboost_var_breaches.png','XGBoost: return, VaR, ES và breach; cả 95%/99%')])
    for _,rel,_ in figures:
        if not (root/rel).is_file():raise ValueError(f'Missing figure: {rel}')
    add(table(['Phần','Hình để tải','Chú thích cần giữ'],[[part,f'[{Path(rel).name}](../{rel})',note] for part,rel,note in figures]))
    add('''Prefix backend1 trong tên hình là tên module tổng hợp chung, không có nghĩa
hình chỉ chứa output của giai đoạn Backend 1. Hình đã lấy từ forecast thật hiện
có; tra bảng đi kèm để biết N và phạm vi. Khi trích, ghi “Nguồn: tính toán của
nhóm từ Binance spot, snapshot 18/10/2026; evaluation 2021–2025” và bổ sung macro
ALFRED khi hình/bảng sử dụng sensitivity. Không ghi nguồn một paper cho số nhóm tính.

Không dùng hình mô tả 2019–2025 để gọi là OOS forecast, hoặc hình ACF warmup để
gọi là toàn mẫu 2019–2026. Các hình stress thể hiện forecast/breach, không phải
khuyến nghị giao dịch. Tất cả hình model chính ở đây không chấm holdout.
''')
    add('''## 14 Những câu cần viết đúng và giới hạn cần giữ

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
''')
    add('''## 15 Tra nguồn và cập nhật tài liệu

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
''')
    destination=root/'docs/BAN_GIAO_VIET_LUAN.md'
    destination.write_bytes(('\n'.join(out).rstrip()+'\n').encode('utf-8'))
    folder=root/'outputs/reporting';folder.mkdir(parents=True,exist_ok=True)
    manifest=dict(scope='existing 2021–2025 evaluation outputs; no refit, no holdout scoring',
        as_of='2026-10-24',dataset_sha256=meta['dataset_sha256'],input_sha256=used,input_hash_modes=hash_modes,
        output='docs/BAN_GIAO_VIET_LUAN.md',output_sha256=sha(destination))
    (folder/'handoff_manifest.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    print(f'Wrote {destination}; {len(used)} verified input files; no models fitted.')
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--snapshot',type=Path,help='Optional verified JSON intermediate for Parquet-free authoring')
    a=p.parse_args();build(a.root,a.snapshot)

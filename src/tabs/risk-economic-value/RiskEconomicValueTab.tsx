import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, ChartNoAxesCombined, CircleHelp, Gauge, ShieldCheck, ShieldAlert, TrendingDown } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, apiPaths, type DashboardSample, type RiskBacktestRow, type RiskResponse, type RiskResearchResponse } from '../../lib/api'
import { ChartEmpty, fmt, Metric } from '../../components/DashboardParts'
import './risk-economic-value.css'

type SymbolCode = 'BTCUSDT' | 'ETHUSDT'
type ResearchTab = 'ro4' | 'ro5'

const MODELS = [
  ['combo_core4', 'Combo Core 4'],
  ['combo_econ', 'Combo Econ'],
  ['enet', 'Elastic Net'],
  ['garch', 'GARCH(1,1)'],
  ['gjr_garch', 'GJR-GARCH'],
  ['har_rv', 'HAR-RV'],
  ['hist_mean', 'Historical Mean'],
  ['naive_rw', 'Naive Random Walk'],
  ['xgboost', 'XGBoost'],
] as const

const MODEL_LABELS = Object.fromEntries(MODELS) as Record<string, string>
const CRISIS_LABELS: Record<string, string> = {
  may_2021_selloff: 'Đợt bán tháo tháng 5/2021',
  luna_collapse_2022: 'Luna/UST mất neo · 05/2022',
  ftx_collapse_2022: 'Thanh khoản FTX · 11/2022',
}

const formatPct = (value: number | null | undefined, digits = 2) =>
  value == null || !Number.isFinite(value) ? '—' : `${value.toFixed(digits)}%`
const formatPValue = (value: number | null) => value == null ? '—' : value.toFixed(3)
const periodLabel = (sample: DashboardSample) => sample === 'evaluation' ? 'Evaluation · 2021–2025' : 'Holdout · 2026'

function BacktestStatus({ row }: { row: RiskBacktestRow }) {
  const kupiecPass = row.kupiec_p != null && row.kupiec_p >= 0.05
  const independencePass = row.christoffersen_p != null && row.christoffersen_p >= 0.05
  if (kupiecPass && independencePass) return <span className="risk-result-pill supported">Chưa bác bỏ</span>
  if (row.kupiec_p == null || row.christoffersen_p == null) return <span className="risk-result-pill unavailable">Chưa đủ dữ liệu</span>
  return <span className="risk-result-pill rejected">Có cảnh báo</span>
}

function AnalysisNotice({ loading, error }: { loading: boolean; error: unknown }) {
  return (
    <div className={`notice ${error ? '' : 'notice-success'} risk-data-notice`}>
      <span className="notice-icon"><ShieldCheck size={17} /></span>
      <div>
        <strong>{loading ? 'Đang tải kết quả kiểm định rủi ro' : error ? 'Không tải được kết quả nghiên cứu rủi ro' : 'Kết quả backtest VaR và mô phỏng volatility targeting'}</strong>
        <p>{error instanceof Error ? error.message : 'Dùng common sample để so sánh công bằng giữa mô hình; dữ liệu theo bộ lọc tài sản và kỳ đánh giá.'}</p>
      </div>
      <span className="notice-tag">BACKEND</span>
    </div>
  )
}

function RiskChart({ items, error }: { items: RiskResponse['items']; error: unknown }) {
  if (!items.length) return <div className="chart-wrap"><ChartEmpty error={error} /></div>
  return (
    <div className="chart-wrap risk-line-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={items}>
          <CartesianGrid stroke="#203047" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(0, 10)} tick={{ fill: '#718097', fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={36} />
          <YAxis tick={{ fill: '#718097', fontSize: 10 }} tickLine={false} axisLine={false} width={48} tickFormatter={(value: number) => `${value}%`} />
          <Tooltip
            labelFormatter={(value) => String(value).slice(0, 10)}
            formatter={(value) => typeof value === 'number' ? [`${value.toFixed(3)}%`] : ['—']}
            contentStyle={{ background: '#0d1725', border: '1px solid #26374d', borderRadius: 6, color: '#e7edf6', fontSize: 11 }}
          />
          <Line type="monotone" dataKey="return" name="Return thực tế" stroke="#9aa9bb" strokeWidth={1.2} dot={false} connectNulls={false} />
          <Line type="monotone" dataKey="var" name="VaR" stroke="#f2b83f" strokeWidth={1.7} dot={false} connectNulls={false} />
          <Line type="monotone" dataKey="es" name="ES" stroke="#f07845" strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function RiskEconomicValueTab({ symbol, sample }: { symbol: SymbolCode; sample: DashboardSample }) {
  const [activeTab, setActiveTab] = useState<ResearchTab>('ro4')
  const [alpha, setAlpha] = useState<0.01 | 0.05>(0.01)
  const [model, setModel] = useState('combo_core4')
  const [window, setWindow] = useState<'rolling' | 'expanding'>('rolling')

  const analysis = useQuery({
    queryKey: ['risk-research', symbol, model, window, alpha, sample],
    queryFn: async () => (await api.get<RiskResearchResponse>(apiPaths.riskResearch, {
      params: { symbol, model, window, alpha, sample },
    })).data,
  })
  const risk = useQuery({
    queryKey: ['risk-series', symbol, model, window, alpha, sample],
    queryFn: async () => (await api.get<RiskResponse>(apiPaths.risk, {
      params: { symbol, model, window, alpha, limit: 3000, sample },
    })).data,
  })

  const selectedBacktest = analysis.data?.backtest.find((row) => row.model === model)
  const crisisRows = useMemo(
    () => (analysis.data?.crisis_backtest ?? []).filter((row) => row.model === model && row.status === 'ok'),
    [analysis.data, model],
  )
  const selectedStrategy = analysis.data?.selected_strategy
  const strategyAdvantage = selectedStrategy?.strategy_ann_return_pct != null && selectedStrategy.bh_ann_return_pct != null
    ? selectedStrategy.strategy_ann_return_pct - selectedStrategy.bh_ann_return_pct
    : null
  const conclusion = selectedBacktest
    ? selectedBacktest.kupiec_p != null && selectedBacktest.christoffersen_p != null
      && selectedBacktest.kupiec_p >= 0.05 && selectedBacktest.christoffersen_p >= 0.05
      ? 'Chưa bác bỏ ở mức 5%'
      : 'Có cảnh báo kiểm định'
    : 'Chưa có kết quả'

  return (
    <div className="risk-research">
      <div className="vf-research-tabs risk-research-tabs" role="tablist" aria-label="Câu hỏi nghiên cứu rủi ro">
        <button type="button" role="tab" aria-selected={activeTab === 'ro4'} className={activeTab === 'ro4' ? 'active' : ''} onClick={() => setActiveTab('ro4')}>
          <ShieldAlert size={17} /> RO4 · VaR & Expected Shortfall
        </button>
        <button type="button" role="tab" aria-selected={activeTab === 'ro5'} className={activeTab === 'ro5' ? 'active' : ''} onClick={() => setActiveTab('ro5')}>
          <ChartNoAxesCombined size={17} /> RO5 · Volatility targeting
        </button>
      </div>

      <AnalysisNotice loading={analysis.isLoading} error={analysis.error} />

      <div className="vf-question-card risk-question-card">
        <div className="risk-question-copy">
          <span className={`vf-question-tag risk-question-tag ${activeTab}`}>{activeTab === 'ro4' ? 'RO4' : 'RO5'}</span>
          <div>
            <h2>{activeTab === 'ro4' ? 'VaR và Expected Shortfall' : 'Giá trị kinh tế của dự báo biến động'}</h2>
            <p>{activeTab === 'ro4'
              ? 'Mô hình nào kiểm soát tỷ lệ vi phạm VaR phù hợp hơn, kể cả trong các giai đoạn thị trường căng thẳng?'
              : 'Cải thiện dự báo biến động có chuyển thành kết quả quản trị vị thế tốt hơn sau chi phí giao dịch không?'}</p>
          </div>
        </div>
        <div className="risk-controls">
          <label className="risk-control">
            <span>Mô hình</span>
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              {MODELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="risk-control">
            <span>Cửa sổ</span>
            <select value={window} onChange={(event) => setWindow(event.target.value as 'rolling' | 'expanding')}>
              <option value="rolling">Rolling</option>
              <option value="expanding">Expanding</option>
            </select>
          </label>
          {activeTab === 'ro4' && (
            <div className="risk-confidence" aria-label="Mức tin cậy VaR">
              <button type="button" className={alpha === 0.05 ? 'active' : ''} aria-pressed={alpha === 0.05} onClick={() => setAlpha(0.05)}>95%</button>
              <button type="button" className={alpha === 0.01 ? 'active' : ''} aria-pressed={alpha === 0.01} onClick={() => setAlpha(0.01)}>99%</button>
            </div>
          )}
          <span className="risk-sample-tag">{periodLabel(sample)}</span>
        </div>
      </div>

      {activeTab === 'ro4' ? (
        <>
          <div className="risk-conclusion">
            <span className={`risk-conclusion-icon ${conclusion === 'Có cảnh báo kiểm định' ? 'warning' : ''}`}>
              {conclusion === 'Có cảnh báo kiểm định' ? <CircleHelp size={17} /> : <ShieldCheck size={17} />}
            </span>
            <div><strong>Kết quả cho {MODEL_LABELS[model]}</strong><p>{conclusion} · kiểm định Kupiec và Christoffersen, mức ý nghĩa 5%.</p></div>
            <span className="risk-conclusion-period">{sample === 'evaluation' ? 'Out-of-sample' : 'Final holdout'}</span>
          </div>

          <div className="metric-grid">
            <Metric label={`Vi phạm VaR ${100 - alpha * 100}%`} value={selectedBacktest?.n_breach == null ? '—' : String(selectedBacktest.n_breach)} suffix={`/ ${selectedBacktest?.n ?? '—'}`} note="Quan sát common sample" icon={<ShieldAlert size={17} />} />
            <Metric label="Tỷ lệ vi phạm thực tế" value={formatPct(selectedBacktest?.breach_rate == null ? null : selectedBacktest.breach_rate * 100)} suffix="" note={`Mức kỳ vọng ${formatPct(alpha * 100)}`} icon={<Activity size={17} />} />
            <Metric label="Kupiec p-value" value={formatPValue(selectedBacktest?.kupiec_p ?? null)} suffix="" note="Kiểm định tỷ lệ vi phạm" icon={<Gauge size={17} />} />
            <Metric label="Christoffersen p-value" value={formatPValue(selectedBacktest?.christoffersen_p ?? null)} suffix="" note="Kiểm định tính độc lập" icon={<BarChart3 size={17} />} />
          </div>

          <div className="panel vf-panel table-panel risk-backtest-panel">
            <div className="panel-heading"><div><h3>Backtest VaR · so sánh mô hình</h3><p>{symbol.replace('USDT', '')} · {window} · mức tin cậy {100 - alpha * 100}% · common sample</p></div><span className="risk-method-tag">FHS / Student-t</span></div>
            <div className="vf-table-scroll table-wrap"><table className="vf-table">
              <thead><tr><th>Mô hình</th><th>Số vi phạm / kỳ vọng</th><th>Tỷ lệ vi phạm</th><th>Kupiec p</th><th>Christoffersen p</th><th>Quantile loss</th><th>Kết luận</th></tr></thead>
              <tbody>{(analysis.data?.backtest ?? []).map((row) => (
                <tr key={row.model} className={row.model === model ? 'selected' : ''}>
                  <td><b>{MODEL_LABELS[row.model] ?? row.model}</b><small>{row.method}</small></td>
                  <td>{row.n_breach ?? '—'} / {row.n ? (row.n * alpha).toFixed(1) : '—'}</td>
                  <td>{row.breach_rate == null ? '—' : formatPct(row.breach_rate * 100)}</td>
                  <td>{formatPValue(row.kupiec_p)}</td>
                  <td>{formatPValue(row.christoffersen_p)}</td>
                  <td>{fmt(row.quantile_loss, 4)}</td>
                  <td><BacktestStatus row={row} /></td>
                </tr>
              ))}</tbody>
            </table></div>
            {!analysis.isLoading && !analysis.error && !analysis.data?.backtest.length && <p className="risk-empty-note">Không có bảng backtest cho mẫu và bộ lọc đang chọn.</p>}
            <p className="risk-footnote">p-value dưới 0.05 cho thấy có bằng chứng bác bỏ giả thuyết kiểm định tương ứng. Các kiểm định này đánh giá coverage của VaR, không phải kiểm định hiệu chuẩn ES.</p>
          </div>

          <div className="risk-panel-grid">
            <section className="panel vf-panel risk-chart-panel">
              <div className="panel-heading"><div><h3>Return, VaR và Expected Shortfall</h3><p>{MODEL_LABELS[model]} · {symbol.replace('USDT', '')} · đơn vị % log return</p></div><span className="risk-method-tag">α = {alpha}</span></div>
              <div className="risk-chart-legend"><span><i className="returns" />Return thực tế</span><span><i className="var" />VaR</span><span><i className="es" />Expected Shortfall</span></div>
              <RiskChart items={risk.data?.items ?? []} error={risk.error} />
            </section>
            <section className="panel vf-panel risk-crisis-panel">
              <div className="panel-heading"><div><h3>Vi phạm trong giai đoạn căng thẳng</h3><p>Đếm trên các ngày có dữ liệu VaR hợp lệ</p></div><TrendingDown size={17} /></div>
              {crisisRows.length ? <div className="risk-crisis-list">{crisisRows.map((row) => (
                <article className="risk-crisis-card" key={row.crisis}>
                  <div><strong>{CRISIS_LABELS[row.crisis] ?? row.crisis}</strong><span>{row.start} – {row.end}</span></div>
                  <b>{row.n_breach ?? '—'} <small>/ {row.n} ngày vi phạm</small></b>
                  <i><span style={{ width: `${Math.min(100, Math.max(0, (row.breach_rate ?? 0) * 100))}%` }} /></i>
                  <small>Tỷ lệ thực tế {formatPct(row.breach_rate == null ? null : row.breach_rate * 100)} · kỳ vọng {formatPct(alpha * 100)}</small>
                </article>
              ))}</div> : <div className="risk-empty-note">{sample === 'holdout' ? 'Các cửa sổ khủng hoảng 2021–2022 nằm ngoài kỳ holdout 2026; không dùng lại làm kết quả holdout.' : 'Không có cửa sổ khủng hoảng đủ dữ liệu cho mô hình và bộ lọc này.'}</div>}
            </section>
          </div>

          <div className="panel vf-panel table-panel risk-observations">
            <div className="panel-heading"><div><h3>Quan sát VaR gần nhất</h3><p>Chuỗi dữ liệu thực từ risk output</p></div></div>
            <div className="vf-table-scroll table-wrap"><table className="vf-table"><thead><tr><th>Ngày</th><th>Return (%)</th><th>VaR (%)</th><th>ES (%)</th><th>Breach</th><th>Trạng thái</th></tr></thead>
              <tbody>{[...(risk.data?.items ?? [])].slice(-12).reverse().map((point) => <tr key={point.date}>
                <td>{point.date.slice(0, 10)}</td><td>{fmt(point.return)}</td><td>{fmt(point.var)}</td><td>{fmt(point.es)}</td><td>{point.breach == null ? '—' : point.breach ? 'Có' : 'Không'}</td><td>{point.status}</td>
              </tr>)}</tbody>
            </table></div>
          </div>
        </>
      ) : (
        <>
          <div className="risk-conclusion risk-economics-conclusion">
            <span className="risk-conclusion-icon"><ChartNoAxesCombined size={17} /></span>
            <div><strong>Volatility targeting · {selectedStrategy?.vol_target_pct ?? 15}% mục tiêu năm hóa</strong><p>So sánh với buy-and-hold trên cùng kỳ; đã tính phí giao dịch theo thiết lập backend.</p></div>
            <span className="risk-conclusion-period">Mô phỏng học thuật</span>
          </div>

          <div className="metric-grid">
            <Metric label="Lợi nhuận năm hóa · chiến lược" value={formatPct(selectedStrategy?.strategy_ann_return_pct)} suffix="" note={`Buy-and-hold ${formatPct(selectedStrategy?.bh_ann_return_pct)}`} icon={<ChartNoAxesCombined size={17} />} />
            <Metric label="Sharpe · chiến lược" value={fmt(selectedStrategy?.strategy_sharpe, 3)} suffix="" note={`Buy-and-hold ${fmt(selectedStrategy?.bh_sharpe, 3)}`} icon={<Gauge size={17} />} />
            <Metric label="Max drawdown" value={formatPct(selectedStrategy?.strategy_max_drawdown_pct)} suffix="" note={`Buy-and-hold ${formatPct(selectedStrategy?.bh_max_drawdown_pct)}`} icon={<TrendingDown size={17} />} />
            <Metric label="Δ lợi nhuận năm hóa" value={strategyAdvantage == null ? '—' : formatPct(strategyAdvantage)} suffix="" note="Targeting trừ buy-and-hold" icon={<Activity size={17} />} />
          </div>

          <div className="panel vf-panel risk-chart-panel risk-wealth-panel">
            <div className="panel-heading"><div><h3>Đường tài sản tích lũy</h3><p>{MODEL_LABELS[model]} · {symbol.replace('USDT', '')} · lợi nhuận tích lũy, gốc = 0%</p></div><span className="risk-method-tag">{selectedStrategy?.vol_target_pct ?? 15}% target</span></div>
            <div className="risk-chart-legend"><span><i className="targeting" />Volatility targeting</span><span><i className="buy-hold" />Buy-and-hold</span></div>
            {analysis.data?.strategy_series.length ? <div className="chart-wrap risk-line-chart">
              <ResponsiveContainer width="100%" height="100%"><LineChart data={analysis.data.strategy_series}>
                <CartesianGrid stroke="#203047" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(value: string) => value.slice(0, 10)} tick={{ fill: '#718097', fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={38} />
                <YAxis tick={{ fill: '#718097', fontSize: 10 }} tickLine={false} axisLine={false} width={50} tickFormatter={(value: number) => `${value}%`} />
                <Tooltip labelFormatter={(value) => String(value).slice(0, 10)} formatter={(value) => typeof value === 'number' ? [`${value.toFixed(2)}%`] : ['—']} contentStyle={{ background: '#0d1725', border: '1px solid #26374d', borderRadius: 6, color: '#e7edf6', fontSize: 11 }} />
                <Line type="monotone" dataKey="strategy_cum" name="Volatility targeting" stroke="#f2b83f" strokeWidth={1.8} dot={false} />
                <Line type="monotone" dataKey="bh_cum" name="Buy-and-hold" stroke="#91a4bc" strokeWidth={1.4} dot={false} />
              </LineChart></ResponsiveContainer>
            </div> : <div className="risk-empty-note">{analysis.isLoading ? 'Đang tải chuỗi tài sản từ backend…' : 'Không có chuỗi strategy cho mẫu đang chọn.'}</div>}
          </div>

          <div className="panel vf-panel table-panel risk-strategy-panel">
            <div className="panel-heading"><div><h3>So sánh kết quả volatility targeting</h3><p>{symbol.replace('USDT', '')} · {window} · mục tiêu và chi phí theo protocol backend</p></div></div>
            <div className="vf-table-scroll table-wrap"><table className="vf-table"><thead><tr><th>Mô hình</th><th>Lợi nhuận năm hóa</th><th>Buy-and-hold</th><th>Sharpe</th><th>Max drawdown</th><th>Trọng số TB</th><th>Ngày thiếu forecast</th><th>Chi phí tích lũy</th></tr></thead>
              <tbody>{(analysis.data?.volatility_targeting ?? []).map((row) => <tr key={row.model} className={row.model === model ? 'selected' : ''}>
                <td><b>{MODEL_LABELS[row.model] ?? row.model}</b></td><td>{formatPct(row.strategy_ann_return_pct)}</td><td>{formatPct(row.bh_ann_return_pct)}</td><td>{fmt(row.strategy_sharpe, 3)}</td><td>{formatPct(row.strategy_max_drawdown_pct)}</td><td>{row.mean_weight == null ? '—' : row.mean_weight.toFixed(3)}</td><td>{row.n_missing_forecast} / {row.n_days}</td><td>{formatPct(row.total_cost_pct_of_daily_nav)}</td>
              </tr>)}</tbody>
            </table></div>
          </div>
          <p className="risk-footnote risk-assumption-note">Thiết lập cố định từ backend: mục tiêu biến động 15%/năm, đòn bẩy tối đa 1×, phí một chiều 5 bps, annualization 365 ngày. Đây là mô phỏng lịch sử, không phải khuyến nghị đầu tư; holdout được khởi tạo riêng và không tối ưu tham số trên holdout.</p>
        </>
      )}
    </div>
  )
}

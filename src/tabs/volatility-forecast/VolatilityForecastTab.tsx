import { useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Activity, BarChart3, Database, Download, Layers, Shield, Sparkles, Target, TrendingUp } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useDashboardOverview, useForecasts, useMarket } from '../../lib/dashboardQueries'
import type { ForecastRecord, MarketPoint } from '../../lib/api'
import { RQ2Results, RQ3Results } from './ResearchSections'
import './volatility-forecast.css'

type SymbolCode = 'BTCUSDT' | 'ETHUSDT'
type HorizonDays = 1 | 7
type ResearchTab = 'rq1' | 'rq2' | 'rq3'
type RangeKey = '3M' | '6M' | '1Y' | 'ALL'
type MetricSample = { regime: string; actual: number; forecast: number; har: number }

const RANGE_DAYS: Record<RangeKey, number> = { '3M': 92, '6M': 183, '1Y': 365, ALL: Infinity }
const REGIME_COLORS: Record<string, string> = { normal: '#91a4bc', bull: '#45c39f', bear: '#f0ad36', crisis: '#ed8181' }
const REGIME_ORDER = ['normal', 'bull', 'bear', 'crisis']
const fmt = (value: number | null | undefined, digits = 3) =>
  typeof value === 'number' && Number.isFinite(value)
    ? value.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : '—'
const dateKey = (value: string) => value.slice(0, 10)
const modelName = (name: string) => ({
  enet: 'Elastic Net',
  xgboost: 'XGBoost',
  har_rv: 'HAR-RV',
  combo_core4: 'Combo Core 4',
  combo_econ: 'Combo Econ',
  gjr_garch: 'GJR-GARCH',
  garch: 'GARCH',
  naive_rw: 'Naive Random Walk',
  hist_mean: 'Historical Mean',
}[name.toLowerCase()] ?? name.toUpperCase())
const varianceActual = (point: MarketPoint | undefined, horizon: HorizonDays) =>
  point ? (horizon === 1 ? point.y_rv_h1 : point.y_rv_h7) : null
const varianceForecast = (item: ForecastRecord) => item.rv_forecast_pct2

function jsonRecord(value?: string | null): Record<string, number> {
  if (!value) return {}
  try {
    const parsed: unknown = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, number> : {}
  } catch {
    return {}
  }
}

function qlike(actual: number, forecast: number) {
  return actual > 0 && forecast > 0 ? Math.log(forecast) + actual / forecast : null
}

function PanelTitle({ icon, title, subtitle, badge }: {
  icon: ReactNode
  title: string
  subtitle: string
  badge?: string
}) {
  return <div className="vf-panel-title"><div className="vf-title-icon">{icon}</div><div className="vf-title-copy"><h3>{title}</h3><p>{subtitle}</p></div>{badge && <span className="vf-badge">{badge}</span>}</div>
}

function EmptyState({ loading, error }: { loading: boolean; error: unknown }) {
  return <div className="vf-empty"><Database size={23}/><strong>{loading ? 'Đang tải dự báo từ backend…' : 'Chưa tải được chuỗi dự báo'}</strong><span>{loading ? 'Đang ghép forecast với dữ liệu RV thực tế.' : error instanceof Error ? error.message : 'Kiểm tra kết nối API backend rồi thử lại.'}</span></div>
}

export default function VolatilityForecastTab({ symbol = 'BTCUSDT', horizonDays = 1 }: { symbol?: SymbolCode; horizonDays?: HorizonDays }) {
  const [activeTab, setActiveTab] = useState<ResearchTab>('rq1')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [range, setRange] = useState<RangeKey>('1Y')
  const overview = useDashboardOverview(symbol, horizonDays)
  const market = useMarket(symbol, 3000)
  const effectiveModel = selectedModel ?? overview.data?.best_model?.model ?? 'enet'
  const selectedForecasts = useForecasts(symbol, effectiveModel, horizonDays, 3000)
  const harForecasts = useForecasts(symbol, 'har_rv', horizonDays, 3000)

  const marketByOrigin = useMemo(() => new Map((market.data?.series ?? []).map(point => [dateKey(point.origin_date), point])), [market.data])
  const marketByTarget = useMemo(() => {
    const map = new Map<string, MarketPoint>()
    for (const point of market.data?.series ?? []) {
      const target = horizonDays === 1 ? point.target_end_h1 : point.target_end_h7
      if (target) map.set(dateKey(target), point)
    }
    return map
  }, [market.data, horizonDays])

  const sortedForecasts = useMemo(
    () => [...(selectedForecasts.data?.items ?? [])].sort((a, b) => a.target_date.localeCompare(b.target_date)),
    [selectedForecasts.data],
  )
  const chartRows = useMemo(() => sortedForecasts.flatMap(item => {
    const actualPoint = marketByTarget.get(dateKey(item.target_date))
    const actualVariance = actualPoint ? varianceActual(actualPoint, horizonDays) : null
    const forecastVol = item.volatility_forecast_pct
    const actualVol = typeof actualVariance === 'number' && actualVariance >= 0 ? Math.sqrt(actualVariance) : null
    if (forecastVol == null && actualVol == null) return []
    return [{
      date: dateKey(item.target_date),
      forecastVol,
      actualVol,
      forecastVariance: item.rv_forecast_pct2,
      regime: actualPoint?.regime?.toLowerCase() ?? 'normal',
    }]
  }), [sortedForecasts, marketByTarget, horizonDays])
  const visibleChartRows = useMemo(() => {
    if (!chartRows.length || range === 'ALL') return chartRows
    const latest = new Date(chartRows[chartRows.length - 1].date).getTime()
    const cutoff = latest - RANGE_DAYS[range] * 86400000
    return chartRows.filter(row => new Date(row.date).getTime() >= cutoff)
  }, [chartRows, range])

  const comparison = overview.data?.comparison ?? []
  const sortedComparison = useMemo(() => [...comparison].sort((a, b) => (a.QLIKE ?? Infinity) - (b.QLIKE ?? Infinity)), [comparison])
  const bestModel = overview.data?.best_model
  const selectedMetrics = comparison.find(row => row.model.toLowerCase() === effectiveModel.toLowerCase())
  const relativeQlike = selectedMetrics?.QLIKE_relative_to_har
  const dm = overview.data?.qlike_dm_vs_har
  const latestForecast = sortedForecasts.at(-1)
  const latestTraining = latestForecast
  const components = latestTraining?.combination_components
    ? (() => { try { return JSON.parse(latestTraining.combination_components!) as string[] } catch { return [] } })()
    : []
  const weights = jsonRecord(latestTraining?.combination_weights)

  const regimeSamples = useMemo(() => {
    const harByOrigin = new Map((harForecasts.data?.items ?? []).map(item => [dateKey(item.origin_date), item]))
    const data: MetricSample[] = []
    for (const item of selectedForecasts.data?.items ?? []) {
      const key = dateKey(item.origin_date)
      const marketPoint = marketByOrigin.get(key)
      const actual = varianceActual(marketPoint, horizonDays)
      const forecast = varianceForecast(item)
      const har = harByOrigin.get(key)
      const harValue = har ? varianceForecast(har) : null
      if (typeof actual !== 'number' || actual <= 0 || typeof forecast !== 'number' || forecast <= 0 || typeof harValue !== 'number' || harValue <= 0) continue
      data.push({ regime: marketPoint?.regime?.toLowerCase() || 'normal', actual, forecast, har: harValue })
    }
    return data
  }, [selectedForecasts.data, harForecasts.data, marketByOrigin, horizonDays])

  const regimeMetrics = useMemo(() => REGIME_ORDER.map(regime => {
    const rows = regimeSamples.filter(row => row.regime === regime)
    const avgQlike = (key: 'forecast' | 'har') => rows.length ? rows.reduce((sum, row) => sum + (qlike(row.actual, row[key]) ?? 0), 0) / rows.length : null
    const rmse = (key: 'forecast' | 'har') => rows.length ? Math.sqrt(rows.reduce((sum, row) => sum + (row[key] - row.actual) ** 2, 0) / rows.length) : null
    const modelLoss = avgQlike('forecast')
    const harLoss = avgQlike('har')
    return { regime, n: rows.length, modelLoss, harLoss, ratio: modelLoss !== null && harLoss ? modelLoss / harLoss : null, modelRmse: rmse('forecast'), harRmse: rmse('har') }
  }), [regimeSamples])
  const recent = [...sortedForecasts].reverse().slice(0, 10)
  const selectedName = modelName(effectiveModel)
  const isLoading = overview.isLoading || selectedForecasts.isLoading || market.isLoading
  const hasError = overview.error ?? selectedForecasts.error ?? market.error

  const exportForecastCsv = () => {
    const rows = sortedForecasts.map(item => {
      const actualPoint = marketByTarget.get(dateKey(item.target_date))
      const actual = varianceActual(actualPoint, horizonDays)
      return [dateKey(item.origin_date), dateKey(item.target_date), item.rv_forecast_pct2 ?? '', item.volatility_forecast_pct ?? '', actual ?? '', actualPoint?.regime ?? '', item.status].join(',')
    })
    const csv = ['origin_date,target_date,forecast_rv_pct2,forecast_volatility_pct,realized_rv_pct2,regime,status', ...rows].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = symbol.toLowerCase() + '_forecast_h' + horizonDays + '.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading && !selectedForecasts.data && !overview.data) return <EmptyState loading error={hasError}/>
  if (hasError && !selectedForecasts.data && !overview.data) return <EmptyState loading={false} error={hasError}/>

  return <div className="volatility-forecast-tab">
    <nav className="vf-research-tabs" aria-label="Câu hỏi nghiên cứu về dự báo">
      <button className={activeTab === 'rq1' ? 'active' : ''} onClick={() => setActiveTab('rq1')} aria-pressed={activeTab === 'rq1'}><BarChart3 size={16}/><span>RQ1 · So sánh mô hình</span></button>
      <button className={activeTab === 'rq2' ? 'active' : ''} onClick={() => setActiveTab('rq2')} aria-pressed={activeTab === 'rq2'}><Layers size={16}/><span>RQ2 · Thông tin mô hình</span></button>
      <button className={activeTab === 'rq3' ? 'active' : ''} onClick={() => setActiveTab('rq3')} aria-pressed={activeTab === 'rq3'}><TrendingUp size={16}/><span>RQ3 · Theo regime</span></button>
    </nav>

    {activeTab === 'rq1' && <div className="vf-section">
      <section className="vf-question-card">
        <span className="vf-question-tag">RQ1</span>
        <div><h2>Mô hình nào dự báo biến động tốt nhất?</h2><p>{symbol.replace('USDT', '')} · {horizonDays} ngày · Rolling out-of-sample · {overview.data?.evaluation_period ?? 'Đang chờ metadata đánh giá'}</p></div>
        <span className="vf-answer-badge"><Target size={15}/>{bestModel?.model ? 'Model tốt nhất: ' + modelName(bestModel.model) : 'Đang tải kết quả'}</span>
      </section>

      <div className="vf-summary-grid">
        <article className="vf-summary-card"><span>Model được chọn</span><strong>{selectedName}</strong><small>{latestForecast?.training_kind ?? 'Model từ bảng đánh giá backend'}</small></article>
        <article className="vf-summary-card"><span>QLIKE out-of-sample</span><strong>{fmt(selectedMetrics?.QLIKE, 4)}</strong><small>{selectedMetrics?.n?.toLocaleString('vi-VN') ?? '—'} quan sát · backend</small></article>
        <article className="vf-summary-card"><span>So với HAR-RV</span><strong className={relativeQlike != null && relativeQlike < 1 ? 'vf-good' : ''}>{relativeQlike == null ? '—' : ((1 - relativeQlike) * 100).toLocaleString('vi-VN', { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + '%'}</strong><small>QLIKE thấp hơn là tốt hơn</small></article>
        <article className="vf-summary-card"><span>DM p-value</span><strong>{fmt(dm?.p_value, 4)}</strong><small>{dm?.status ?? 'Chưa có kiểm định'}</small></article>
      </div>

      <section className="vf-panel">
        <PanelTitle icon={<BarChart3 size={17}/>} title="So sánh mô hình out-of-sample" subtitle="Chỉ số trả về từ dashboard/overview API · cùng mẫu đánh giá" badge={'N = ' + (selectedMetrics?.n?.toLocaleString('vi-VN') ?? '—')}/>
        {sortedComparison.length ? <div className="vf-table-scroll"><table className="vf-table"><thead><tr><th>Mô hình</th><th>RMSE</th><th>MAE</th><th>QLIKE</th><th>QLIKE / HAR-RV</th><th>Số mẫu</th><th></th></tr></thead><tbody>{sortedComparison.map((row,index) => <tr key={row.model} className={row.model.toLowerCase() === effectiveModel.toLowerCase() ? 'selected' : ''}>
          <td><strong>{modelName(row.model)}</strong>{index === 0 && <span className="vf-best-tag">QLIKE thấp nhất</span>}</td><td>{fmt(row.RMSE, 4)}</td><td>{fmt(row.MAE, 4)}</td><td className={index === 0 ? 'vf-amber' : ''}>{fmt(row.QLIKE, 4)}</td><td>{row.QLIKE_relative_to_har == null ? '—' : fmt(row.QLIKE_relative_to_har, 3) + '×'}</td><td>{row.n?.toLocaleString('vi-VN') ?? '—'}</td><td><button className="vf-select-model" onClick={() => setSelectedModel(row.model)} aria-label={'Xem forecast của ' + modelName(row.model)}>Xem forecast</button></td>
        </tr>)}</tbody></table></div> : <EmptyState loading={overview.isLoading} error={overview.error}/>}
      </section>

      <div className="vf-chart-grid">
        <section className="vf-panel vf-chart-panel">
          <div className="vf-panel-heading-row"><PanelTitle icon={<Activity size={17}/>} title="Dự báo và RV thực tế" subtitle={'Độ biến động (%) · ' + selectedName + ' và observed RV'} badge={'Horizon ' + horizonDays + 'D'}/>
            <div className="vf-chart-tools"><div className="vf-range-picker">{(['3M','6M','1Y','ALL'] as RangeKey[]).map(key => <button key={key} className={range === key ? 'active' : ''} onClick={() => setRange(key)}>{key === 'ALL' ? 'Tất cả' : key}</button>)}</div><button className="vf-icon-button" onClick={exportForecastCsv} title="Tải forecast CSV"><Download size={15}/></button></div>
          </div>
          <div className="vf-chart">{visibleChartRows.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={visibleChartRows} margin={{top:10,right:10,bottom:0,left:0}}><CartesianGrid stroke="#21344b" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="date" tickFormatter={(v:string)=>v.slice(0,7)} tick={{fill:'#90a2b8',fontSize:11}} tickLine={false} axisLine={false} minTickGap={34}/><YAxis tick={{fill:'#90a2b8',fontSize:11}} tickLine={false} axisLine={false} width={48} tickFormatter={(v:number)=>fmt(v,1)+'%'}/><Tooltip labelFormatter={v=>'Ngày '+String(v)} formatter={(v,n)=>[fmt(Number(v),3)+'%',n==='forecastVol'?'Dự báo':'RV thực tế']} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:8,color:'#e7edf6',fontSize:12}}/><Legend formatter={(value)=>value==='forecastVol'?'Dự báo':'RV thực tế'} wrapperStyle={{fontSize:11,color:'#a9b8cb'}}/><Line type="monotone" dataKey="actualVol" name="RV thực tế" stroke="#c7d4e3" strokeWidth={2} dot={false} connectNulls={false}/><Line type="monotone" dataKey="forecastVol" name="forecastVol" stroke="#f0a51c" strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls={false}/></LineChart></ResponsiveContainer> : <EmptyState loading={selectedForecasts.isLoading || market.isLoading} error={selectedForecasts.error ?? market.error}/>}</div>
          <p className="vf-chart-foot">Forecast variance và actual RV lấy từ API; biểu diễn √RV theo đơn vị phần trăm. Khoảng hiển thị lọc trên ngày target.</p>
        </section>

        <section className="vf-panel vf-model-detail">
          <PanelTitle icon={<Target size={17}/>} title="Chi tiết model đang xem" subtitle="Metrics và kiểm định từ backend" badge={horizonDays + ' ngày'}/>
          <div className="vf-model-name"><span>MÔ HÌNH</span><strong>{selectedName}</strong></div>
          <div className="vf-detail-list"><div><span>RMSE</span><strong>{fmt(selectedMetrics?.RMSE, 4)}</strong></div><div><span>MAE</span><strong>{fmt(selectedMetrics?.MAE, 4)}</strong></div><div><span>QLIKE</span><strong>{fmt(selectedMetrics?.QLIKE, 4)}</strong></div><div><span>DM p-value vs HAR-RV</span><strong>{fmt(dm?.p_value, 4)}</strong></div><div><span>Forecast mới nhất</span><strong>{latestForecast ? dateKey(latestForecast.target_date) : '—'}</strong></div></div>
          <p className="vf-model-note">Số liệu đánh giá giữ nguyên theo response API; chọn một hàng trong bảng để xem chuỗi dự báo của model đó.</p>
        </section>
      </div>

      <section className="vf-panel">
        <div className="vf-panel-heading-row"><PanelTitle icon={<Database size={17}/>} title="10 forecast gần nhất" subtitle="Ghép forecast với RV thực tế theo target date" badge={selectedName}/><button className="vf-download-button" onClick={exportForecastCsv}><Download size={14}/> CSV</button></div>
        {recent.length ? <div className="vf-table-scroll"><table className="vf-table vf-recent-table"><thead><tr><th>Ngày dự báo</th><th>Target</th><th>Regime</th><th>RV forecast (%²)</th><th>Vol forecast (%)</th><th>RV thực tế (%²)</th><th>Status</th></tr></thead><tbody>{recent.map(item=>{const target=marketByTarget.get(dateKey(item.target_date));const actual=varianceActual(target,horizonDays);return <tr key={item.origin_date+item.target_date}><td>{dateKey(item.origin_date)}</td><td>{dateKey(item.target_date)}</td><td><span className="vf-regime-label" style={{'--regime-color':REGIME_COLORS[target?.regime?.toLowerCase() ?? 'normal']} as CSSProperties}>{target?.regime ?? '—'}</span></td><td>{fmt(item.rv_forecast_pct2,3)}</td><td>{fmt(item.volatility_forecast_pct,3)}</td><td>{fmt(actual,3)}</td><td><span className={item.status === 'ok' ? 'vf-status-ok' : 'vf-status-warn'}>{item.status || '—'}</span></td></tr>})}</tbody></table></div> : <EmptyState loading={selectedForecasts.isLoading} error={selectedForecasts.error}/>}
      </section>
    </div>}

    {activeTab === 'rq2' && <RQ2Results symbol={symbol} horizonDays={horizonDays}/>}
    {activeTab === 'rq3' && <RQ3Results symbol={symbol} horizonDays={horizonDays}/>}
  </div>
}

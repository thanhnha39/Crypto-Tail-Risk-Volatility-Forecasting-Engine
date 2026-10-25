import { useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Activity, BarChart3, Database, Download, Layers, Target, TrendingUp } from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useDashboardOverview, useForecasts, useMarket } from '../../lib/dashboardQueries'
import type { DashboardSample, MarketPoint } from '../../lib/api'
import { RQ2Results, RQ3Results } from './ResearchSections'
import './volatility-forecast.css'

type SymbolCode = 'BTCUSDT' | 'ETHUSDT'
type HorizonDays = 1 | 7
type ResearchTab = 'rq1' | 'rq2' | 'rq3'
type RangeKey = '3M' | '6M' | '1Y' | 'ALL'

const RANGE_DAYS: Record<RangeKey, number> = { '3M': 92, '6M': 183, '1Y': 365, ALL: Infinity }
const REGIME_COLORS: Record<string, string> = { normal: '#91a4bc', bull: '#45c39f', bear: '#f0ad36', crisis: '#ed8181' }
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

export default function VolatilityForecastTab({ symbol = 'BTCUSDT', horizonDays = 1, sample = 'evaluation' }: { symbol?: SymbolCode; horizonDays?: HorizonDays; sample?: DashboardSample }) {
  const [activeTab, setActiveTab] = useState<ResearchTab>('rq1')
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [range, setRange] = useState<RangeKey>('1Y')
  const overview = useDashboardOverview(symbol, horizonDays, sample)
  const market = useMarket(symbol, 3000)
  const effectiveModel = selectedModel ?? overview.data?.best_model?.model ?? 'enet'
  const selectedForecasts = useForecasts(symbol, effectiveModel, horizonDays, 3000, sample)
  const harForecasts = useForecasts(symbol, 'har_rv', horizonDays, 3000, sample)

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
  const sortedHarForecasts = useMemo(
    () => [...(harForecasts.data?.items ?? [])].sort((a, b) => a.target_date.localeCompare(b.target_date)),
    [harForecasts.data],
  )
  const harByTarget = useMemo(
    () => new Map(sortedHarForecasts.map(item => [dateKey(item.target_date), item])),
    [sortedHarForecasts],
  )
  const chartRows = useMemo(() => sortedForecasts.flatMap(item => {
    const actualPoint = marketByTarget.get(dateKey(item.target_date))
    const actualVariance = actualPoint ? varianceActual(actualPoint, horizonDays) : null
    const harVariance = harByTarget.get(dateKey(item.target_date))?.rv_forecast_pct2
    const forecastVol = item.volatility_forecast_pct
    const actualVol = typeof actualVariance === 'number' && actualVariance >= 0 ? Math.sqrt(actualVariance) : null
    const harVol = typeof harVariance === 'number' && harVariance >= 0 ? Math.sqrt(harVariance) : null
    if (forecastVol == null && actualVol == null && harVol == null) return []
    return [{
      date: dateKey(item.target_date),
      forecastVol,
      actualVol,
      harVol,
      forecastVariance: item.rv_forecast_pct2,
      regime: actualPoint?.regime?.toLowerCase() ?? 'normal',
    }]
  }), [sortedForecasts, marketByTarget, harByTarget, horizonDays])
  const visibleChartRows = useMemo(() => {
    if (!chartRows.length || range === 'ALL') return chartRows
    const latest = new Date(chartRows[chartRows.length - 1].date).getTime()
    const cutoff = latest - RANGE_DAYS[range] * 86400000
    return chartRows.filter(row => new Date(row.date).getTime() >= cutoff)
  }, [chartRows, range])

  const comparison = overview.data?.comparison ?? []
  const sortedComparison = useMemo(() => [...comparison].sort((a, b) => (a.QLIKE ?? Infinity) - (b.QLIKE ?? Infinity)), [comparison])
  const bestModel = overview.data?.best_model
  const bestMetrics = bestModel
    ? comparison.find(row => row.model.toLowerCase() === bestModel.model.toLowerCase())
    : undefined
  const bestMlModel = sortedComparison.find(row => ['enet', 'xgboost'].includes(row.model.toLowerCase()))
  const harModelMetrics = comparison.find(row => row.model.toLowerCase() === 'har_rv')
  const garchModelMetrics = comparison.find(row => row.model.toLowerCase() === 'garch')
  const mlBeatsHar = bestMlModel?.QLIKE != null && harModelMetrics?.QLIKE != null && bestMlModel.QLIKE < harModelMetrics.QLIKE
  const mlBeatsGarch = bestMlModel?.QLIKE != null && garchModelMetrics?.QLIKE != null && bestMlModel.QLIKE < garchModelMetrics.QLIKE
  const mlSignificantlyBeatsHar = bestMlModel?.dm_p_value != null
    && bestMlModel.dm_p_value < 0.05
    && bestMlModel.dm_mean_diff != null
    && bestMlModel.dm_mean_diff < 0
  const researchConclusion = !bestMlModel
    ? 'Chưa đủ dữ liệu'
    : mlBeatsHar && mlBeatsGarch && mlSignificantlyBeatsHar
      ? 'Ủng hộ'
      : mlBeatsHar || mlBeatsGarch
        ? 'Ủng hộ một phần'
        : 'Chưa ủng hộ'
  const recent = [...sortedForecasts].reverse().slice(0, 10)
  const selectedName = modelName(effectiveModel)
  const pairedQlikeRows = useMemo(() => {
    return sortedForecasts.flatMap(item => {
      const actual = varianceActual(marketByTarget.get(dateKey(item.target_date)), horizonDays)
      const harForecast = harByTarget.get(dateKey(item.target_date))?.rv_forecast_pct2
      const forecast = item.rv_forecast_pct2
      if (
        typeof actual !== 'number' || actual <= 0 ||
        typeof forecast !== 'number' || forecast <= 0 ||
        typeof harForecast !== 'number' || harForecast <= 0
      ) return []
      const loss = (prediction: number) => {
        const ratio = actual / prediction
        return ratio - Math.log(ratio) - 1
      }
      return [{ date: dateKey(item.target_date), modelQlike: loss(forecast), harQlike: loss(harForecast) }]
    })
  }, [sortedForecasts, marketByTarget, harByTarget, horizonDays])
  const rollingQlikeRows = useMemo(() => pairedQlikeRows.flatMap((_, index) => {
    const windowRows = pairedQlikeRows.slice(Math.max(0, index - 59), index + 1)
    if (windowRows.length < 60) return []
    return [{
      date: pairedQlikeRows[index].date,
      modelQlike: windowRows.reduce((sum, row) => sum + row.modelQlike, 0) / windowRows.length,
      harQlike: windowRows.reduce((sum, row) => sum + row.harQlike, 0) / windowRows.length,
    }]
  }), [pairedQlikeRows])
  const modelMeanQlike = pairedQlikeRows.length
    ? pairedQlikeRows.reduce((sum, row) => sum + row.modelQlike, 0) / pairedQlikeRows.length
    : null
  const harMeanQlike = pairedQlikeRows.length
    ? pairedQlikeRows.reduce((sum, row) => sum + row.harQlike, 0) / pairedQlikeRows.length
    : null
  const qlikeDeltaPct = modelMeanQlike != null && harMeanQlike != null && harMeanQlike !== 0
    ? (modelMeanQlike / harMeanQlike - 1) * 100
    : null
  const isLoading = overview.isLoading || selectedForecasts.isLoading || market.isLoading || harForecasts.isLoading
  const hasError = overview.error ?? selectedForecasts.error ?? market.error ?? harForecasts.error

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
        <div><h2>Mô hình ML/DL có dự báo RV tốt hơn GARCH và HAR-RV không?</h2><p>{symbol.replace('USDT', '')} · Horizon {horizonDays} ngày · {overview.data?.window ?? 'rolling'} · {sample === 'holdout' ? 'Holdout' : 'Evaluation'} · {overview.data?.evaluation_period ?? 'Đang tải kỳ đánh giá'}</p></div>
        <span className="vf-answer-badge"><Target size={15}/>{bestMlModel ? `Kết luận: ${researchConclusion}` : 'Đang tải kết quả'}</span>
      </section>

      <div className="vf-rq1-summary-grid">
        <section className="vf-panel">
          <PanelTitle icon={<BarChart3 size={17}/>} title="Bảng so sánh mô hình out-of-sample" subtitle={`${symbol.replace('USDT', '')}/USD · ${overview.data?.window ?? 'rolling'} · horizon ${horizonDays} ngày · số liệu ${sample === 'holdout' ? 'holdout' : 'evaluation'} thực tế`} badge={'N = ' + (bestModel?.n?.toLocaleString('vi-VN') ?? '—')}/>
          {sortedComparison.length ? <div className="vf-table-scroll"><table className="vf-table vf-rq1-table"><thead><tr><th>Mô hình</th><th>RMSE</th><th>MAE</th><th>QLIKE</th><th>Δ QLIKE vs HAR-RV</th><th>DM p-value</th><th></th></tr></thead><tbody>{sortedComparison.map((row,index) => {
            const deltaPct = row.QLIKE_relative_to_har == null ? null : (row.QLIKE_relative_to_har - 1) * 100
            const isBaseline = row.model.toLowerCase() === 'har_rv'
            const dmIsSignificant = row.dm_p_value != null && row.dm_p_value < 0.05
            return <tr key={row.model} className={`${row.model.toLowerCase() === effectiveModel.toLowerCase() ? 'selected' : ''} ${index === 0 ? 'vf-rq1-best-row' : isBaseline ? 'vf-rq1-baseline-row' : ''}`}>
              <td><strong>{modelName(row.model)}</strong>{index === 0 && <span className="vf-best-tag">QLIKE thấp nhất</span>}{isBaseline && <span className="vf-baseline-tag">Nền</span>}</td>
              <td>{fmt(row.RMSE, 4)}</td><td>{fmt(row.MAE, 4)}</td><td className={index === 0 ? 'vf-amber' : ''}>{fmt(row.QLIKE, 4)}</td>
              <td className={deltaPct == null ? '' : deltaPct < 0 ? 'vf-good' : deltaPct > 0 ? 'vf-amber' : ''}>{deltaPct == null ? '—' : `${deltaPct < 0 ? '▼ ' : deltaPct > 0 ? '▲ +' : ''}${fmt(Math.abs(deltaPct), 1)}%`}</td>
              <td>{isBaseline ? '— (nền)' : row.dm_p_value == null ? '—' : <span className={dmIsSignificant ? 'vf-significant' : ''}>{fmt(row.dm_p_value, 3)}{dmIsSignificant ? ' **' : ''}</span>}</td>
              <td><button className="vf-select-model" onClick={() => setSelectedModel(row.model)} aria-label={'Xem forecast của ' + modelName(row.model)}>Xem</button></td>
            </tr>
          })}</tbody></table></div> : <EmptyState loading={overview.isLoading} error={overview.error}/>}
          <div className="vf-rq1-table-foot"><span><strong>QLIKE thấp hơn là tốt hơn.</strong> Δ âm: tốt hơn HAR-RV. DM p &lt; 0,05: khác biệt có ý nghĩa thống kê.</span><span>DM test với hiệu chỉnh HLN.</span></div>
        </section>

        <section className="vf-panel vf-rq1-best-panel">
          <div className="vf-panel-title"><div className="vf-title-icon"><Target size={17}/></div><div className="vf-title-copy"><h3>Mô hình tối ưu ({horizonDays} ngày)</h3><p>Kết quả theo QLIKE trên mẫu đang chọn</p></div><button className="vf-icon-button" onClick={exportForecastCsv} title="Tải forecast CSV"><Download size={15}/></button></div>
          {bestModel ? <>
            <div className="vf-rq1-best-name"><span>MÔ HÌNH TỐT NHẤT</span><strong>{modelName(bestModel.model)}</strong><small>{bestModel.n?.toLocaleString('vi-VN') ?? '—'} quan sát out-of-sample</small></div>
            <div className="vf-detail-list">
              <div><span>RMSE out-of-sample</span><strong>{fmt(bestModel.RMSE, 4)}</strong></div>
              <div><span>MAE out-of-sample</span><strong>{fmt(bestModel.MAE, 4)}</strong></div>
              <div><span>QLIKE out-of-sample</span><strong className="vf-amber">{fmt(bestModel.QLIKE, 4)}</strong></div>
              <div><span>DM p-value vs HAR-RV</span><strong>{bestMetrics?.dm_p_value == null ? '—' : `${fmt(bestMetrics.dm_p_value, 3)}${bestMetrics.dm_p_value < 0.05 ? ' **' : ''}`}</strong></div>
              <div><span>Δ QLIKE vs HAR-RV</span><strong className={bestModel.QLIKE_relative_to_har != null && bestModel.QLIKE_relative_to_har < 1 ? 'vf-good' : ''}>{bestModel.QLIKE_relative_to_har == null ? '—' : `${((bestModel.QLIKE_relative_to_har - 1) * 100).toLocaleString('vi-VN', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`}</strong></div>
            </div>
            <p className="vf-model-note">
              {bestMetrics?.dm_p_value == null
                ? 'Backend chưa cung cấp kiểm định DM cho cấu hình này.'
                : bestMetrics.dm_p_value < 0.05
                  ? 'Khác biệt QLIKE so với HAR-RV có ý nghĩa thống kê theo DM test (HLN).'
                  : 'Chưa đủ bằng chứng thống kê để kết luận QLIKE khác HAR-RV (DM test, HLN).'}
            </p>
          </> : <EmptyState loading={overview.isLoading} error={overview.error}/>}
        </section>
      </div>

      <div className="vf-chart-grid">
        <section className="vf-panel vf-chart-panel">
          <div className="vf-panel-heading-row"><PanelTitle icon={<Activity size={17}/>} title="Dự báo và RV thực tế" subtitle={'Độ biến động (%) · ' + selectedName + ' so với HAR-RV'} badge={'Horizon ' + horizonDays + 'D'}/>
            <div className="vf-chart-tools"><div className="vf-range-picker">{(['3M','6M','1Y','ALL'] as RangeKey[]).map(key => <button key={key} className={range === key ? 'active' : ''} onClick={() => setRange(key)}>{key === 'ALL' ? 'Tất cả' : key}</button>)}</div><button className="vf-icon-button" onClick={exportForecastCsv} title="Tải forecast CSV"><Download size={15}/></button></div>
          </div>
          <div className="vf-chart">{visibleChartRows.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={visibleChartRows} margin={{top:10,right:10,bottom:0,left:0}}><CartesianGrid stroke="#21344b" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="date" tickFormatter={(v:string)=>v.slice(0,7)} tick={{fill:'#90a2b8',fontSize:11}} tickLine={false} axisLine={false} minTickGap={34}/><YAxis tick={{fill:'#90a2b8',fontSize:11}} tickLine={false} axisLine={false} width={48} tickFormatter={(v:number)=>fmt(v,1)+'%'}/><Tooltip labelFormatter={v=>'Ngày '+String(v)} formatter={(v,n)=>[fmt(Number(v),3)+'%',n==='forecastVol'?selectedName:n==='harVol'?'HAR-RV':'RV thực tế']} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:8,color:'#e7edf6',fontSize:12}}/><Legend formatter={(value)=>value==='forecastVol'?selectedName:value==='harVol'?'HAR-RV':'RV thực tế'} wrapperStyle={{fontSize:11,color:'#a9b8cb'}}/><Line type="monotone" dataKey="actualVol" name="RV thực tế" stroke="#e5edf6" strokeWidth={2.2} dot={false} connectNulls={false}/><Line type="monotone" dataKey="forecastVol" name="forecastVol" stroke="#f0ad36" strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls={false}/><Line type="monotone" dataKey="harVol" name="harVol" stroke="#8393a8" strokeWidth={1.7} strokeDasharray="2 4" dot={false} connectNulls={false}/></LineChart></ResponsiveContainer> : <EmptyState loading={selectedForecasts.isLoading || market.isLoading} error={selectedForecasts.error ?? market.error}/>}</div>
          <p className="vf-chart-foot">RV thực tế lấy từ dữ liệu quan sát; hai đường dự báo lấy từ forecast của mô hình đang xem và HAR-RV, ghép theo target date.</p>
        </section>

        <section className="vf-panel vf-chart-panel">
          <PanelTitle icon={<Activity size={17}/>} title="Rolling QLIKE (cửa sổ 60 mẫu)" subtitle="QLIKE tính từ RV thực tế và forecast variance ghép cùng target date" badge={rollingQlikeRows.length ? 'So sánh với HAR-RV' : undefined}/>
          <div className="vf-chart">{rollingQlikeRows.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={rollingQlikeRows} margin={{top:10,right:10,bottom:0,left:0}}><CartesianGrid stroke="#21344b" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="date" tickFormatter={(v:string)=>v.slice(0,7)} tick={{fill:'#90a2b8',fontSize:10}} tickLine={false} axisLine={false} minTickGap={30}/><YAxis tick={{fill:'#90a2b8',fontSize:10}} tickLine={false} axisLine={false} width={42} tickFormatter={(v:number)=>fmt(v,2)}/><Tooltip labelFormatter={v=>'Ngày '+String(v)} formatter={(v,n)=>[fmt(Number(v),4),n==='modelQlike'?selectedName:'HAR-RV']} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:8,color:'#e7edf6',fontSize:12}}/><Legend formatter={(value)=>value==='modelQlike'?selectedName:'HAR-RV'} wrapperStyle={{fontSize:11,color:'#a9b8cb'}}/><Line type="monotone" dataKey="modelQlike" name="modelQlike" stroke="#f0ad36" strokeWidth={2} strokeDasharray="5 3" dot={false}/><Line type="monotone" dataKey="harQlike" name="harQlike" stroke="#93a3b8" strokeWidth={1.8} dot={false}/></LineChart></ResponsiveContainer> : <EmptyState loading={selectedForecasts.isLoading || harForecasts.isLoading || market.isLoading} error={selectedForecasts.error ?? harForecasts.error ?? market.error}/>}</div>
          <div className="vf-rolling-summary">
            <span>QLIKE trung bình (N={pairedQlikeRows.length.toLocaleString('vi-VN')}): <strong>{fmt(modelMeanQlike, 4)}</strong> · HAR-RV: <strong>{fmt(harMeanQlike, 4)}</strong></span>
            <span>{qlikeDeltaPct == null ? 'Chưa đủ dữ liệu so sánh' : `${qlikeDeltaPct < 0 ? 'Thấp hơn' : qlikeDeltaPct > 0 ? 'Cao hơn' : 'Bằng'} HAR-RV ${fmt(Math.abs(qlikeDeltaPct), 1)}%`}</span>
          </div>
          <p className="vf-chart-foot">Đường rolling dùng trung bình QLIKE trên 60 quan sát paired liên tiếp; không dùng số liệu minh họa.</p>
        </section>
      </div>

      <section className="vf-panel">
        <div className="vf-panel-heading-row"><PanelTitle icon={<Database size={17}/>} title="10 ngày dự báo gần nhất (out-of-sample)" subtitle="Dự báo và RV thực tế được ghép theo target date từ backend" badge={selectedName}/><button className="vf-download-button" onClick={exportForecastCsv}><Download size={14}/> CSV</button></div>
        {recent.length ? <div className="vf-table-scroll"><table className="vf-table vf-recent-table"><thead><tr><th>Ngày dự báo</th><th>Target</th><th>Regime</th><th>RV forecast (%²)</th><th>Vol forecast (%)</th><th>RV thực tế (%²)</th><th>Status</th></tr></thead><tbody>{recent.map(item=>{const target=marketByTarget.get(dateKey(item.target_date));const actual=varianceActual(target,horizonDays);return <tr key={item.origin_date+item.target_date}><td>{dateKey(item.origin_date)}</td><td>{dateKey(item.target_date)}</td><td><span className="vf-regime-label" style={{'--regime-color':REGIME_COLORS[target?.regime?.toLowerCase() ?? 'normal']} as CSSProperties}>{target?.regime ?? '—'}</span></td><td>{fmt(item.rv_forecast_pct2,3)}</td><td>{fmt(item.volatility_forecast_pct,3)}</td><td>{fmt(actual,3)}</td><td><span className={item.status === 'ok' ? 'vf-status-ok' : 'vf-status-warn'}>{item.status || '—'}</span></td></tr>})}</tbody></table></div> : <EmptyState loading={selectedForecasts.isLoading} error={selectedForecasts.error}/>}
      </section>
    </div>}

    {activeTab === 'rq2' && <RQ2Results symbol={symbol} horizonDays={horizonDays} sample={sample}/>}
    {activeTab === 'rq3' && <RQ3Results symbol={symbol} horizonDays={horizonDays} sample={sample}/>}
  </div>
}

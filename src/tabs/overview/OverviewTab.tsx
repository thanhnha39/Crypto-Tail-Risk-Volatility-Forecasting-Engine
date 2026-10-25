import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Disc,
  Download,
  Flame,
  Info,
  Shield,
  Table as TableIcon,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  api,
  apiPaths,
  type CrisisBacktestPoint,
  type DashboardSample,
  type OverviewResponse,
} from '../../lib/api'
import { dashboardWindow, useForecasts, useMarket } from '../../lib/dashboardQueries'
import heroCryptoImg from '../../assets/hero-background.png'
import './overview.css'

interface OverviewTabProps {
  symbol: 'BTCUSDT' | 'ETHUSDT'
  horizonDays: 1 | 7
  sample: DashboardSample
  onNavigateTab?: (tab: string) => void
}

type Timeframe = '3M' | '6M' | '1Y' | 'ALL'

const crisisChartWidth = 320
const crisisChartHeight = 80

function crisisChartYDomain(points: CrisisBacktestPoint[]) {
  const values = points.flatMap((point) => [point.return, point.var]).filter((value): value is number => value != null)
  if (values.length === 0) return { min: -1, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const padding = Math.max((max - min) * 0.1, 0.1)
  return { min: min - padding, max: max + padding }
}

function crisisChartPath(
  points: CrisisBacktestPoint[],
  valueFor: (point: CrisisBacktestPoint) => number | null,
  domain: { min: number; max: number },
) {
  let path = ''
  let segmentStarted = false
  const innerWidth = crisisChartWidth - 20
  const innerHeight = crisisChartHeight - 14

  points.forEach((point, index) => {
    const value = valueFor(point)
    if (value == null) {
      segmentStarted = false
      return
    }

    const x = 10 + (index / Math.max(points.length - 1, 1)) * innerWidth
    const y = 7 + ((domain.max - value) / (domain.max - domain.min)) * innerHeight
    path += `${segmentStarted ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)} `
    segmentStarted = true
  })

  return path.trim()
}

export default function OverviewTab({ symbol, horizonDays, sample, onNavigateTab }: OverviewTabProps) {
  const [timeframe, setTimeframe] = useState<Timeframe>('6M')
  const [showTable, setShowTable] = useState(false)

  const overview = useQuery({
    queryKey: ['dashboard-overview', symbol, dashboardWindow, horizonDays, sample],
    queryFn: async () =>
      (
        await api.get<OverviewResponse>(apiPaths.overview, {
          params: { symbol, model: 'best', window: dashboardWindow, horizon_days: horizonDays, sample },
        })
      ).data,
  })

  const data = overview.data
  const market = useMarket(symbol, 3000)
  const forecasts = useForecasts(symbol, data?.model ?? 'xgboost', horizonDays, 3000, sample)

  const risk95 = data?.latest_risk?.alpha_95
  const risk99 = data?.latest_risk?.alpha_99
  const backtest99 = data?.risk_backtest?.find((row) => row.alpha === 0.01)

  // Format dates to DD/MM/YYYY
  const formatDateDMY = (dateStr?: string | null) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    if (Number.isNaN(d.getTime())) {
      const parts = dateStr.slice(0, 10).split('-')
      if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`
      return '—'
    }
    const day = String(d.getUTCDate()).padStart(2, '0')
    const month = String(d.getUTCMonth() + 1).padStart(2, '0')
    const year = d.getUTCFullYear()
    return `${day}/${month}/${year}`
  }

  const forecastDate = formatDateDMY(data?.latest_forecast?.target_date)
  const originDate = formatDateDMY(data?.latest_forecast?.origin_date)

  // Best model formatting
  const rawModelName = data?.best_model?.model ?? data?.model ?? '—'
  const bestName = rawModelName.toLowerCase().includes('xgboost')
    ? 'XGBoost'
    : rawModelName.toLowerCase().includes('har')
    ? 'HAR-RV'
    : rawModelName.toUpperCase().replace('_', ' ')

  const qlikeReduction = data?.best_model?.QLIKE_relative_to_har != null
    ? (1 - data.best_model.QLIKE_relative_to_har) * 100
    : null

  const breachRateDisplay = backtest99 ? (backtest99.breach_rate * 100).toFixed(1) : '—'

  // Chart data preparation
  const chartData = useMemo(() => {
    const isWeekly = horizonDays === 7
    const series = market.data?.series ?? []
    const forecastItems = forecasts.data?.items ?? []

    const actualMap = new Map<string, { rv: number | null; regime: string }>()
    const regimeByDate = new Map<string, string>()
    for (const point of series) {
      regimeByDate.set(point.origin_date.slice(0, 10), point.regime)
      const key = (isWeekly ? point.target_end_h7 : point.target_end_h1)?.slice(0, 10) ?? ''
      if (key) {
        actualMap.set(key, {
          rv: isWeekly ? point.y_rv_h7 : point.y_rv_h1,
          regime: point.regime || 'Normal',
        })
      }
    }

    const points = forecastItems
      .map((item) => {
        const dateKey = item.target_date.slice(0, 10)
        const actualInfo = actualMap.get(dateKey)
        const d = new Date(item.target_date)
        const m = String(d.getUTCMonth() + 1).padStart(2, '0')
        const y = String(d.getUTCFullYear()).slice(2)
        const regime = regimeByDate.get(dateKey) ?? actualInfo?.regime ?? ''
        const labelRegime =
          regime.toLowerCase() === 'bull'
            ? ' (Bull)'
            : regime.toLowerCase() === 'bear'
            ? ' (Bear)'
            : regime.toLowerCase() === 'crisis'
            ? ' (Crisis)'
            : ''

        return {
          date: dateKey,
          label: `T${m}/${y}${labelRegime}`,
          actual: actualInfo?.rv != null ? Number(Math.sqrt(Math.max(actualInfo.rv, 0)).toFixed(2)) : null,
          forecast: item.volatility_forecast_pct != null ? Number(item.volatility_forecast_pct.toFixed(2)) : null,
          regime,
        }
      })
      .filter((p) => p.actual != null || p.forecast != null)

    if (timeframe === 'ALL' || points.length === 0) return points
    const months = timeframe === '3M' ? 3 : timeframe === '6M' ? 6 : 12
    const cutoff = new Date(`${points[points.length - 1].date}T00:00:00Z`)
    cutoff.setUTCMonth(cutoff.getUTCMonth() - months)
    return points.filter((point) => new Date(`${point.date}T00:00:00Z`) >= cutoff)
  }, [forecasts.data, horizonDays, market.data, timeframe])

  // Download chart data as CSV
  const handleExportChartCsv = () => {
    const headers = ['Date', 'Label', 'Actual_RV_pct', 'Forecast_RV_pct', 'Regime']
    const rows = chartData.map((d) => [
      d.date,
      `"${d.label}"`,
      d.actual ?? '',
      d.forecast ?? '',
      d.regime,
    ])
    const csvContent =
      'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `${symbol}_realized_vs_forecast_${timeframe}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Model comparison rankings for QLIKE loss
  const modelRankings = useMemo(() => {
    const rawList = data?.comparison ?? []
    return rawList.filter((item) => item.QLIKE != null).slice(0, 3).map((item, index) => ({
        rank: index + 1,
        name:
          item.model.toLowerCase() === 'xgboost'
            ? 'XGBoost'
            : item.model.toLowerCase() === 'har_rv'
            ? 'HAR-RV'
            : item.model.toLowerCase() === 'garch'
            ? 'GARCH(1,1)'
            : item.model.toUpperCase().replace('_', ' '),
        qlike: item.QLIKE,
      }))
  }, [data?.comparison])

  const dmPValue = data?.qlike_dm_vs_har?.p_value ?? null

  const crisisNames: Record<string, string> = {
    may_2021_selloff: '\u0042\u00e1\u006e \u0074\u0068\u00e1\u006f \u0074\u0068\u00e1\u006e\u0067 \u0035\u002f\u0032\u0030\u0032\u0031',
    luna_collapse_2022: 'Luna m\u1ea5t neo',
    ftx_collapse_2022: 'Thanh kho\u1ea3n FTX',
  }
  const crisisEvents = data?.crisis_backtest ?? []

  return (
    <div className="overview-tab-container">
      {/* 1. HERO SECTION */}
      <section className="overview-hero-card">
        <div className="hero-left-content">
          <span className="hero-kicker-tag">Dự báo out-of-sample</span>
          <h2 className="hero-main-title">Đo lường <em>rủi ro</em><br />tiền mã hóa</h2>
          <p className="hero-sub-title">Dự báo biến động và rủi ro đuôi cho {symbol === 'BTCUSDT' ? 'BTC' : 'ETH'}</p>

          <div className="hero-metric-row">
            <div className="hero-big-stat">
              <strong>
                {data?.latest_forecast?.volatility_forecast_pct != null
                  ? (data.latest_forecast.volatility_forecast_pct.toFixed(1) + '%')
                  : '—'}
              </strong>
              <div className="hero-stat-desc">
                <span>Biến động dự báo cho ngày</span>
                <span>{forecastDate}</span>
                <small>Ngày lập dự báo: {originDate}</small>
              </div>
            </div>

            <div className="hero-divider-line" />

            <div className="hero-regime-pill">
              <span className="regime-dot-circle" />
              <span>Trạng thái: <strong>{data?.forecast_origin_regime ?? '—'}</strong></span>
            </div>

            <div className="hero-var-reading">
              <span>VaR 99%:</span>
              <strong className="var-negative-val">
                {risk99?.var != null ? (risk99.var.toFixed(1) + '%') : '—'}
              </strong>
            </div>
          </div>
        </div>

        <div className="hero-right-crypto-banner">
          <img src={heroCryptoImg} alt="Đ\u1ed3 h\u1ecda th\u1ecb tr\u01b0\u1eddng crypto v\u1edbi BTC v\u00e0 ETH" className="crypto-hero-img" />
        </div>
      </section>

      {/* 2. YELLOW HIGHLIGHT CONCLUSION STRIP */}
      <div className="overview-conclusion-strip">
        <Info size={16} className="conclusion-info-icon" />
        <p>
          <strong>Kết luận chính:</strong> {bestName} có QLIKE {qlikeReduction == null ? '—' : `thấp hơn HAR-RV ${qlikeReduction.toFixed(1)}%`}; VaR 99% vi phạm {backtest99 ? `${backtest99.n_breach}/${backtest99.n} ngày (${breachRateDisplay}%)` : '—'} (kỳ vọng 1%).
        </p>
      </div>

      {/* 3. ROW OF 6 METRIC CARDS */}
      <div className="overview-metric-cards-row">
        {/* Card 1: VaR 95% */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">VAR 95%</span>
            <Shield size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value">
            {risk95?.var != null ? `${risk95.var.toFixed(1)}%` : '—'}
          </div>
          <div className="metric-box-note">Ngày {risk95?.date ? formatDateDMY(risk95.date) : '—'}</div>
        </div>

        {/* Card 2: VaR 99% */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">VAR 99%</span>
            <TriangleAlert size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value">
            {risk99?.var != null ? `${risk99.var.toFixed(1)}%` : '—'}
          </div>
          <div className="metric-box-note">Ngày {risk99?.date ? formatDateDMY(risk99.date) : '—'}</div>
        </div>

        {/* Card 3: Expected Shortfall 95% */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">EXPECTED SHORTFALL 95%</span>
            <BarChart3 size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value">
            {risk95?.es != null ? `${risk95.es.toFixed(1)}%` : '—'}
          </div>
          <div className="metric-box-note">Ngày {risk95?.date ? formatDateDMY(risk95.date) : '—'}</div>
        </div>

        {/* Card 4: Expected Shortfall 99% */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">EXPECTED SHORTFALL 99%</span>
            <Flame size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value">
            {risk99?.es != null ? `${risk99.es.toFixed(1)}%` : '—'}
          </div>
          <div className="metric-box-note">Ngày {risk99?.date ? formatDateDMY(risk99.date) : '—'}</div>
        </div>

        {/* Card 5: Biến động thực hiện */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">BIẾN ĐỘNG THỰC HIỆN</span>
            <TrendingUp size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value">
            {data?.latest_market?.realized_volatility_pct != null
              ? `${data.latest_market.realized_volatility_pct.toFixed(1)}%`
              : '—'}
          </div>
          <div className="metric-box-note">Lợi suất 5 phút · {data?.latest_market?.origin_date ? formatDateDMY(data.latest_market.origin_date) : '—'}</div>
        </div>

        {/* Card 6: Regime at the forecast origin */}
        <div className="metric-box">
          <div className="metric-box-top">
            <span className="metric-box-label">TRẠNG THÁI TẠI MỐC DỰ BÁO</span>
            <Disc size={16} className="metric-box-icon" />
          </div>
          <div className="metric-box-value serif-value">
            {data?.latest_market?.regime ?? '—'}
          </div>
          <div className="metric-box-note">Tại ngày lập dự báo {data?.latest_market?.origin_date ? formatDateDMY(data.latest_market.origin_date) : '—'}</div>
        </div>
      </div>

      {/* 4. MIDDLE SECTION: CHART + BEST MODEL RANKING */}
      <div className="overview-middle-grid">
        {/* Left Panel: Realized & Forecast Chart */}
        <section className="overview-panel chart-panel">
          <div className="panel-top-bar">
            <div>
              <h3 className="panel-title">Biến động thực hiện và dự báo (%)</h3>
              <p className="panel-subtitle">Dự báo trước một bước, mô hình tốt nhất theo QLIKE.</p>
            </div>
            <div className="chart-controls-group">
              <div className="timeframe-pill-selector">
                {(['3M', '6M', '1Y', 'ALL'] as Timeframe[]).map((tf) => (
                  <button
                    key={tf}
                    className={`tf-button ${timeframe === tf ? 'active' : ''}`}
                    onClick={() => setTimeframe(tf)}
                  >
                    {tf === '3M' ? '3T' : tf === '6M' ? '6T' : tf === '1Y' ? '1N' : 'Tất cả'}
                  </button>
                ))}
              </div>
              <button
                className={`panel-icon-btn ${showTable ? 'active' : ''}`}
                onClick={() => setShowTable(!showTable)}
                title="Xem dạng bảng"
              >
                <TableIcon size={14} />
              </button>
              <button
                className="panel-icon-btn"
                onClick={handleExportChartCsv}
                title="Tải dữ liệu chuỗi"
              >
                <Download size={14} />
              </button>
            </div>
          </div>

          {showTable ? (
            <div className="chart-table-view">
              <table>
                <thead>
                  <tr>
                    <th>NGÀY</th>
                    <th>THỜI ĐIỂM</th>
                    <th>BIẾN ĐỘNG THỰC HIỆN (%)</th>
                    <th>DỰ BÁO ({bestName}) (%)</th>
                    <th>TRẠNG THÁI</th>
                  </tr>
                </thead>
                <tbody>
                  {chartData.map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td>{row.label}</td>
                      <td>{row.actual != null ? `${row.actual}%` : '—'}</td>
                      <td>{row.forecast != null ? `${row.forecast}%` : '—'}</td>
                      <td>
                        <span className={`regime-tag regime-${row.regime.toLowerCase()}`}>
                          {row.regime}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="chart-canvas-container">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 20, right: 35, left: 10, bottom: 5 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} strokeDasharray="3 3" />
                  
                  {/* Regime vertical background highlight bands */}
                  {chartData.map((pt, idx) => {
                    const r = pt.regime.toLowerCase()
                    if (r === 'bull') {
                      return (
                        <ReferenceArea
                          key={`bull-${idx}`}
                          x1={pt.label}
                          x2={chartData[idx + 1]?.label ?? pt.label}
                          fill="#10b981"
                          fillOpacity={0.12}
                        />
                      )
                    }
                    if (r === 'bear') {
                      return (
                        <ReferenceArea
                          key={`bear-${idx}`}
                          x1={pt.label}
                          x2={chartData[idx + 1]?.label ?? pt.label}
                          fill="#ef4444"
                          fillOpacity={0.08}
                        />
                      )
                    }
                    if (r === 'crisis') {
                      return (
                        <ReferenceArea
                          key={`crisis-${idx}`}
                          x1={pt.label}
                          x2={chartData[idx + 1]?.label ?? pt.label}
                          fill="#dc2626"
                          fillOpacity={0.18}
                        />
                      )
                    }
                    return null
                  })}

                  <XAxis
                    dataKey="label"
                    stroke="#64748b"
                    tick={{ fill: '#8b9bb1', fontSize: 10 }}
                    tickLine={false}
                    axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
                  />
                  <YAxis
                    orientation="right"
                    stroke="#64748b"
                    tick={{ fill: '#8b9bb1', fontSize: 10 }}
                    tickFormatter={(val: number) => `${val.toFixed(1)}%`}
                    tickLine={false}
                    axisLine={false}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#09172a',
                      border: '1px solid #1e3a5f',
                      borderRadius: 8,
                      color: '#ffffff',
                      fontSize: 11,
                    }}
                    formatter={(val: number, name: string) => [
                      `${val}%`,
                      name === 'actual' ? 'Biến động thực hiện' : `Dự báo (${bestName})`,
                    ]}
                  />
                  {/* Actual realized volatility line */}
                  <Line
                    type="monotone"
                    dataKey="actual"
                    name="actual"
                    stroke="#ffffff"
                    strokeWidth={2}
                    dot={{ fill: '#ffffff', r: 3.5, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: '#ffffff' }}
                  />
                  {/* Forecast volatility line */}
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    name="forecast"
                    stroke="#efa51d"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ fill: '#efa51d', r: 2.5, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: '#efa51d' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Chart Legend */}
          <div className="chart-legend-row">
            <div className="legend-items-left">
              <span className="legend-item">
                <span className="legend-line-solid" />
                <span>Nét liền trắng (●): Biến động thực hiện</span>
              </span>
              <span className="legend-item">
                <span className="legend-line-dashed" />
                <span>Nét đứt vàng (■): Dự báo ({bestName})</span>
              </span>
            </div>
            <div className="regime-legend-dots">
              <span className="regime-dot-item">
                <i className="dot-normal" /> Normal
              </span>
              <span className="regime-dot-item">
                <i className="dot-bull" /> Bull
              </span>
              <span className="regime-dot-item">
                <i className="dot-bear" /> Bear
              </span>
              <span className="regime-dot-item">
                <i className="dot-crisis" /> Crisis
              </span>
            </div>
          </div>

          {/* Bottom Conclusion */}
          <div className="chart-conclusion-footer">
            <CheckCircle2 size={15} className="conclusion-check-icon" />
            <p>
              <strong>Kết luận:</strong> Dự báo bám sát biến động thực hiện, khoảng lệch lớn nhất xuất hiện trong các đợt Crisis.
            </p>
          </div>
        </section>

        {/* Right Panel: Best Model (Out-of-sample) */}
        <section className="overview-panel best-model-panel">
          <div className="best-model-header">
            <span className="panel-kicker">GIAI ĐOẠN KIỂM ĐỊNH</span>
            <h3 className="panel-title">Mô hình tốt nhất (Out-of-sample)</h3>
          </div>

          {/* Top highlight card */}
          <div className="leading-model-card">
            <div className="leading-col-left">
              <span className="leading-label">MÔ HÌNH DẪN ĐẦU</span>
              <strong className="leading-name">{bestName}</strong>
            </div>
            <div className="leading-col-right">
              <span className="leading-label-right">QLIKE THẤP NHẤT</span>
              <strong className="leading-score">
                {data?.best_model?.QLIKE != null ? data.best_model.QLIKE.toFixed(3) : '—'}
              </strong>
            </div>
          </div>

          {/* Rankings section */}
          <div className="loss-ranking-section">
            <h4 className="loss-ranking-title">XẾP HẠNG ĐỘ MẤT MÁT QLIKE</h4>
            <div className="loss-ranking-list">
              {modelRankings.map((m) => {
                const isFirst = m.rank === 1
                const baseQ = modelRankings[0]?.qlike ?? null
                // Proportional bar width
                const barWidth = isFirst ? 100 : baseQ != null && m.qlike != null ? Math.max(20, Math.min(95, (baseQ / m.qlike) * 100)) : 0

                return (
                  <div key={m.name} className={`loss-rank-row ${isFirst ? 'best-rank-row' : ''}`}>
                    <div className="loss-row-info">
                      <span className="loss-model-name">
                        {m.rank}. {m.name}
                      </span>
                      <span className="loss-score-tag">QLIKE: {m.qlike != null ? m.qlike.toFixed(3) : '—'}</span>
                    </div>
                    <div className="loss-progress-track">
                      <div
                        className={`loss-progress-bar ${isFirst ? 'bar-gold' : m.rank === 2 ? 'bar-light-gray' : 'bar-dark-gray'}`}
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Diebold-Mariano note */}
          <div className="dm-test-footer">
            <div className="dm-test-row">
              <span className="dm-test-label">Diebold-Mariano p-value so với HAR-RV:</span>
              <span className="dm-pill-badge">{dmPValue != null ? dmPValue.toFixed(3) : '—'}</span>
            </div>
            <p className="dm-footnote">
              * QLIKE càng thấp càng tốt. p-value &lt; 0.05 biểu thị sai số khác biệt có ý nghĩa thống kê.
            </p>
          </div>
        </section>
      </div>

      {/* 5. BOTTOM SECTION: CRISIS STRESS & HISTORICAL BACKTEST */}
      <section className="overview-panel stress-section-panel">
        <div className="stress-section-header">
          <div>
            <span className="panel-kicker">KIỂM ĐỊNH KHỦNG HOẢNG</span>
            <h3 className="panel-title">Giai đoạn stress và backtest lịch sử</h3>
            <p className="panel-subtitle">Số lần VaR 99% bị vi phạm trong các cửa sổ khủng hoảng đã biết</p>
          </div>
          <button
            className="view-backtest-link-btn"
            onClick={() => onNavigateTab?.('risk')}
            title="Chuyển sang tab VaR & giá trị kinh tế"
          >
            <span>Xem backtest chi tiết</span>
            <ArrowRight size={14} />
          </button>
        </div>

        {overview.isPending ? (
          <p className="stress-empty-state">Đang tải dữ liệu backtest khủng hoảng…</p>
        ) : overview.isError ? (
          <p className="stress-empty-state stress-error-state">Không thể tải dữ liệu backtest: {overview.error.message}</p>
        ) : crisisEvents.length > 0 ? (
          <div className="crisis-cards-grid">
            {crisisEvents.map((evt) => {
              const domain = crisisChartYDomain(evt.series)
              const returnPath = crisisChartPath(evt.series, (point) => point.return, domain)
              const varPath = crisisChartPath(evt.series, (point) => point.var, domain)

              return (
                <article key={evt.crisis} className="crisis-card">
                  <div className="crisis-card-top">
                    <h4 className="crisis-card-name">{crisisNames[evt.crisis] ?? evt.event}</h4>
                    <span className="crisis-card-date">{evt.start.slice(0, 7)}</span>
                  </div>

                  <div className="crisis-warning-badge">
                    <TriangleAlert size={14} className="warning-icon" />
                    <span>
                      {evt.n_breach} / {evt.n} vi phạm VaR 99% · kỳ vọng {(evt.n * 0.01).toFixed(2)}
                    </span>
                  </div>

                  {evt.series.length > 0 ? (
                    <div className="crisis-mini-chart-wrap">
                      <svg
                        className="crisis-mini-svg"
                        viewBox={`0 0 ${crisisChartWidth} ${crisisChartHeight}`}
                        role="img"
                        aria-label={`Lợi suất, VaR 99% và các vi phạm trong giai đoạn ${evt.start} đến ${evt.end}`}
                      >
                        {[22, 43, 64].map((y) => (
                          <line key={y} x1="10" x2="310" y1={y} y2={y} className="crisis-chart-gridline" />
                        ))}
                        <path d={varPath} className="crisis-chart-var-line" />
                        <path d={returnPath} className="crisis-chart-return-line" />
                        {evt.series.map((point, index) => {
                          if (point.breach !== 1 || point.return == null) return null
                          const x = 10 + (index / Math.max(evt.series.length - 1, 1)) * (crisisChartWidth - 20)
                          const y = 7 + ((domain.max - point.return) / (domain.max - domain.min)) * (crisisChartHeight - 14)
                          return <circle key={point.date} cx={x} cy={y} r="3" className="crisis-chart-breach-dot" />
                        })}
                      </svg>
                      <div className="crisis-chart-legend">
                        <span className="legend-return-item">Lợi suất</span>
                        <span className="legend-var-item">VaR 99%</span>
                        <span className="legend-breach-item">● Vi phạm</span>
                      </div>
                    </div>
                  ) : (
                    <div className="crisis-mini-chart-empty">Không có chuỗi dữ liệu để vẽ</div>
                  )}

                  <div className="crisis-model-breaches">
                    {evt.model_breaches.map((model) => (
                      <div key={model.model} className={`crisis-model-row ${model.model === data?.model ? 'best-model-breach' : ''}`}>
                        <span>{model.label}</span>
                        <strong className="breach-val">
                          {model.n_breach ?? '—'} / {model.n ?? '—'}
                        </strong>
                      </div>
                    ))}
                  </div>

                  <div className="crisis-card-footer">
                    <span>
                      Max drawdown {evt.max_drawdown_pct.toFixed(1)}% · {evt.n}/{evt.calendar_days} ngày có VaR hợp lệ
                    </span>
                  </div>
                </article>
              )
            })}
          </div>
        ) : (
          <p className="stress-empty-state">
            {sample === 'holdout'
              ? 'Các giai đoạn khủng hoảng lịch sử thuộc tập evaluation, không nằm trong kỳ holdout.'
              : 'Không có dữ liệu backtest khủng hoảng phù hợp với bộ lọc hiện tại.'}
          </p>
        )}

        {/* Footnote */}
        <div className="stress-bottom-footnote">
          Chuỗi lịch sử hiển thị theo dữ liệu evaluation; số ngày hợp lệ là các ngày có forecast VaR để chấm điểm.
        </div>
      </section>
    </div>
  )
}

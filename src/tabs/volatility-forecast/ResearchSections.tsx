import { useMemo } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Activity, BarChart3, Database, Layers, Shield, Sparkles, TrendingUp } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useVolatilityResearch } from '../../lib/dashboardQueries'

type ResearchRow = Record<string, string | number | boolean | null>
const colors: Record<string, string> = { normal: '#91a4bc', bull: '#45c39f', bear: '#f0ad36', crisis: '#ed8181' }
const text = (row: ResearchRow, key: string) => typeof row[key] === 'string' ? row[key] as string : ''
const number = (row: ResearchRow, key: string) => typeof row[key] === 'number' ? row[key] as number : null
const fmt = (value: number | null, digits = 4) => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
const modelLabel = (value: string) => ({ enet: 'Elastic Net', xgboost: 'XGBoost', har_rv: 'HAR-RV', garch: 'GARCH(1,1)', gjr_garch: 'GJR-GARCH', combo_core4: 'Combo Core 4', combo_econ: 'Combo Econ', naive_rw: 'Naive RW', hist_mean: 'Historical Mean' }[value] ?? value)

function Header({ code, title, subtitle, icon }: { code: string; title: string; subtitle: string; icon: ReactNode }) {
  return <div className="vf-question-card"><span className="vf-question-tag">{code}</span><div><h2>{title}</h2><p>{subtitle}</p></div><span className="vf-answer-badge">{icon} Backend results</span></div>
}
function PanelTitle({ icon, title, subtitle, badge }: { icon: ReactNode; title: string; subtitle: string; badge?: string }) {
  return <div className="vf-panel-title"><div className="vf-title-icon">{icon}</div><div className="vf-title-copy"><h3>{title}</h3><p>{subtitle}</p></div>{badge && <span className="vf-badge">{badge}</span>}</div>
}
function Loading({ loading, error }: { loading: boolean; error?: unknown }) {
  return <div className="vf-empty"><Database size={22}/><strong>{loading ? 'Đang tải kết quả Backend 3…' : 'Không tải được kết quả nghiên cứu'}</strong><span>{error instanceof Error ? error.message : 'Kiểm tra backend API và thử tải lại.'}</span></div>
}

export function RQ2Results({ symbol, horizonDays }: { symbol: string; horizonDays: 1 | 7 }) {
  const query = useVolatilityResearch(symbol, horizonDays)
  const result = query.data
  const ablation = (result?.volume_ablation ?? []).filter(row => text(row, 'model') === 'xgboost')
  const shap = useMemo(() => [...(result?.shap_importance ?? [])].sort((a, b) => (number(b, 'mean_abs_shap') ?? 0) - (number(a, 'mean_abs_shap') ?? 0)), [result?.shap_importance])
  const macro = (result?.macro_sensitivity ?? []).filter(row => text(row, 'model') === 'xgboost')
  if (query.isLoading && !result) return <Loading loading/>
  if (query.error && !result) return <Loading loading={false} error={query.error}/>
  return <div className="vf-section">
    <Header code="RQ2" title="Biến bổ sung có tăng sức dự báo ngoài lịch sử return và RV không?" subtitle={`${symbol.replace('USDT', '')} · ${result?.window ?? 'rolling'} · horizon ${horizonDays} ngày · mẫu đánh giá từ backend`} icon={<Sparkles size={15}/>}/>
    <div className="vf-chart-grid vf-rq2-grid">
      <section className="vf-panel"><PanelTitle icon={<Layers size={17}/>} title="Kiểm tra bổ sung biến (Ablation study)" subtitle="So sánh QLIKE trên cùng mẫu và cùng cấu hình huấn luyện" badge="XGBoost"/>
        {ablation.length ? <div className="vf-table-scroll"><table className="vf-table"><thead><tr><th>Bộ biến</th><th>QLIKE đầy đủ</th><th>QLIKE nền</th><th>Chênh lệch</th><th>DM p-value</th><th>N</th></tr></thead><tbody>{ablation.map((row, i) => <tr key={String(row.model) + String(row.auxiliary_features)}><td><strong>{i === 0 ? 'Có biến phụ trợ' : String(row.auxiliary_features ?? 'Biến phụ trợ')}</strong><small className="vf-cell-note">{String(row.auxiliary_features ?? '')}</small></td><td>{fmt(number(row, 'QLIKE_full'))}</td><td>{fmt(number(row, 'QLIKE_core'))}</td><td className={(number(row, 'QLIKE_full_minus_core') ?? 0) < 0 ? 'vf-good' : 'vf-amber'}>{fmt(number(row, 'QLIKE_full_minus_core'))}</td><td>{fmt(number(row, 'dm_p_value'))}</td><td>{number(row, 'n_common')?.toLocaleString('vi-VN') ?? '—'}</td></tr>)}</tbody></table></div> : <Loading loading={query.isLoading} error={query.error}/>}
        <p className="vf-chart-foot">QLIKE và kiểm định DM là kết quả ablation đã xuất từ backend; chênh lệch âm nghĩa là QLIKE của mô hình đầy đủ thấp hơn.</p>
      </section>
      <section className="vf-panel"><PanelTitle icon={<Activity size={17}/>} title="Mức quan trọng của biến (SHAP)" subtitle="Mean absolute SHAP trên dự báo XGBoost ngoài mẫu" badge={shap.length ? `N = ${number(shap[0], 'n_origins')?.toLocaleString('vi-VN') ?? '—'}` : undefined}/>
        {shap.length ? <div className="vf-shap-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={shap} layout="vertical" margin={{ top: 2, right: 20, bottom: 2, left: 12 }}><CartesianGrid stroke="#21344b" strokeDasharray="3 5" horizontal={false}/><XAxis type="number" tick={{ fill: '#90a2b8', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="feature" width={105} tick={{ fill: '#bdcadd', fontSize: 10 }} axisLine={false} tickLine={false}/><Tooltip formatter={value => fmt(Number(value), 5)} contentStyle={{ background: '#091629', border: '1px solid #28405c', borderRadius: 8, color: '#e7edf6', fontSize: 11 }}/><Bar dataKey="mean_abs_shap" name="Mean |SHAP|" fill="#f0ad36" radius={[0, 4, 4, 0]}/></BarChart></ResponsiveContainer></div> : <Loading loading={query.isLoading} error={query.error}/>}
        <p className="vf-chart-foot">SHAP mô tả độ lớn đóng góp vào raw log-RV của XGBoost; không phải tác động nhân quả.</p>
      </section>
    </div>
    <section className="vf-panel"><PanelTitle icon={<TrendingUp size={17}/>} title="Độ nhạy với biến vĩ mô (VIX, USD)" subtitle="Bảng sensitivity riêng của backend; không gộp vào ablation volume" badge="Sensitivity only"/>
      {macro.length ? <div className="vf-table-scroll"><table className="vf-table"><thead><tr><th>Feature set</th><th>QLIKE</th><th>Δ QLIKE so với nền</th><th>DM p-value</th><th>N</th><th>Ghi chú</th></tr></thead><tbody>{macro.map(row => <tr key={String(row.feature_set)}><td><strong>{String(row.feature_set).replaceAll('_', ' ').toUpperCase()}</strong></td><td>{fmt(number(row, 'QLIKE'))}</td><td className={(number(row, 'QLIKE_minus_without_macro') ?? 0) < 0 ? 'vf-good' : ''}>{fmt(number(row, 'QLIKE_minus_without_macro'))}</td><td>{fmt(number(row, 'dm_p_value'))}</td><td>{number(row, 'n')?.toLocaleString('vi-VN') ?? '—'}</td><td>{text(row, 'dm_status') || 'Mốc tham chiếu'}</td></tr>)}</tbody></table></div> : <Loading loading={query.isLoading} error={query.error}/>}
    </section>
  </div>
}

export function RQ3Results({ symbol, horizonDays }: { symbol: string; horizonDays: 1 | 7 }) {
  const query = useVolatilityResearch(symbol, horizonDays)
  const result = query.data
  const regimes = ['normal', 'bull', 'bear', 'crisis']
  const allModels = [...new Set((result?.regime_performance ?? []).map(row => text(row, 'model')))].filter(Boolean).sort((a, b) => a === 'har_rv' ? -1 : b === 'har_rv' ? 1 : a.localeCompare(b))
  const counts = regimes.map(regime => ({ regime: regime[0].toUpperCase() + regime.slice(1), ...(Object.fromEntries(allModels.flatMap(model => {
    const item = result?.regime_performance.find(row => text(row, 'regime') === regime && text(row, 'model') === model)
    return item ? [[model, number(item, 'QLIKE')]] : []
  }))) }))
  const matrix = regimes.map(regime => {
    const reference = result?.regime_performance.find(row => text(row, 'regime') === regime && text(row, 'model') === 'har_rv')
    return { regime, count: number(result?.regime_counts.find(row => text(row, 'regime') === regime) ?? {}, 'n_common_dates'), rows: allModels.map(model => {
      const item = result?.regime_performance.find(row => text(row, 'regime') === regime && text(row, 'model') === model)
      const qlike = item ? number(item, 'QLIKE') : null
      const har = reference ? number(reference, 'QLIKE') : null
      return { model, qlike, ratio: qlike != null && har != null && har !== 0 ? qlike / har : null, n: item ? number(item, 'n') : null }
    }) }
  })
  if (query.isLoading && !result) return <Loading loading/>
  if (query.error && !result) return <Loading loading={false} error={query.error}/>
  return <div className="vf-section">
    <Header code="RQ3" title="Lợi thế dự báo có thay đổi giữa Normal, Bull, Bear và Crisis không?" subtitle={`${symbol.replace('USDT', '')} · ${result?.window ?? 'rolling'} · horizon ${horizonDays} ngày · backend evaluation results`} icon={<TrendingUp size={15}/>}/>
    <div className="vf-chart-grid vf-rq3-grid">
      <section className="vf-panel"><PanelTitle icon={<BarChart3 size={17}/>} title="QLIKE ratio so với HAR-RV theo regime" subtitle="Tỷ số < 1: tốt hơn benchmark · > 1: kém hơn" badge="Backend table"/>
        <div className="vf-table-scroll"><table className="vf-table vf-heatmap"><thead><tr><th>Mô hình</th>{regimes.map(regime => <th key={regime}>{regime.toUpperCase()}</th>)}</tr></thead><tbody>{allModels.filter(model => model !== 'har_rv').map(model => <tr key={model}><td><strong>{modelLabel(model)}</strong></td>{regimes.map(regime => { const row = matrix.find(item => item.regime === regime)?.rows.find(item => item.model === model); return <td key={regime}><span className={`vf-heat-cell ${row?.ratio != null && row.ratio < 1 ? 'better' : row?.ratio != null ? 'worse' : ''}`}>{fmt(row?.ratio ?? null, 2)}{row?.ratio == null ? '' : row.ratio < 1 ? ' ↓' : ' ↑'}</span></td> })}</tr>)}</tbody></table></div>
        <div className="vf-count-row"><strong>Số ngày đánh giá</strong>{matrix.map(row => <span key={row.regime}>{row.regime}: <b>{row.count?.toLocaleString('vi-VN') ?? '—'}</b></span>)}</div>
        <p className="vf-chart-foot">Tỷ số được tính từ QLIKE trong bảng performance backend của cùng symbol, window, horizon và regime; benchmark là HAR-RV.</p>
      </section>
      <section className="vf-panel"><PanelTitle icon={<Activity size={17}/>} title="QLIKE theo regime và mô hình" subtitle="So sánh các mô hình có kết quả thật trong backend" badge={`${allModels.length} models`}/>
        <div className="vf-regime-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={counts} margin={{ top: 10, right: 5, bottom: 0, left: 0 }}><CartesianGrid stroke="#21344b" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="regime" tick={{ fill: '#a9b8cb', fontSize: 10 }} tickLine={false} axisLine={false}/><YAxis tick={{ fill: '#90a2b8', fontSize: 10 }} tickLine={false} axisLine={false} width={44}/><Tooltip formatter={value => fmt(Number(value))} contentStyle={{ background: '#091629', border: '1px solid #28405c', borderRadius: 8, color: '#e7edf6', fontSize: 10 }}/><Legend wrapperStyle={{ fontSize: 9, color: '#a9b8cb' }}/>{allModels.map((model, i) => <Bar key={model} dataKey={model} name={modelLabel(model)} fill={model === 'har_rv' ? '#8394a8' : i === allModels.length - 1 ? '#f0ad36' : `hsl(${205 + i * 13} 56% ${53 + (i % 3) * 6}%)`} radius={[2, 2, 0, 0]}/>)}</BarChart></ResponsiveContainer></div>
        <p className="vf-chart-foot">Các cột dùng QLIKE theo từng regime lấy từ bảng regime_performance của backend.</p>
      </section>
    </div>
    <section className="vf-panel"><PanelTitle icon={<Shield size={17}/>} title="Chi tiết QLIKE và số mẫu theo regime" subtitle="Chỉ hiển thị model/regime có record trong backend" badge="No mock values"/>
      <div className="vf-table-scroll"><table className="vf-table"><thead><tr><th>Regime</th><th>Model</th><th>QLIKE</th><th>QLIKE / HAR-RV</th><th>Số ngày</th><th>RMSE</th><th>MAE</th></tr></thead><tbody>{matrix.flatMap(regime => regime.rows.filter(row => row.qlike != null).map(row => { const raw = result?.regime_performance.find(item => text(item, 'regime') === regime.regime && text(item, 'model') === row.model); return <tr key={`${regime.regime}-${row.model}`}><td><span className="vf-regime-label" style={{ '--regime-color': colors[regime.regime] } as CSSProperties}>{regime.regime[0].toUpperCase() + regime.regime.slice(1)}</span></td><td>{modelLabel(row.model)}</td><td>{fmt(row.qlike)}</td><td className={row.ratio != null && row.ratio < 1 ? 'vf-good' : ''}>{row.ratio == null ? '—' : fmt(row.ratio, 3)}</td><td>{row.n?.toLocaleString('vi-VN') ?? '—'}</td><td>{fmt(number(raw ?? {}, 'RMSE'))}</td><td>{fmt(number(raw ?? {}, 'MAE'))}</td></tr> }))}</tbody></table></div>
      <p className="vf-chart-foot">Crisis hoặc model không có record theo filter sẽ không được tạo giá trị giả; bảng chỉ hiện các hàng có số backend.</p>
    </section>
  </div>
}

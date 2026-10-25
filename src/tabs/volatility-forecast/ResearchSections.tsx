import { useMemo } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Activity, BarChart3, Database, Layers, Shield, Sparkles, TrendingUp } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useVolatilityResearch } from '../../lib/dashboardQueries'
import type { DashboardSample } from '../../lib/api'

type ResearchRow = Record<string, string | number | boolean | null>
const colors: Record<string, string> = { normal: '#91a4bc', bull: '#45c39f', bear: '#f0ad36', crisis: '#ed8181' }
const text = (row: ResearchRow, key: string) => typeof row[key] === 'string' ? row[key] as string : ''
const number = (row: ResearchRow, key: string) => typeof row[key] === 'number' ? row[key] as number : null
const fmt = (value: number | null, digits = 4) => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
const modelLabel = (value: string) => ({ enet: 'Elastic Net', xgboost: 'XGBoost', har_rv: 'HAR-RV', garch: 'GARCH(1,1)', gjr_garch: 'GJR-GARCH', combo_core4: 'Combo Core 4', combo_econ: 'Combo Econ', naive_rw: 'Naive RW', hist_mean: 'Historical Mean' }[value] ?? value)
const featureLabel = (value: string) => ({
  log_rv_d: 'RV ngày trước (RV_d)',
  log_rv_w: 'RV trung bình 5 ngày (RV_w)',
  log_rv_m: 'RV trung bình 22 ngày (RV_m)',
  log_park: 'Biên độ cao-thấp (Parkinson)',
  ret_d: 'Lợi suất ngày trước',
  log_qv: 'Khối lượng giao dịch (Volume)',
  log_turn_rel: 'Turnover tương đối',
}[value] ?? value.replaceAll('_', ' '))

function Header({ code, title, subtitle, icon }: { code: string; title: string; subtitle: string; icon: ReactNode }) {
  return <div className="vf-question-card"><span className="vf-question-tag">{code}</span><div><h2>{title}</h2><p>{subtitle}</p></div><span className="vf-answer-badge">{icon} Backend results</span></div>
}
function PanelTitle({ icon, title, subtitle, badge }: { icon: ReactNode; title: string; subtitle: string; badge?: string }) {
  return <div className="vf-panel-title"><div className="vf-title-icon">{icon}</div><div className="vf-title-copy"><h3>{title}</h3><p>{subtitle}</p></div>{badge && <span className="vf-badge">{badge}</span>}</div>
}
function Loading({ loading, error }: { loading: boolean; error?: unknown }) {
  return <div className="vf-empty"><Database size={22}/><strong>{loading ? 'Đang tải kết quả Backend 3…' : 'Không tải được kết quả nghiên cứu'}</strong><span>{error instanceof Error ? error.message : 'Kiểm tra backend API và thử tải lại.'}</span></div>
}

export function RQ2Results({ symbol, horizonDays, sample }: { symbol: string; horizonDays: 1 | 7; sample: DashboardSample }) {
  const query = useVolatilityResearch(symbol, horizonDays, sample)
  const result = query.data
  const ablation = (result?.volume_ablation ?? []).filter(row => text(row, 'model') === 'xgboost')
  const shap = useMemo(() => [...(result?.shap_importance ?? [])].sort((a, b) => (number(b, 'mean_abs_shap') ?? 0) - (number(a, 'mean_abs_shap') ?? 0)), [result?.shap_importance])
  const macro = (result?.macro_sensitivity ?? []).filter(row => text(row, 'model') === 'xgboost')
  const shapMaximum = Math.max(...shap.map(row => number(row, 'mean_abs_shap') ?? 0), 0)
  const ablationResult = ablation[0]
  const qlikeCore = ablationResult ? number(ablationResult, 'QLIKE_core') : null
  const qlikeFull = ablationResult ? number(ablationResult, 'QLIKE_full') : null
  const volumeDelta = ablationResult ? number(ablationResult, 'QLIKE_full_minus_core') : null
  const volumeDeltaPct = qlikeCore != null && qlikeFull != null && qlikeCore !== 0
    ? (qlikeFull / qlikeCore - 1) * 100
    : null
  const volumePValue = ablationResult ? number(ablationResult, 'dm_p_value') : null
  const matchedSampleSize = ablationResult ? number(ablationResult, 'n_common') : null
  const macroVariants = macro.filter(row => text(row, 'feature_set') !== 'macro_base')
  const significantMacroImprovement = macroVariants.some(row =>
    (number(row, 'QLIKE_minus_without_macro') ?? 0) < 0
      && (number(row, 'dm_p_value') ?? 1) < 0.05,
  )
  const significantMacroWorsening = macroVariants.some(row =>
    (number(row, 'QLIKE_minus_without_macro') ?? 0) > 0
      && (number(row, 'dm_p_value') ?? 1) < 0.05,
  )
  if (query.isLoading && !result) return <Loading loading/>
  if (query.error && !result) return <Loading loading={false} error={query.error}/>
  return <div className="vf-section">
    <Header code="RQ2" title="Biến bổ sung có cải thiện dự báo ngoài các đặc trưng lịch sử RV không?" subtitle={`${symbol.replace('USDT', '')} · ${result?.window ?? 'rolling'} · horizon ${horizonDays} ngày · ${sample === 'holdout' ? 'holdout 2026' : 'evaluation 2021–2025'}`} icon={<Sparkles size={15}/>}/>
    <div className="vf-chart-grid vf-rq2-grid">
      <section className="vf-panel"><PanelTitle icon={<Layers size={17}/>} title="Kiểm tra bổ sung biến (Ablation study)" subtitle="XGBoost · cùng mẫu, cấu hình và tập huấn luyện" badge="XGBoost"/>
        {ablationResult && qlikeCore != null && qlikeFull != null ? <>
          <div className="vf-ablation-bars">
            <div className="vf-ablation-row">
              <div className="vf-ablation-label"><strong>Đặc trưng lõi</strong><span>Không thêm volume</span><b>QLIKE {fmt(qlikeCore)}</b></div>
              <div className="vf-ablation-track"><i className="vf-ablation-core" style={{ width: '100%' }}/></div>
            </div>
            <div className="vf-ablation-row">
              <div className="vf-ablation-label"><strong>+ Volume</strong><span>{text(ablationResult, 'auxiliary_features').split(',').map(featureLabel).join(' · ')}</span><b>QLIKE {fmt(qlikeFull)}</b></div>
              <div className="vf-ablation-track"><i className="vf-ablation-volume" style={{ width: `${Math.min(100, Math.max(0, (qlikeFull / qlikeCore) * 100))}%` }}/></div>
            </div>
          </div>
          <div className="vf-ablation-stats">
            <span>Δ QLIKE: <strong className={volumeDelta != null && volumeDelta < 0 ? 'vf-good' : 'vf-amber'}>{fmt(volumeDelta)}</strong></span>
            <span>Thay đổi: <strong className={volumeDeltaPct != null && volumeDeltaPct < 0 ? 'vf-good' : 'vf-amber'}>{volumeDeltaPct == null ? '—' : `${volumeDeltaPct > 0 ? '+' : ''}${fmt(volumeDeltaPct, 2)}%`}</strong></span>
            <span>DM p-value: <strong>{fmt(volumePValue)}</strong></span>
            <span>N paired: <strong>{matchedSampleSize?.toLocaleString('vi-VN') ?? '—'}</strong></span>
          </div>
          <p className="vf-ablation-conclusion">
            {volumeDelta == null
              ? 'Chưa đủ dữ liệu để so sánh hai tập biến.'
              : volumeDelta < 0 && volumePValue != null && volumePValue < 0.05
                ? 'Thêm volume giảm QLIKE và khác biệt có ý nghĩa thống kê trong mẫu đang chọn.'
                : volumeDelta < 0
                  ? 'Thêm volume làm QLIKE giảm trong mẫu này, nhưng DM chưa cho thấy khác biệt có ý nghĩa ở mức 5%.'
                  : 'Thêm volume không cải thiện QLIKE trong mẫu này.'}
          </p>
        </> : <div className="vf-unavailable"><Database size={18}/><div><strong>{query.isLoading ? 'Đang tải ablation…' : 'Chưa có kết quả ablation cho cấu hình này'}</strong><p>{query.error instanceof Error ? query.error.message : 'Không thay bằng số liệu minh họa; kiểm tra mẫu và horizon đang chọn.'}</p></div></div>}
        <p className="vf-chart-foot">QLIKE thấp hơn là tốt hơn. Chênh lệch âm nghĩa là nhánh có volume giảm loss; backend xác nhận hai nhánh dùng cùng mẫu và cùng cấu hình huấn luyện.</p>
      </section>
      <section className="vf-panel"><PanelTitle icon={<Activity size={17}/>} title="Mức quan trọng của biến (SHAP)" subtitle="Mean |SHAP| trên raw log-RV của XGBoost ngoài mẫu" badge={shap.length ? `N = ${number(shap[0], 'n_origins')?.toLocaleString('vi-VN') ?? '—'}` : undefined}/>
        {shap.length ? <div className="vf-shap-list">{shap.map(row => {
          const value = number(row, 'mean_abs_shap') ?? 0
          return <div className="vf-shap-row" key={text(row, 'feature')}>
            <span title={text(row, 'feature')}>{featureLabel(text(row, 'feature'))}</span>
            <div className="vf-shap-track"><i style={{ width: `${shapMaximum > 0 ? (value / shapMaximum) * 100 : 0}%` }}/></div>
            <strong>{fmt(value, 3)}</strong>
          </div>
        })}</div> : <div className="vf-unavailable"><Database size={18}/><div><strong>{query.isLoading ? 'Đang tải SHAP…' : 'Chưa có kết quả SHAP cho cấu hình này'}</strong><p>{query.error instanceof Error ? query.error.message : 'Không có bảng SHAP tương ứng trong backend.'}</p></div></div>}
        <p className="vf-chart-foot">Mean |SHAP| đo độ lớn đóng góp vào raw log-RV, không cho biết chiều tác động hay quan hệ nhân quả. Thanh được chuẩn hóa theo biến có SHAP lớn nhất trong cấu hình này.</p>
      </section>
    </div>
    <section className="vf-panel"><PanelTitle icon={<TrendingUp size={17}/>} title="Độ nhạy với biến vĩ mô (VIX, USD)" subtitle="Bảng sensitivity riêng của backend; không gộp vào ablation volume" badge="Sensitivity only"/>
      {macro.length ? <div className="vf-table-scroll"><table className="vf-table"><thead><tr><th>Feature set</th><th>QLIKE</th><th>Δ QLIKE so với nền</th><th>DM p-value</th><th>N</th><th>Ghi chú</th></tr></thead><tbody>{macro.map(row => <tr key={String(row.feature_set)}><td><strong>{String(row.feature_set).replaceAll('_', ' ').toUpperCase()}</strong></td><td>{fmt(number(row, 'QLIKE'))}</td><td className={(number(row, 'QLIKE_minus_without_macro') ?? 0) < 0 ? 'vf-good' : 'vf-amber'}>{fmt(number(row, 'QLIKE_minus_without_macro'))}</td><td>{fmt(number(row, 'dm_p_value'))}</td><td>{number(row, 'n')?.toLocaleString('vi-VN') ?? '—'}</td><td>{text(row, 'dm_status') || 'Mốc tham chiếu'}</td></tr>)}</tbody></table></div> : <div className="vf-unavailable"><Database size={18}/><div><strong>{query.isLoading ? 'Đang tải sensitivity…' : 'Không có bảng macro sensitivity cho mẫu này'}</strong><p>{sample === 'holdout' ? 'Backend hiện chỉ xuất bảng sensitivity macro cho evaluation; không suy rộng kết quả evaluation thành kết quả holdout.' : 'Backend không có kết quả macro sensitivity phù hợp.'}</p></div></div>}
      {macro.length > 0 && <p className="vf-ablation-conclusion">
        {significantMacroImprovement
          ? 'Có ít nhất một bộ biến macro giảm QLIKE với khác biệt DM có ý nghĩa ở mức 5% trong cấu hình này.'
          : significantMacroWorsening
            ? 'Có ít nhất một bộ biến macro làm QLIKE tăng với khác biệt DM có ý nghĩa ở mức 5% trong cấu hình này.'
            : 'Trong các bộ VIX/USD đang hiển thị, chưa có khác biệt QLIKE có ý nghĩa thống kê ở mức 5% theo DM.'}
      </p>}
      <p className="vf-chart-foot">Sensitivity macro là phân tích tách biệt, không thuộc mô hình chính và không chứng minh quan hệ nhân quả; chỉ diễn giải trong cấu hình đang hiển thị.</p>
    </section>
  </div>
}

export function RQ3Results({ symbol, horizonDays, sample }: { symbol: string; horizonDays: 1 | 7; sample: DashboardSample }) {
  const query = useVolatilityResearch(symbol, horizonDays, sample)
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

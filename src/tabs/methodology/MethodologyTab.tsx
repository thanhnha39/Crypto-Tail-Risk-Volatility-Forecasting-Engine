import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDownToLine,
  ArrowUp,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileText,
  FlaskConical,
  Layers3,
  LockKeyhole,
  Menu,
  Sigma,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Timer,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { api, apiPaths } from '../../lib/api'
import './methodology.css'

interface SegmentQuality {
  sample_segment: string
  days: number
  eligible_rv: number
  missing_bars: number
}

interface SymbolQuality {
  symbol: string
  raw_rows: number
  clean_rows: number
  coverage_start_utc: string
  coverage_end_utc: string
  expected_days: number
  days_eligible_rv: number
  incomplete_days: number
  missing_bars: number
  zero_volume_bars: number
  large_return_bars: number
  daily_quality_by_segment: SegmentQuality[]
}

interface MacroSource {
  series_id: string
  status: string
  rows: number
  nonmissing_values: number
  last_observation_with_value: string
}

interface MethodologyResponse {
  assets: string[]
  data_frequency: string
  snapshot_id: string | null
  data_source: string | null
  dataset_sha256: string | null
  protocol_sha256: string | null
  dataset_rows: number | null
  feature_columns: string[]
  target_7d_aggregation: string | null
  missing_data_policy: string | null
  turnover_is_proxy: boolean
  evaluation_period: string
  holdout: string
  models: string[]
  core_models: string[]
  source_quality: SymbolQuality[]
  macro_sources: MacroSource[]
  crosscheck: Array<{ symbol: string; status: string; matched_days: number; date_start: string; date_end: string }>
  study_protocol: {
    window_days?: number
    refit_every_days?: number
    main_horizon_days?: number
    sensitivity_horizon_days?: number[]
    main_window?: string
    sensitivity_window?: string
    xgboost_tuning_period?: string
    xgboost_retune?: boolean
    macro_in_main_model?: boolean
    regime?: { crisis_quantile?: number; calibration_segment?: string; log_return_days?: number; bull_threshold_pct?: number; bear_threshold_pct?: number }
    risk?: { confidence_levels?: number[]; garch_gjr_distribution?: string; har_xgboost_method?: string; backtests?: string[] }
  }
  backend_validation: { status: string | null; forecast_rows: number | null; common_scored_rows: number | null; holdout_scored: boolean | null }
  risk_validation: { status: string | null; tests: number | null; passed: boolean | null; failures: number | null; errors: number | null }
  holdout_pipeline_state: string | null
  repository_url: string
  risk_notes: string[]
}

const SECTIONS = [
  ['overview', '1. Tổng quan'],
  ['data', '2. Dữ liệu'],
  ['partition', '3. Chia mẫu'],
  ['methods', '4. Phương pháp'],
  ['evaluation', '5. Đánh giá'],
  ['reproducibility', '6. Tái lập'],
  ['limitations', '7. Giới hạn'],
  ['references', '8. Tài liệu'],
] as const

const PAPERS = [
  { authors: 'Corsi, F. (2009).', title: 'A simple approximate long-memory model of realized volatility.', journal: 'Journal of Financial Econometrics, 7(2), 174–196.', url: 'https://doi.org/10.1093/jjfinec/nbp001' },
  { authors: 'Engle, R. F. (1982).', title: 'Autoregressive conditional heteroscedasticity with estimates of the variance of United Kingdom inflation.', journal: 'Econometrica, 50(4), 987–1007.', url: 'https://doi.org/10.2307/1912773' },
  { authors: 'Bollerslev, T. (1986).', title: 'Generalized autoregressive conditional heteroskedasticity.', journal: 'Journal of Econometrics, 31(3), 307–327.', url: 'https://doi.org/10.1016/0304-4076(86)90063-1' },
  { authors: 'Chen, T., & Guestrin, C. (2016).', title: 'XGBoost: A scalable tree boosting system.', journal: 'Proceedings of the 22nd ACM SIGKDD, 785–794.', url: 'https://doi.org/10.1145/2939672.2939785' },
  { authors: 'Diebold, F. X., & Mariano, R. S. (1995).', title: 'Comparing predictive accuracy.', journal: 'Journal of Business & Economic Statistics, 13(3), 253–263.', url: 'https://doi.org/10.1080/07350015.1995.10524599' },
  { authors: 'Kupiec, P. H. (1995).', title: 'Techniques for verifying the accuracy of risk measurement models.', journal: 'The Journal of Derivatives, 3(2), 73–84.', url: 'https://doi.org/10.3905/jod.1995.407942' },
  { authors: 'Christoffersen, P. F. (1998).', title: 'Evaluating interval forecasts.', journal: 'International Economic Review, 39(4), 841–862.', url: 'https://doi.org/10.2307/2527341' },
  { authors: 'Patton, A. J. (2011).', title: 'Volatility forecast comparison using imperfect volatility proxies.', journal: 'Journal of Econometrics, 160(1), 246–256.', url: 'https://doi.org/10.1016/j.jeconom.2010.03.034' },
]

const number = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('en-US')
const shortHash = (value: string | null) => value ? `${value.slice(0, 12)}…${value.slice(-8)}` : '—'
const dateOnly = (value: string | null | undefined) => value?.slice(0, 10) ?? '—'
function SectionHeading({ number: sectionNumber, title, subtitle, icon }: { number: string; title: string; subtitle: string; icon: ReactNode }) {
  return (
    <header className="method-section-heading">
      <div className="method-section-mark">{icon}<span>{sectionNumber}.</span></div>
      <div className="method-section-heading-copy"><h2>{title}</h2><p>{subtitle}</p></div>
    </header>
  )
}

function StateTag({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'good' | 'warn' | 'neutral' }) {
  return <span className={`method-state ${tone}`}>{children}</span>
}

function MethodSection({ id, children, className = '' }: { id: string; children: ReactNode; className?: string }) {
  return <section id={`method-${id}`} className={`method-section ${className}`}>{children}</section>
}

export default function MethodologyTab({ onNavigateTab }: { onNavigateTab: (tab: 'forecast' | 'risk') => void }) {
  const [activeSection, setActiveSection] = useState<string>('overview')
  const [tocCollapsed, setTocCollapsed] = useState(false)
  const method = useQuery({
    queryKey: ['methodology'],
    queryFn: async () => (await api.get<MethodologyResponse>(apiPaths.methodology)).data,
  })
  const data = method.data
  const mainQuality = data?.source_quality?.[0]

  useEffect(() => {
    const updateActiveSection = () => {
      let current: string = 'overview'
      for (const [id] of SECTIONS) {
        const element = document.getElementById(`method-${id}`)
        if (element && element.getBoundingClientRect().top <= 190) current = id
      }
      setActiveSection(current)
    }
    window.addEventListener('scroll', updateActiveSection, { passive: true })
    updateActiveSection()
    return () => window.removeEventListener('scroll', updateActiveSection)
  }, [])

  const goToSection = (id: string) => {
    setActiveSection(id)
    const section = document.getElementById(`method-${id}`)
    if (section) window.scrollTo({ top: section.getBoundingClientRect().top + window.scrollY - 22, behavior: 'instant' })
  }

  const overviewFacts = [
    { label: 'Tài sản', value: data?.assets.map((asset) => asset.replace('USDT', '')).join(' / ') ?? 'BTC / ETH' },
    { label: 'Nguồn thị trường', value: data?.data_source === 'binance_spot_real_snapshot' ? 'Binance Spot' : data?.data_source ?? '—' },
    { label: 'Snapshot dữ liệu', value: data?.snapshot_id ?? '—' },
    { label: 'Chu kỳ dự báo chính', value: '1 ngày · rolling' },
  ]

  return (
    <div className={`methodology-layout ${tocCollapsed ? 'toc-collapsed' : ''}`}>
      <main className="methodology-content">
        {method.isError && <div className="notice"><span className="notice-icon"><CircleAlert size={17} /></span><div><strong>Không tải được metadata nghiên cứu</strong><p>{method.error instanceof Error ? method.error.message : 'Kiểm tra API rồi tải lại trang.'}</p></div><span className="notice-tag">API ERROR</span></div>}

        <MethodSection id="overview">
          <SectionHeading number="1" title="Tổng quan dự án" subtitle="Khung kinh tế lượng và Machine Learning cho dự báo biến động, rủi ro đuôi" icon={<FlaskConical size={19} />} />
          <div className="method-fact-grid">
            {overviewFacts.map((fact) => <article className="method-fact-card" key={fact.label}><span>{fact.label}</span><strong>{fact.value}</strong></article>)}
          </div>
          <p className="method-lead">Nghiên cứu dự báo realized variance (RV) và đánh giá rủi ro đuôi của BTC và ETH. Mục tiêu là so sánh các baseline và mô hình kinh tế lượng với Machine Learning theo quy trình walk-forward; đây không phải mô hình dự báo giá hay khuyến nghị đầu tư.</p>
          <p className="method-body">Năm mục tiêu nghiên cứu được trình bày ở các tab kết quả: độ chính xác dự báo (RO1), giá trị của nhóm biến bổ sung (RO2), sự khác biệt theo regime (RO3), chất lượng VaR/ES (RO4) và kết quả mô phỏng volatility targeting (RO5). Kết luận không được gán cứng trong mục phương pháp; xem kết quả theo từng mẫu và bộ lọc.</p>
          <div className="method-rq-grid">
            {[
              { id: 'RO1', text: 'So sánh năng lực dự báo RV ngoài mẫu giữa ML và benchmark.', tab: 'forecast' as const },
              { id: 'RO2', text: 'Kiểm tra đóng góp của volume, macro sensitivity và SHAP.', tab: 'forecast' as const },
              { id: 'RO3', text: 'Đánh giá độ chính xác theo trạng thái thị trường.', tab: 'forecast' as const },
              { id: 'RO4', text: 'Đánh giá VaR coverage và các cửa sổ stress lịch sử.', tab: 'risk' as const },
              { id: 'RO5', text: 'Đánh giá mô phỏng phân bổ volatility-target sau chi phí.', tab: 'risk' as const },
            ].map((item) => <button type="button" className="method-rq-card" key={item.id} onClick={() => onNavigateTab(item.tab)}><span>{item.id}<ChevronRight size={14} /></span><p>{item.text}</p><small>Xem kết quả <ArrowDownToLine size={12} /></small></button>)}
          </div>
        </MethodSection>

        <MethodSection id="data">
          <SectionHeading number="2" title="Dữ liệu & thị trường" subtitle="Nguồn, chất lượng dữ liệu và vai trò của từng chuỗi" icon={<Database size={19} />} />
          <div className="method-table-wrap"><table className="method-table"><thead><tr><th>Nguồn</th><th>Biến / nội dung</th><th>Độ phân giải</th><th>Vai trò trong nghiên cứu</th><th>Trạng thái</th></tr></thead><tbody>
            <tr><td><strong>Binance Spot</strong></td><td>BTCUSDT, ETHUSDT OHLCV</td><td>5 phút · UTC</td><td>Nguồn chính để dựng RV, return và features</td><td><StateTag tone="good"><CheckCircle2 size={13} /> Dữ liệu chính</StateTag></td></tr>
            {(data?.macro_sources ?? []).map((source) => <tr key={source.series_id}><td><strong>FRED · {source.series_id}</strong></td><td>{source.series_id === 'VIXCLS' ? 'VIX' : 'Broad USD index'}</td><td>Ngày</td><td>Độ nhạy riêng; không thuộc mô hình chính do chưa xác minh point-in-time</td><td><StateTag tone="warn"><CircleAlert size={13} /> Chưa xác minh PIT</StateTag></td></tr>)}
            <tr><td><strong>CoinGecko</strong></td><td>Giá đóng cửa tham chiếu</td><td>Đối chiếu mẫu 365 ngày gần nhất</td><td>Cross-check, không thay thế nguồn giá chính</td><td><StateTag>Đối chiếu</StateTag></td></tr>
          </tbody></table></div>
          <div className="method-data-stats">
            {[
              { label: 'Nến sạch mỗi tài sản', value: number(mainQuality?.clean_rows), note: '5 phút · snapshot backend' },
              { label: 'Ngày lịch trong snapshot', value: number(mainQuality?.expected_days), note: `${dateOnly(mainQuality?.coverage_start_utc)} đến ${dateOnly(mainQuality?.coverage_end_utc)}` },
              { label: 'Ngày đủ điều kiện tính RV', value: number(mainQuality?.days_eligible_rv), note: 'Yêu cầu đủ nến và return hợp lệ' },
              { label: 'Nến bị quarantine', value: '0', note: 'Theo QA summary của snapshot' },
            ].map((stat) => <article className="method-stat-card" key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong><small>{stat.note}</small></article>)}
          </div>
          <h3 className="method-subheading">Chất lượng dữ liệu theo tài sản</h3>
          <div className="method-table-wrap"><table className="method-table"><thead><tr><th>Tài sản</th><th>Nến nguồn</th><th>Ngày đủ RV</th><th>Ngày thiếu</th><th>Nến thiếu</th><th>Volume = 0</th><th>Return lớn được gắn cờ</th></tr></thead><tbody>
            {(data?.source_quality ?? []).map((row) => <tr key={row.symbol}><td><strong>{row.symbol}</strong></td><td>{number(row.clean_rows)}</td><td>{number(row.days_eligible_rv)} / {number(row.expected_days)}</td><td>{number(row.incomplete_days)}</td><td>{number(row.missing_bars)}</td><td>{number(row.zero_volume_bars)}</td><td>{number(row.large_return_bars)}</td></tr>)}
          </tbody></table></div>
          <div className="method-note"><CircleAlert size={16} /><p>Không điền RV thiếu bằng 0, không nén lịch ngày và không winsorize return lớn. Ngày thiếu dữ liệu được giữ lại trong lịch và phản ánh trong cờ QA.</p></div>
        </MethodSection>

        <MethodSection id="partition">
          <SectionHeading number="3" title="Chia mẫu & walk-forward" subtitle="Tách giai đoạn theo thời gian, giữ nguyên lịch và thông tin có sẵn tại forecast origin" icon={<Layers3 size={19} />} />
          <div className="method-overlap-note"><span><ShieldCheck size={16} /> Giai đoạn và mốc thời gian theo protocol backend</span><StateTag tone="good">Lịch cố định</StateTag></div>
          <div className="method-timeline">
            <div className="method-timeline-segment context"><strong>Đệm dữ liệu</strong><span>12/2018</span><small>Giữ lịch sử nguồn để warmup</small></div>
            <div className="method-timeline-segment warmup"><strong>Warmup / tuning</strong><span>2019–2020</span><small>Huấn luyện, validation và hiệu chuẩn ngưỡng regime</small></div>
            <div className="method-timeline-segment evaluation"><strong>Evaluation</strong><span>2021–2025</span><small>So sánh ngoài mẫu chính</small></div>
            <div className="method-timeline-segment holdout"><strong>Final holdout</strong><span>2026*</span><small>01/01 đến {dateOnly(mainQuality?.coverage_end_utc)}</small></div>
          </div>
          <div className="method-process-grid">
            {[
              { icon: <Database size={17} />, title: 'Lịch ngày UTC', text: 'Nến 5 phút được giữ theo lịch; ngày không đủ dữ liệu không bị nối tắt.' },
              { icon: <Timer size={17} />, title: `${data?.study_protocol?.window_days ?? 730} ngày rolling`, text: 'Cửa sổ chính được chọn theo ngày lịch, kết thúc tại forecast origin.' },
              { icon: <Target size={17} />, title: `Refit mỗi ${data?.study_protocol?.refit_every_days ?? 5} ngày`, text: 'Dự báo hằng ngày; trạng thái được cập nhật bằng thông tin đã quan sát.' },
              { icon: <LockKeyhole size={17} />, title: 'Nhãn đã quan sát', text: 'Chỉ nhãn mục tiêu hoàn tất trước thời điểm fit mới được đưa vào train.' },
            ].map((step) => <article className="method-process-card" key={step.title}><i>{step.icon}</i><strong>{step.title}</strong><p>{step.text}</p></article>)}
          </div>
          <p className="method-footnote">* Snapshot dữ liệu kết thúc {dateOnly(mainQuality?.coverage_end_utc)}; không gọi holdout là trọn năm 2026. Holdout đã được dùng cho QA/mô tả và không được mô tả là dữ liệu chưa từng được xem.</p>
        </MethodSection>

        <MethodSection id="methods">
          <SectionHeading number="4" title="Phương pháp" subtitle="Định nghĩa RV, cấu trúc mô hình, ước lượng VaR/ES và phân bổ rủi ro" icon={<Sigma size={19} />} />
          <div className="method-formula-grid">
            <article className="method-formula-card"><span>REALIZED VARIANCE · %²</span><strong>r<sub>t,i</sub> = 100 ln(C<sub>t,i</sub>/C<sub>t,i−1</sub>)<br />RV<sub>d,t</sub> = Σ<sub>i=1</sub><sup>288</sup> r<sub>t,i</sub>²</strong><p>Return log từ close của hai nến 5 phút liền nhau; RV là tổng bình phương trong ngày UTC và chỉ hợp lệ khi đủ 288 return liền nhau.</p></article>
            <article className="method-formula-card"><span>HAR-RV · HỒI QUY OLS</span><strong>Ŷ<sub>t</sub><sup>(h)</sup> = β₀ + β<sub>d</sub>RV<sub>d,t</sub> + β<sub>w</sub>RV<sub>w,t</sub> + β<sub>m</sub>RV<sub>m,t</sub></strong><p>Ŷ<sub>t</sub><sup>(h)</sup> dự báo tổng RV của h ngày kế tiếp (h = 1 hoặc 7). RV<sub>w,t</sub> và RV<sub>m,t</sub> lần lượt là trung bình rolling 5 và 22 ngày kết thúc tại ngày t; hồi quy dùng RV thô theo %².</p></article>
            <article className="method-formula-card"><span>GARCH(1,1) / GJR-GARCH · %²</span><strong>σ²<sub>t</sub> = ω + [α + γI(ε<sub>t−1</sub>&lt;0)]ε²<sub>t−1</sub> + βσ²<sub>t−1</sub></strong><p>r<sub>t</sub> = μ + ε<sub>t</sub>; innovations Student-t. GARCH đặt γ = 0, GJR ước lượng thêm γ bất đối xứng. Dự báo h ngày là tổng đường đi phương sai; với h = 7, Student-t không phải phân phối chính xác của tổng return.</p></article>
          </div>
          <div className="method-model-table-wrap"><table className="method-table"><thead><tr><th>Nhóm</th><th>Mô hình</th><th>Thiết lập / vai trò</th></tr></thead><tbody>
            <tr><td>Benchmark</td><td>Naive RV, Historical Mean</td><td>Baseline đơn giản để kiểm tra mức cải thiện dự báo</td></tr>
            <tr><td>Kinh tế lượng</td><td>HAR-RV, GARCH, GJR-GARCH</td><td>HAR-RV hồi quy trực tiếp tổng RV tương lai; GARCH/GJR dự báo tổng đường đi phương sai. Target h7 là tổng RV của 7 ngày kế tiếp.</td></tr>
            <tr><td>Machine Learning</td><td>Elastic Net, XGBoost</td><td>Dự báo log tổng RV; chuyển lại bằng exp(log forecast + log mean(exp(train residual))) với smearing chỉ tính trên train.</td></tr>
            <tr><td>Ensemble</td><td>Combo Econ, Combo Core 4</td><td>Trung bình variance thành phần hợp lệ; không đổi trọng số theo ngày thiếu</td></tr>
          </tbody></table></div>
          <div className="method-info-grid">
            <article><div><CircleAlert size={16} /><strong>Từ RV forecast sang VaR/ES một ngày</strong></div><p>Với horizon 1 ngày, GARCH/GJR dùng Student-t chuẩn hóa; các mô hình còn lại dùng filtered historical simulation trên residual chuẩn hóa ngoài mẫu của chính mô hình (cần tối thiểu 20 residual đã quan sát tại forecast time). VaR và ES là return đuôi trái, thường âm. VaR/ES không được suy ra trực tiếp cho horizon 7 ngày.</p></article>
            <article><div><SlidersHorizontal size={16} /><strong>Volatility targeting</strong></div><p>Strategy dùng target 15%/năm, giới hạn trọng số tối đa 1×, phí một chiều 5 bps và annualization 365 ngày. Đây là cấu hình mô phỏng cố định, không tối ưu trên holdout.</p></article>
          </div>
        </MethodSection>

        <MethodSection id="evaluation">
          <SectionHeading number="5" title="Đánh giá" subtitle="Chỉ số forecast, kiểm định rủi ro và tiêu chí diễn giải" icon={<ClipboardCheck size={19} />} />
          <div className="method-evaluation-grid">
            {[
              { number: '01', title: 'Độ chính xác dự báo', text: 'QLIKE là thước đo chính, RMSE và MAE bổ sung. Các mô hình được so sánh trên cùng tập ngày kiểm tra ngoài mẫu. QLIKE phạt nặng khi dự báo thấp hơn thực tế, phù hợp với quản trị rủi ro.', note: 'Diebold–Mariano trên hiệu số QLIKE · HAC (Newey–West) · hiệu chỉnh Harvey–Leybourne–Newbold (1997)' },
              { number: '02', title: 'So sánh VaR', text: 'Báo cáo số lần và tỷ lệ vi phạm (breach) ở mức tin cậy 95% và 99%, trên cùng tập ngày của mọi mô hình để đối chiếu công bằng.', note: 'Kupiec: độ phủ không điều kiện · Christoffersen: độc lập và độ phủ có điều kiện' },
              { number: '03', title: 'Trạng thái thị trường (regime)', text: 'Mỗi ngày được gán nhãn bằng thông tin sẵn có tại thời điểm dự báo. Điều kiện Crisis được xét trước; ngưỡng được hiệu chỉnh trên warmup rồi cố định trước khi đánh giá. Trước khi kết thúc warmup hoặc khi chưa đủ lịch sử 90 ngày, nhãn là Unclassified.', note: 'QLIKE được so theo từng regime, kèm số ngày của mỗi regime' },
              { number: '04', title: 'Giá trị kinh tế', text: 'So sánh chiến lược volatility targeting với buy-and-hold qua CAGR, Sharpe, drawdown và chi phí giao dịch.', note: 'Mô phỏng lịch sử, không phải dự báo lợi nhuận' },
            ].map((item) => <article className="method-evaluation-card" key={item.number}><span>{item.number}</span><div><strong>{item.title}</strong><p>{item.text}</p><small>{item.note}</small></div></article>)}
          </div>
          <div className="method-note caution"><CircleAlert size={16} /><p>Kupiec và Christoffersen chỉ kiểm tra độ phủ của <strong>VaR</strong>, không phải kiểm định chuẩn cho ES. p-value ≥ 0.05 nghĩa là chưa bác bỏ giả thuyết kiểm định, không phải chứng minh mô hình đúng.</p></div>
          <div className="method-subgrid">
            <div><strong>Quy tắc regime</strong><p>Crisis khi RV trung bình 22 ngày vượt phân vị 90% tính riêng cho từng coin trên warmup. Ngoài Crisis: Bear khi log return 90 ngày ≤ −10%, Bull khi ≥ +10%, các ngày còn lại là Normal. Trước khi kết thúc warmup hoặc khi chưa đủ lịch sử 90 ngày, nhãn là Unclassified. Các ngưỡng được cố định trước evaluation, không điều chỉnh sau khi xem kết quả.</p></div>
            <div><strong>Cửa sổ stress</strong><p>Các cửa sổ lấy theo file backtest của backend: COVID 12–16/03/2020, bán tháo 01–31/05/2021, Luna 07–13/05/2022 và FTX 06–14/11/2022. Sự kiện ngoài giai đoạn kiểm tra ngoài mẫu (như COVID 2020) được đánh dấu “ngoài mẫu”, không dùng làm kết quả kiểm định.</p></div>
          </div>
        </MethodSection>

        <MethodSection id="reproducibility">
          <SectionHeading number="6" title="Tái lập & kiểm tra" subtitle="Snapshot, hash giao thức, trạng thái pipeline và kiểm thử backend" icon={<ClipboardCheck size={19} />} />
          <div className="method-provenance-grid">
            <article><span>DATA SNAPSHOT</span><strong>{data?.snapshot_id ?? '—'}</strong><small>{data?.dataset_rows == null ? '—' : `${number(data.dataset_rows)} coin-day rows`}</small></article>
            <article><span>DATASET SHA-256</span><strong>{shortHash(data?.dataset_sha256 ?? null)}</strong><small>Hash dữ liệu đầu vào đã xử lý</small></article>
            <article><span>PROTOCOL SHA-256</span><strong>{shortHash(data?.protocol_sha256 ?? null)}</strong><small>Hash protocol đánh giá</small></article>
            <article><span>HOLDOUT PIPELINE</span><strong>{data?.holdout_pipeline_state ?? '—'}</strong><small>Holdout được phục vụ riêng evaluation</small></article>
          </div>
          <div className="method-validation-grid">
            <article><span className="method-validation-icon"><CheckCircle2 size={18} /></span><div><strong>Kiểm tra dataset</strong><p>{data?.backend_validation?.status ?? 'Chưa có trạng thái'} · {number(data?.backend_validation?.forecast_rows)} forecast rows</p><small>{number(data?.backend_validation?.common_scored_rows)} common scored rows · holdout scored: {String(data?.backend_validation?.holdout_scored ?? '—')}</small></div></article>
            <article><span className="method-validation-icon"><CheckCircle2 size={18} /></span><div><strong>Risk test suite</strong><p>{data?.risk_validation?.passed ? `${number(data.risk_validation.tests)} tests passed` : data?.risk_validation?.status ?? 'Chưa xác nhận'}</p><small>{number(data?.risk_validation?.failures)} failures · {number(data?.risk_validation?.errors)} errors</small></div></article>
          </div>
          <div className="method-repo-row"><div><FileText size={17} /><span>Backend lưu kết quả đã tính; dashboard đọc output, không fit lại mô hình.</span></div><a href={data?.repository_url ?? 'https://github.com/thanhnha39/Crypto-Tail-Risk-Volatility-Forecasting-Engine'} target="_blank" rel="noreferrer">Mở GitHub <ExternalLink size={14} /></a></div>
        </MethodSection>

        <MethodSection id="limitations">
          <SectionHeading number="7" title="Giới hạn nghiên cứu" subtitle="Điều kiện dữ liệu, giả định mô hình và phạm vi diễn giải" icon={<CircleAlert size={19} />} />
          <div className="method-limit-grid">
            {[
              'Chưa có dữ liệu order-book và độ sâu thanh khoản; OHLCV không mô tả đầy đủ market microstructure.',
              'Macro FRED chưa xác minh point-in-time availability; các biến này không nằm trong mô hình dự báo chính.',
              'Regime là quy tắc cố định, không phải mô hình Markov-switching; kết quả phụ thuộc ngưỡng hiệu chuẩn warmup.',
              'Các sự kiện stress lịch sử được chọn theo lịch trong protocol; COVID 2020 nằm ngoài evaluation 2021–2025.',
              `Snapshot holdout kết thúc ${dateOnly(mainQuality?.coverage_end_utc)}; mẫu ngắn làm kiểm định VaR 99% có công suất hạn chế.`,
              'Mô phỏng chiến lược chưa bao gồm slippage, latency và cash yield; không diễn giải là hiệu quả giao dịch thực tế.',
              'Turnover là proxy dựa trên volume, không phải turnover theo market capitalization.',
              'Kupiec/Christoffersen chỉ đánh giá VaR coverage; backend chưa có kiểm định hiệu chuẩn ES riêng.',
            ].map((item, index) => <article className="method-limit-card" key={item}><span>{String(index + 1).padStart(2, '0')}</span><p>{item}</p></article>)}
          </div>
        </MethodSection>

        <MethodSection id="references">
          <SectionHeading number="8" title="Tài liệu tham khảo" subtitle={`${PAPERS.length} tài liệu nền tảng về realized volatility, forecast evaluation và backtesting`} icon={<BookOpen size={19} />} />
          <div className="method-reference-list">{PAPERS.map((paper) => <a className="method-reference" href={paper.url} target="_blank" rel="noreferrer" key={paper.url}><span><strong>{paper.authors}</strong> {paper.title} <em>{paper.journal}</em></span><ExternalLink size={16} /></a>)}</div>
          <p className="method-footnote">Tài liệu tham khảo nêu nền tảng phương pháp; cấu hình thực nghiệm cụ thể được mô tả theo backend snapshot và protocol hash ở trên.</p>
        </MethodSection>
      </main>

      <aside className={`method-toc ${tocCollapsed ? 'collapsed' : ''}`}>
        {tocCollapsed ? <button type="button" className="method-toc-expand" onClick={() => setTocCollapsed(false)} aria-label="Mở mục lục"><Menu size={19} /></button> : (
          <div className="method-toc-card">
            <div className="method-toc-heading"><span>MỤC LỤC TRANG</span><button type="button" onClick={() => setTocCollapsed(true)} aria-label="Thu gọn mục lục"><Menu size={17} /></button></div>
            <nav>{SECTIONS.map(([id, label]) => <button type="button" key={id} className={activeSection === id ? 'active' : ''} onClick={() => goToSection(id)}>{label}</button>)}</nav>
            <button type="button" className="method-back-top" onClick={() => window.scrollTo({ top: 0, behavior: 'instant' })}><ArrowUp size={15} /> Về đầu trang</button>
          </div>
        )}
      </aside>
    </div>
  )
}

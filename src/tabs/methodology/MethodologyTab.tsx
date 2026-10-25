import { useQuery } from '@tanstack/react-query'
import { BookOpenText } from 'lucide-react'
import { api, apiPaths } from '../../lib/api'
import { MethodCard } from '../../components/DashboardParts'

interface MethodologyResponse {
  assets: string[]
  data_frequency: string
  evaluation_period: string
  holdout: string
  core_models: string[]
  risk_notes: string[]
}

export default function MethodologyTab() {
  const method = useQuery({ queryKey: ['methodology'], queryFn: async () => (await api.get<MethodologyResponse>(apiPaths.methodology)).data })
  const data = method.data
  return <><div className="notice"><span className="notice-icon"><BookOpenText size={17} /></span><div><strong>Phương pháp và giới hạn</strong><p>Nội dung được phục vụ bởi API theo quy ước và schema của dự án.</p></div><span className="notice-tag">RESEARCH NOTES</span></div><div className="method-grid"><MethodCard title="Tài sản & dữ liệu" value={`${data?.assets.join(' / ') ?? '—'} · ${data?.data_frequency ?? ''}`} /><MethodCard title="Giai đoạn đánh giá" value={data?.evaluation_period ?? '—'} /><MethodCard title="Holdout" value={data?.holdout ?? '—'} /><MethodCard title="Mô hình cốt lõi" value={data?.core_models.join(' · ') ?? '—'} /><MethodCard title="Đơn vị dự báo" value="RV variance: %² · volatility: %" /><MethodCard title="Đơn vị risk" value="Return, VaR, ES: % log return · đuôi trái" /></div><div className="panel method-notes"><h3>Quy ước khi đọc kết quả</h3><ul>{(data?.risk_notes ?? ['Đang tải dữ liệu…']).map((note) => <li key={note}>{note}</li>)}</ul><p>Forecast accuracy và tail-risk validation là hai phần đánh giá riêng. Không diễn giải volatility forecast như dự báo hướng giá; mẫu đánh giá hiện tại không bao gồm holdout 2026.</p></div></>
}

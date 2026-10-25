import type { ReactNode } from 'react'
import { BarChart3 } from 'lucide-react'

export function Metric({ label, value, suffix, note, icon }: { label: string; value: string; suffix: string; note: string; icon: ReactNode }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><i>{icon}</i></div><div className="metric-value">{value}<small>{suffix}</small></div><div className="metric-note">{note}</div></article>
}

export function ChartLegend() { return <span className="chart-legend"><i /> Forecast <i className="legend-muted" /> Actual</span> }

export function ChartEmpty({ error }: { error: unknown }) {
  return <div className="chart-empty"><div className="chart-lines"><span /><span /><span /><span /></div><div className="chart-empty-content"><BarChart3 size={24} /><strong>{error ? 'Không tải được dữ liệu' : 'Đang tải chuỗi dữ liệu'}</strong><small>{error instanceof Error ? error.message : 'Vui lòng chờ API phản hồi.'}</small></div><div className="chart-x"><span>2021</span><span>2022</span><span>2023</span><span>2024</span><span>2025</span></div></div>
}

export function DataTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return <div className="panel table-panel data-table-panel"><div className="panel-heading"><div><h3>{title}</h3><p>Dữ liệu đã tải từ API</p></div></div><div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column.toUpperCase()}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={`${row[0]}-${index}`}>{row.map((cell, cellIndex) => <td key={`${cellIndex}-${cell}`}>{cell}</td>)}</tr>) : <tr><td colSpan={columns.length}>Chưa có dữ liệu</td></tr>}</tbody></table></div></div>
}

export function MethodCard({ title, value }: { title: string; value: string }) { return <article className="panel method-card"><span>{title}</span><p>{value}</p></article> }
export function fmt(value: number | null | undefined, digits = 2) { return value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits) }

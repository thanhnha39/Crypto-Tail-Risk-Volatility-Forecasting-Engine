import { useMemo, useState } from 'react'
import { Activity, Database, Download, ShieldAlert } from 'lucide-react'
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { useMarket } from '../../lib/dashboardQueries'
import type { MarketPoint } from '../../lib/api'
import './market-data.css'

type SymbolCode = 'BTCUSDT' | 'ETHUSDT'
type RangeKey = '1y' | '3y' | 'all'
type Regime = 'normal' | 'bull' | 'bear' | 'crisis'
const COLORS: Record<Regime, string> = { normal: '#71839b', bull: '#46c3a0', bear: '#e4a321', crisis: '#ef7d7d' }
const LABELS: Record<Regime, string> = { normal: 'Normal', bull: 'Bull', bear: 'Bear', crisis: 'Crisis' }
const ORDER: Regime[] = ['normal', 'bull', 'bear', 'crisis']
const RANGES: Record<RangeKey, number> = { '1y': 365, '3y': 1095, all: Infinity }
const fmt = (n: number | null | undefined, digits = 2) => typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('vi-VN', { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '—'
const day = (s: string) => s.slice(0, 10)
const regimeOf = (s: string): Regime => s.toLowerCase() in COLORS ? s.toLowerCase() as Regime : 'normal'
const sqrtRV = (p: MarketPoint) => typeof p.rv_d === 'number' && p.rv_d >= 0 ? Math.sqrt(p.rv_d) : null

function inverseNormal(p: number) {
  const a = [-39.6968302866538,220.946098424521,-275.928510446969,138.357751867269,-30.6647980661472,2.50662827745924]
  const b = [-54.4760987982241,161.585836858041,-155.698979859887,66.8013118877197,-13.2806815528857]
  const c = [-0.00778489400243029,-0.322396458041136,-2.40075827716184,-2.54973253934373,4.37466414146497,2.93816398269878]
  const d = [0.00778469570904146,0.32246712907004,2.445134137143,3.75440866190742]
  if (p < .02425) { const q = Math.sqrt(-2*Math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1) }
  if (p > .97575) { const q = Math.sqrt(-2*Math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1) }
  const q=p-.5, r=q*q
  return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
}
function stats(x: number[]) {
  if (!x.length) return { n: 0, mean: null as number|null, sd: null as number|null, skew: null as number|null, kurt: null as number|null, jb: null as number|null, p: null as number|null }
  const mean=x.reduce((a,b)=>a+b,0)/x.length, m2=x.reduce((a,b)=>a+(b-mean)**2,0)/x.length
  if (!m2) return { n:x.length, mean, sd:0, skew:0, kurt:0, jb:0, p:1 }
  const m3=x.reduce((a,b)=>a+(b-mean)**3,0)/x.length, m4=x.reduce((a,b)=>a+(b-mean)**4,0)/x.length
  const skew=m3/m2**1.5, kurt=m4/m2**2-3, jb=x.length/6*(skew**2+kurt**2/4)
  return { n:x.length, mean, sd:Math.sqrt(x.reduce((a,b)=>a+(b-mean)**2,0)/Math.max(x.length-1,1)), skew, kurt, jb, p:Math.exp(-jb/2) }
}
function histogram(x: number[], bins=30) {
  if (!x.length) return []
  const lo=Math.min(...x), hi=Math.max(...x), w=(hi-lo||1)/bins
  const data=Array.from({length:bins},(_,i)=>({x:lo+w*(i+.5),observed:0,normal:0}))
  x.forEach(v=>data[Math.min(bins-1,Math.floor((v-lo)/w))].observed++)
  const s=stats(x)
  if (s.sd && s.mean!==null) data.forEach(d=>{const z=(d.x-s.mean!)/s.sd!; d.normal=x.length*w/(s.sd!*Math.sqrt(2*Math.PI))*Math.exp(-z*z/2)})
  return data
}
function acf(x: number[], max=60) {
  if (x.length<3) return []
  const mean=x.reduce((a,b)=>a+b,0)/x.length, den=x.reduce((a,b)=>a+(b-mean)**2,0)
  if (!den) return []
  return Array.from({length:Math.min(max,x.length-1)},(_,i)=>{const lag=i+1;let num=0;for(let j=lag;j<x.length;j++)num+=(x[j]-mean)*(x[j-lag]-mean);return {lag,acf:num/den}})
}
function qqData(x: number[], mean: number|null, sd: number|null) {
  if (!x.length || mean===null || sd===null) return []
  const sorted=[...x].sort((a,b)=>a-b), n=Math.min(120,sorted.length)
  return Array.from({length:n},(_,i)=>{const j=Math.min(sorted.length-1,Math.floor((i+.5)*sorted.length/n)), p=(j+.5)/sorted.length; return {theoretical:inverseNormal(p)*sd+mean,observed:sorted[j]}})
}
function PanelTitle({ title, subtitle, badge }: {title:string;subtitle:string;badge?:string}) {
  return <div className="md-panel-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>{badge&&<span className="md-badge">{badge}</span>}</div>
}
function Empty({ loading, error }: {loading:boolean;error:unknown}) {
  return <div className="md-empty"><Database size={23}/><strong>{loading?'Đang tải dữ liệu thị trường…':'Không thể tải dữ liệu thị trường'}</strong><span>{loading?'Đang truy vấn backend cho tài sản đã chọn.':error instanceof Error?error.message:'Hãy kiểm tra API backend rồi tải lại trang.'}</span></div>
}

export default function MarketDataTab({ symbol='BTCUSDT' }: { symbol?: SymbolCode }) {
  const [range,setRange]=useState<RangeKey>('all')
  const market=useMarket(symbol,3000), all=market.data?.series??[]
  const points=useMemo(()=>{if(!all.length)return [];const span=RANGES[range];if(!Number.isFinite(span))return all;const last=new Date(all.at(-1)!.origin_date).getTime(),cutoff=last-span*86400000;return all.filter(p=>new Date(p.origin_date).getTime()>=cutoff)},[all,range])
  const returns=useMemo(()=>points.flatMap(p=>typeof p.ret_d==='number'&&Number.isFinite(p.ret_d)?[p.ret_d]:[]),[points])
  const rv=useMemo(()=>points.flatMap(p=>{const v=sqrtRV(p);return v===null?[]:[{...p,date:day(p.origin_date),rvPct:v,regimeKey:regimeOf(p.regime)}]}),[points])
  const s=useMemo(()=>stats(returns),[returns]), hist=useMemo(()=>histogram(returns),[returns]), qq=useMemo(()=>qqData(returns,s.mean,s.sd),[returns,s.mean,s.sd])
  const rvValues=rv.map(p=>p.rvPct), acfData=useMemo(()=>acf(rvValues),[rvValues]), bound=acfData.length?1.96/Math.sqrt(rvValues.length):0
  const regimeCounts=ORDER.map(key=>{const count=points.filter(p=>regimeOf(p.regime)===key).length;return {key,count,share:points.length?100*count/points.length:0}})
  const runs=useMemo(()=>{const out:Array<{start:string;end:string;regime:Regime}>=[];rv.forEach(p=>{const last=out.at(-1);if(last?.regime===p.regimeKey)last.end=p.date;else out.push({start:p.date,end:p.date,regime:p.regimeKey})});return out},[rv])
  const q=market.data?.quality, expected=Number(q?.expected_days), eligible=Number(q?.days_eligible_rv)
  const coverage=expected>0?eligible/expected*100:null, start=points[0]?.origin_date, end=points.at(-1)?.origin_date
  const meanRV=rvValues.length?rvValues.reduce((a,b)=>a+b,0)/rvValues.length:null
  const loading=market.isLoading||market.isFetching
  const exportCsv=()=>{const header='origin_date,origin_segment,regime,rv_d_pct2,realized_volatility_pct,daily_return_pct';const rows=points.map(p=>[day(p.origin_date),p.origin_segment,p.regime,p.rv_d??'',sqrtRV(p)??'',p.ret_d??''].join(','));const blob=new Blob(['\\uFEFF'+[header,...rows].join('\\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=symbol.toLowerCase()+'_market_'+range+'.csv';a.click();URL.revokeObjectURL(url)}
  if (loading&&!market.data) return <div className="market-data-page"><Empty loading error={market.error}/></div>
  if (market.error&&!market.data) return <div className="market-data-page"><Empty loading={false} error={market.error}/></div>

  return <div className="market-data-page">
    <section className="md-panel md-history-panel">
      <PanelTitle title="Biến động thực tế & trạng thái thị trường" subtitle={'Chuỗi hằng ngày · '+symbol+' · độ biến động = √RV ngày'} badge={start&&end?day(start)+' — '+day(end):undefined}/>
      <div className="md-toolbar"><div className="md-legend">{ORDER.map(r=><span key={r}><i style={{background:COLORS[r]}}/>{LABELS[r]}</span>)}</div>
        <div className="md-actions"><div className="md-range">{(['1y','3y','all'] as RangeKey[]).map(k=><button key={k} className={range===k?'active':''} onClick={()=>setRange(k)} aria-pressed={range===k}>{k==='all'?'Toàn bộ':k==='1y'?'1 năm':'3 năm'}</button>)}</div><button className="md-export" onClick={exportCsv}><Download size={14}/> CSV</button></div>
      </div>
      <div className="md-main-chart">{rv.length?<ResponsiveContainer width="100%" height="100%"><ComposedChart data={rv} margin={{top:16,right:18,bottom:5,left:5}}>
        <defs><linearGradient id="mdArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f2a41b" stopOpacity={.3}/><stop offset="100%" stopColor="#f2a41b" stopOpacity={.01}/></linearGradient></defs>
        <CartesianGrid stroke="#203047" strokeDasharray="3 5" vertical={false}/>{runs.map((r,i)=><ReferenceArea key={r.start+i} x1={r.start} x2={r.end} fill={COLORS[r.regime]} fillOpacity={.08} ifOverflow="hidden"/>)}<XAxis dataKey="date" tickFormatter={(v:string)=>v.slice(0,7)} tick={{fill:'#92a1b5',fontSize:12}} tickLine={false} axisLine={false} minTickGap={42}/><YAxis tick={{fill:'#92a1b5',fontSize:12}} tickLine={false} axisLine={false} width={58} tickFormatter={(v:number)=>fmt(v,1)+'%'}/>
        <Tooltip labelFormatter={v=>'Ngày '+String(v)} formatter={(v,_n,item)=>[fmt(Number(v),3)+'% · RV='+fmt(Number(item.payload.rv_d),3)+'%²','Biến động thực tế']} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:9,color:'#e7edf6',fontSize:12}}/>
        <Area type="monotone" dataKey="rvPct" stroke="#f2a41b" strokeWidth={2.2} fill="url(#mdArea)" connectNulls={false}/>
      </ComposedChart></ResponsiveContainer>:<Empty loading={false} error={market.error}/>}</div>
      <div className="md-chart-caption"><span><i className="md-line-key"/>√RV ngày thực tế (%)</span><span><i className="md-band-key"/>Nền màu: regime trả về từ backend</span></div>
    </section>

    <section className="md-analysis-grid">
      <article className="md-panel md-analysis-panel"><PanelTitle title="Phân phối lợi suất" subtitle={'Lợi suất ngày · '+returns.length.toLocaleString('vi-VN')+' quan sát'} badge="Log returns (%)"/>
        <div className="md-small-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={hist} margin={{top:12,right:12,bottom:2,left:0}}><CartesianGrid stroke="#203047" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="x" type="number" domain={['dataMin','dataMax']} tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} tickFormatter={(v:number)=>fmt(v,1)+'%'}/><YAxis tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} width={34}/><Tooltip formatter={(v,n)=>[fmt(Number(v),1),n==='normal'?'Chuẩn tham chiếu':'Số phiên']} labelFormatter={v=>'Lợi suất '+fmt(Number(v),2)+'%'} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:9,color:'#e7edf6',fontSize:12}}/><Bar dataKey="observed" name="Số phiên" fill="#319cc4" radius={[2,2,0,0]}/><Line type="monotone" dataKey="normal" name="Chuẩn tham chiếu" stroke="#f2a41b" strokeDasharray="4 4" dot={false} strokeWidth={2}/></ComposedChart></ResponsiveContainer></div>
        <div className="md-insight"><span>Độ lệch chuẩn</span><strong>{fmt(s.sd,3)}%</strong></div><div className="md-conclusion"><b>KẾT LUẬN</b> Phân phối được tính từ lợi suất ngày thực tế do API trả về.</div>
      </article>
      <article className="md-panel md-analysis-panel"><PanelTitle title="Q-Q plot" subtitle="Lợi suất thực tế so với phân phối chuẩn lý thuyết" badge="Normal Q-Q"/>
        <div className="md-small-chart"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{top:12,right:12,bottom:12,left:0}}><CartesianGrid stroke="#203047" strokeDasharray="3 5"/><XAxis type="number" dataKey="theoretical" name="Lý thuyết" tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} tickFormatter={(v:number)=>fmt(v,1)+'%'} label={{value:'Phân vị lý thuyết (%)',position:'insideBottom',offset:-7,fill:'#8291a6',fontSize:11}}/><YAxis type="number" dataKey="observed" name="Quan sát" tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} width={38} tickFormatter={(v:number)=>fmt(v,1)+'%'}/><Tooltip formatter={v=>fmt(Number(v),3)+'%'} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:9,color:'#e7edf6',fontSize:12}}/>{qq.length>1&&<ReferenceLine segment={[{x:qq[0].theoretical,y:qq[0].theoretical},{x:qq.at(-1)!.theoretical,y:qq.at(-1)!.theoretical}]} stroke="#a3afc0" strokeDasharray="4 4"/>}<Scatter data={qq} fill="#f2a41b"/></ScatterChart></ResponsiveContainer></div>
        <div className="md-insight"><span>Jarque–Bera p-value</span><strong className={s.p!==null&&s.p<.05?'md-warn':'md-good'}>{fmt(s.p,4)}</strong></div><div className="md-conclusion"><b>KIỂM ĐỊNH</b> Jarque–Bera tính từ cùng mẫu lợi suất đang chọn.</div>
      </article>
      <article className="md-panel md-analysis-panel md-stats-panel"><PanelTitle title="Thống kê mô tả" subtitle={'Mẫu quan sát · '+symbol} badge={'N = '+returns.length.toLocaleString('vi-VN')}/>
        <div className="md-table-wrap"><table className="md-table"><thead><tr><th>Chỉ tiêu</th><th>{symbol.replace('USDT','')}</th></tr></thead><tbody><tr><td>Số quan sát</td><td>{s.n.toLocaleString('vi-VN')}</td></tr><tr><td>Trung bình lợi suất ngày</td><td>{fmt(s.mean,4)}%</td></tr><tr><td>Độ lệch chuẩn</td><td>{fmt(s.sd,3)}%</td></tr><tr><td>Skewness</td><td>{fmt(s.skew,3)}</td></tr><tr><td>Excess kurtosis</td><td>{fmt(s.kurt,3)}</td></tr><tr><td>Jarque–Bera p-value</td><td className={s.p!==null&&s.p<.05?'md-warn':'md-good'}>{fmt(s.p,4)}</td></tr><tr><td>RV ngày trung bình</td><td className="md-accent">{fmt(meanRV,3)}%</td></tr></tbody></table></div><p className="md-footnote">Tính trên khoảng thời gian hiện chọn.</p>
      </article>
    </section>

    <section className="md-regime-grid">
      <article className="md-panel md-acf-panel"><PanelTitle title="ACF của biến động thực tế" subtitle="Tự tương quan của √RV ngày từ lag 1 đến lag 60" badge="Daily RV"/>
        <div className="md-acf-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={acfData} margin={{top:16,right:12,bottom:4,left:0}}><CartesianGrid stroke="#203047" strokeDasharray="3 5" vertical={false}/><XAxis dataKey="lag" tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} interval={4} tickFormatter={(v:number)=>'k='+v}/><YAxis domain={[-1,1]} tick={{fill:'#92a1b5',fontSize:11}} tickLine={false} axisLine={false} width={34}/><ReferenceLine y={bound} stroke="#44bad6" strokeDasharray="4 4"/><ReferenceLine y={-bound} stroke="#44bad6" strokeDasharray="4 4"/><Tooltip formatter={v=>fmt(Number(v),3)} labelFormatter={v=>'Lag '+v} contentStyle={{background:'#091629',border:'1px solid #28405c',borderRadius:9,color:'#e7edf6',fontSize:12}}/><Bar dataKey="acf" name="ACF" radius={[2,2,0,0]}>{acfData.map(p=><Cell key={p.lag} fill={p.acf>=0?'#e99c12':'#349fc5'}/>)}</Bar></BarChart></ResponsiveContainer></div>
        <div className="md-acf-caption"><span>Ngưỡng tham khảo ±1.96/√n</span><strong><Activity size={14}/> Long-memory check</strong></div><div className="md-conclusion"><b>KẾT LUẬN</b> ACF được tính từ chuỗi √RV hợp lệ trong khoảng đang chọn.</div>
      </article>
      <article className="md-panel md-regime-panel"><PanelTitle title="Dòng thời gian regime" subtitle="Nhãn regime được backend cung cấp theo ngày" badge="Market regimes"/>
        <div className="md-regime-track">{regimeCounts.map(r=>r.count>0&&<span key={r.key} style={{width:r.share+'%',background:COLORS[r.key]}} title={LABELS[r.key]+': '+r.count+' ngày'}/>)}</div><div className="md-regime-dates"><span>{start?day(start).slice(0,4):'—'}</span><span>{end?day(end).slice(0,4):'—'}</span></div>
        <div className="md-table-wrap"><table className="md-table md-regime-table"><thead><tr><th>Trạng thái</th><th>Số ngày</th><th>Tỷ lệ</th></tr></thead><tbody>{regimeCounts.map(r=><tr key={r.key}><td><span className="md-regime-label"><i style={{background:COLORS[r.key]}}/>{LABELS[r.key]}</span></td><td>{r.count.toLocaleString('vi-VN')}</td><td style={{color:COLORS[r.key]}}>{fmt(r.share,1)}%</td></tr>)}</tbody></table></div><p className="md-regime-note">Số ngày và tỷ lệ tính trực tiếp từ các bản ghi đang hiển thị.</p>
      </article>
    </section>

    <section className="md-panel md-quality-panel"><PanelTitle title="Chất lượng dữ liệu & phạm vi mẫu" subtitle="Các chỉ số audit và phân vùng do API backend cung cấp" badge="Backend audit"/>
      <div className="md-quality-metrics"><div><span>Độ phủ RV hợp lệ</span><strong>{fmt(coverage,1)}%</strong><small>{fmt(eligible,0)} / {fmt(expected,0)} ngày dự kiến</small></div><div><span>Ngày thiếu bar</span><strong>{fmt(Number(q?.incomplete_days),0)}</strong><small>{fmt(Number(q?.missing_bars),0)} bar thiếu trên dataset</small></div><div><span>Bar đã làm sạch</span><strong>{fmt(Number(q?.clean_rows),0)}</strong><small>{fmt(Number(q?.quarantined_rows),0)} bar bị cách ly</small></div><div><span>Return lớn được gắn cờ</span><strong>{fmt(Number(q?.large_return_bars),0)}</strong><small>Trường audit của backend</small></div></div>
      <div className="md-inventory-heading"><h3>Phân vùng mẫu</h3><span>Theo sample segment trong response API</span></div>
      <div className="md-table-wrap"><table className="md-table md-inventory"><thead><tr><th>Phân vùng</th><th>Số ngày</th><th>Ngày RV hợp lệ</th><th>Bar thiếu</th></tr></thead><tbody>{(q?.daily_quality_by_segment??[]).map((r:any)=><tr key={r.sample_segment}><td>{r.sample_segment}</td><td>{fmt(Number(r.days),0)}</td><td>{fmt(Number(r.eligible_rv),0)}</td><td>{fmt(Number(r.missing_bars),0)}</td></tr>)}</tbody></table></div>
      <div className="md-quality-note"><ShieldAlert size={15}/><span>API market không cung cấp giá đóng cửa hoặc danh mục nguồn chi tiết; trang không hiển thị các chỉ số đó.</span></div>
    </section>
  </div>
}

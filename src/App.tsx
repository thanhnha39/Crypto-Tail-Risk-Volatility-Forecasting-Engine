import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, BookOpen, Calendar, CircleHelp, Download, Landmark, LayoutGrid, Menu, Moon, TrendingUp, Wifi } from 'lucide-react'
import { api, apiPaths } from './lib/api'
import OverviewTab from './tabs/overview/OverviewTab'
import MarketDataTab from './tabs/market-data/MarketDataTab'
import VolatilityForecastTab from './tabs/volatility-forecast/VolatilityForecastTab'
import RiskEconomicValueTab from './tabs/risk-economic-value/RiskEconomicValueTab'
import MethodologyTab from './tabs/methodology/MethodologyTab'

const tabs = [
  { id: 'overview', label: 'Tổng quan', icon: LayoutGrid, eyebrow: 'BẢNG ĐIỀU KHIỂN' },
  { id: 'market', label: 'Dữ liệu & trạng thái thị trường', icon: TrendingUp, eyebrow: 'DỮ LIỆU THỊ TRƯỜNG' },
  { id: 'forecast', label: 'Dự báo biến động', icon: Activity, eyebrow: 'DỰ BÁO NGOÀI MẪU' },
  { id: 'risk', label: 'VaR & giá trị kinh tế', icon: Landmark, eyebrow: 'RỦI RO ĐUÔI' },
  { id: 'method', label: 'Phương pháp & giới hạn', icon: BookOpen, eyebrow: 'TÀI LIỆU NGHIÊN CỨU' },
] as const
type TabId = (typeof tabs)[number]['id']

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [symbol, setSymbol] = useState<'BTCUSDT' | 'ETHUSDT'>('BTCUSDT')
  const [horizonDays, setHorizonDays] = useState<1 | 7>(1)
  const [darkMode, setDarkMode] = useState(true)
  const currentTab = tabs.find((tab) => tab.id === activeTab)!
  const Icon = currentTab.icon
  const health = useQuery({ queryKey: ['api-health'], queryFn: async () => (await api.get(apiPaths.health)).data })
  const exportData = async () => {
    try {
      const response = await api.get('/exports/dashboard.csv', { params: { symbol, horizon_days: horizonDays, window: 'rolling' }, responseType: 'blob' })
      const url = URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${symbol.toLowerCase()}_dashboard_h${horizonDays}.csv`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      window.alert('Không thể xuất dữ liệu. Hãy kiểm tra API backend đang chạy.')
    }
  }

  return (
    <div className={`app-shell ${darkMode ? 'theme-dark' : 'theme-light'}`}>
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" onClick={() => setActiveTab('overview')}>
          <span className="brand-mark"><Activity size={19} strokeWidth={2.4} /></span>
          <span className="brand-copy"><strong>CRYPTO <em>RISK</em></strong><small>Dự báo biến động và rủi ro đuôi</small></span>
        </a>
        <nav className="side-nav" aria-label="Điều hướng chính">
          {tabs.map(({ id, label, icon: TabIcon }) => (
            <button key={id} className={`nav-item ${activeTab === id ? 'active' : ''}`} onClick={() => { setActiveTab(id); setMobileOpen(false) }}>
              <TabIcon size={18} strokeWidth={1.8} /><span>{label}</span>{activeTab === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-filters">
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">BỘ LỌC</span>
            <div className="asset-filter-row">
              <button className={symbol === 'BTCUSDT' ? 'selected' : ''} onClick={() => setSymbol('BTCUSDT')} aria-pressed={symbol === 'BTCUSDT'}>
                <span className="asset-coin-icon bitcoin-icon" aria-hidden="true">₿</span>BTC
              </button>
              <button className={symbol === 'ETHUSDT' ? 'selected' : ''} onClick={() => setSymbol('ETHUSDT')} aria-pressed={symbol === 'ETHUSDT'}>
                <svg className="asset-coin-icon ethereum-icon" viewBox="0 0 24 32" aria-hidden="true"><path d="M12 1 1.7 16.2 12 21.5l10.3-5.3L12 1Z" fill="currentColor" opacity=".9"/><path d="M12 23.4 1.7 18.1 12 31l10.3-12.9L12 23.4Z" fill="currentColor" opacity=".65"/></svg>ETH
              </button>
            </div>
          </div>
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">THỜI GIAN DỰ BÁO</span>
            <div className="horizon-filter-row">
              <button className={horizonDays === 1 ? 'selected' : ''} onClick={() => setHorizonDays(1)}>1 ngày</button>
              <button className={horizonDays === 7 ? 'selected' : ''} onClick={() => setHorizonDays(7)}>7 ngày</button>
            </div>
          </div>
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">KHUNG THỜI GIAN</span>
            <div className="date-range-chip">
              <Calendar size={13} />
              <span>01/01/2021 – 30/09/2026</span>
            </div>
          </div>
          <button className="export-button" onClick={exportData}>
            <Download size={14} /> Xuất dữ liệu
          </button>
        </div>
        <div className="sidebar-bottom">
          <div className="connection">
            <span className={`connection-dot ${health.isSuccess ? 'live' : ''}`} />
            <span>{health.isSuccess ? 'API ĐÃ KẾT NỐI' : 'API CHƯA KẾT NỐI'}</span>
          </div>
          <small>Công cụ học thuật, không phải khuyến nghị đầu tư.</small>
        </div>
      </aside>
      <main className="main-area">
        <header className={`topbar ${activeTab === 'overview' ? 'topbar-overview' : activeTab === 'market' ? 'topbar-market' : ''}`}>
          <button className="mobile-menu" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Mở menu"><Menu size={20} /></button>
          <div className="breadcrumb">RESEARCH <span>/</span> <b>{currentTab.eyebrow}</b></div>
          <div className="topbar-right">
            <span className={`api-status ${health.isSuccess ? 'connected' : ''}`}><span /> {health.isSuccess ? 'Backend kết nối' : 'Chưa kết nối backend'}</span>
            <button className="help-button"><CircleHelp size={17} /> Hướng dẫn</button>
          </div>
        </header>
        <section className={`page-content ${activeTab === 'overview' ? 'page-content-overview' : activeTab === 'market' ? 'page-content-market' : ''}`}>
          <div className="page-heading">
            <div>
              {activeTab !== 'overview' && activeTab !== 'market' && <div className="eyebrow"><Icon size={14} /> {currentTab.eyebrow}</div>}
              <h1 className={(activeTab === 'overview' || activeTab === 'market') ? 'heading-overview' : ''}>{currentTab.label}</h1>
              <p>{activeTab === 'overview' ? 'Kết quả chính và mức rủi ro hiện tại của BTC và ETH' : <>Kết quả ngoài mẫu BTC và ETH <span>·</span> dữ liệu thị trường đến {String(health.data?.market_data_end ?? '—').slice(0, 10)}</>}</p>
            </div>
            {(activeTab === 'overview' || activeTab === 'market') ? (
              <div className="dark-mode-toggle" onClick={() => setDarkMode(!darkMode)} role="button" tabIndex={0} title="Chuyển chế độ giao diện">
                <Moon size={14} />
                <span>Chế độ tối</span>
                <span className={`toggle-pill ${darkMode ? 'on' : ''}`}>
                  <span className="toggle-circle" />
                </span>
              </div>
            ) : (
              <div className="period-note">Forecast evaluation · 2021–2025</div>
            )}
          </div>
          {activeTab === 'overview' && <OverviewTab symbol={symbol} horizonDays={horizonDays} onNavigateTab={(tab) => setActiveTab(tab as TabId)} />}
          {activeTab === 'market' && <MarketDataTab symbol={symbol} />}
          {activeTab === 'forecast' && <VolatilityForecastTab symbol={symbol} horizonDays={horizonDays} />}
          {activeTab === 'risk' && <RiskEconomicValueTab />}
          {activeTab === 'method' && <MethodologyTab />}
          <footer className="page-footer"><span><Wifi size={13} /> {health.isSuccess ? `API hoạt động · Snapshot ${health.data.data_snapshot ?? '—'}` : 'Đang chờ API · UTC'}</span><span>Research snapshot · UTC</span></footer>
        </section>
      </main>
    </div>
  )
}

export default App

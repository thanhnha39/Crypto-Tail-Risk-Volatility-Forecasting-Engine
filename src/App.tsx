import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, BookOpen, ChevronLeft, ChevronRight, Download, Landmark, LayoutGrid, TrendingUp, Wifi } from 'lucide-react'
import { api, apiPaths } from './lib/api'
import type { DashboardSample } from './lib/api'
import TopHeader from './components/TopHeader'
import OverviewTab from './tabs/overview/OverviewTab'
import MarketDataTab from './tabs/market-data/MarketDataTab'
import VolatilityForecastTab from './tabs/volatility-forecast/VolatilityForecastTab'
import RiskEconomicValueTab from './tabs/risk-economic-value/RiskEconomicValueTab'
import MethodologyTab from './tabs/methodology/MethodologyTab'

const tabs = [
  {
    id: 'overview', label: 'Tổng quan', icon: LayoutGrid, eyebrow: 'BẢNG ĐIỀU KHIỂN',
    module: 'MÔ-ĐUN I · TỔNG QUAN', subtitle: 'Dự án học thuật Crypto Risk',
    description: 'Kết quả chính và mức rủi ro hiện tại của BTC và ETH',
  },
  {
    id: 'market', label: 'Dữ liệu & trạng thái thị trường', icon: TrendingUp, eyebrow: 'DỮ LIỆU THỊ TRƯỜNG',
    module: 'MÔ-ĐUN II · DỮ LIỆU & REGIMES', subtitle: 'Nến 5 phút · nguồn thị trường và chất lượng dữ liệu',
    description: 'Khám phá dữ liệu BTC/ETH, độ đầy đủ của chuỗi và trạng thái thị trường.',
  },
  {
    id: 'forecast', label: 'Dự báo biến động', icon: Activity, eyebrow: 'DỰ BÁO NGOÀI MẪU',
    module: 'MÔ-ĐUN III · DỰ BÁO ĐỊNH LƯỢNG', subtitle: 'Dự án học thuật Crypto Risk',
    description: 'So sánh dự báo realized variance ngoài mẫu giữa các mô hình và benchmark.',
  },
  {
    id: 'risk', label: 'VaR & giá trị kinh tế', icon: Landmark, eyebrow: 'RỦI RO ĐUÔI',
    module: 'MÔ-ĐUN IV & V · TÀI CHÍNH ĐỊNH LƯỢNG', subtitle: 'VaR/ES · volatility targeting',
    description: 'Đánh giá rủi ro lỗ ở đuôi phân phối và kết quả mô phỏng chiến lược.',
  },
  {
    id: 'method', label: 'Phương pháp & Hạn chế', icon: BookOpen, eyebrow: 'PHƯƠNG PHÁP & HẠN CHẾ',
    module: 'MÔ-ĐUN VI · PHƯƠNG PHÁP & HẠN CHẾ', subtitle: 'Phương pháp nghiên cứu và các giới hạn',
    description: 'Dữ liệu, thiết kế đánh giá, khả năng tái lập và các hạn chế của nghiên cứu.',
  },
] as const
type TabId = (typeof tabs)[number]['id']

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [symbol, setSymbol] = useState<'BTCUSDT' | 'ETHUSDT'>('BTCUSDT')
  const [horizonDays, setHorizonDays] = useState<1 | 7>(1)
  const [sample, setSample] = useState<DashboardSample>('evaluation')
  const [darkMode, setDarkMode] = useState(true)
  const currentTab = tabs.find((tab) => tab.id === activeTab)!
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
    <div className={`app-shell ${darkMode ? 'theme-dark' : 'theme-light'} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" onClick={() => setActiveTab('overview')}>
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="17" stroke="currentColor" strokeDasharray="2 2" strokeOpacity=".55" strokeWidth="1.4" />
              <path d="m11 27 7-9 5 4 7-11" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
              <circle cx="30" cy="11" r="2.2" fill="currentColor" />
              <path d="M10 23v6m6-4v4m6-2v2m6-8v8" stroke="currentColor" strokeLinecap="round" strokeOpacity=".4" />
            </svg>
          </span>
          <span className="brand-copy"><strong>CRYPTO <em>RISK.</em></strong><small>Dự báo biến động &amp; Rủi ro</small></span>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            aria-label={sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
            aria-expanded={!sidebarCollapsed}
            title={sidebarCollapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </a>
        <nav className="side-nav" aria-label="Điều hướng chính">
          {tabs.map(({ id, label, icon: TabIcon }) => (
            <button key={id} title={label} className={`nav-item ${activeTab === id ? 'active' : ''}`} onClick={() => { setActiveTab(id); setMobileOpen(false) }}>
              <TabIcon size={18} strokeWidth={1.8} /><span>{label}</span>{activeTab === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-filters">
          <div className="sidebar-filter-heading">
            <span>BỘ LỌC MÔ PHỎNG</span>
            <i aria-label="Bộ lọc đang hoạt động" />
          </div>
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">TÀI SẢN (COIN)</span>
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
            <span className="sidebar-filter-label">KHUNG DỰ BÁO (HORIZON)</span>
            <div className="horizon-filter-row">
              <button className={horizonDays === 1 ? 'selected' : ''} onClick={() => setHorizonDays(1)}>1 ngày</button>
              <button className={horizonDays === 7 ? 'selected' : ''} onClick={() => setHorizonDays(7)}>7 ngày</button>
            </div>
          </div>
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">MẪU ĐÁNH GIÁ</span>
            <div className="horizon-filter-row">
              <button className={sample === 'evaluation' ? 'selected' : ''} onClick={() => setSample('evaluation')} aria-pressed={sample === 'evaluation'}>2021–2025</button>
              <button className={sample === 'holdout' ? 'selected' : ''} onClick={() => setSample('holdout')} aria-pressed={sample === 'holdout'}>Holdout 2026</button>
            </div>
          </div>
          <div className="sidebar-filter-group">
            <span className="sidebar-filter-label">KHOẢNG THỜI GIAN OUT-OF-SAMPLE</span>
            <div className="date-range-chip">
              <span>Backend API</span>
              <span aria-hidden="true">→</span>
              <span>{String(health.data?.market_data_end ?? '—').slice(0, 10)}</span>
            </div>
          </div>
        </div>
        <div className="sidebar-bottom">
          <button className="export-button" onClick={exportData}>
            <Download size={14} /> Xuất dữ liệu
          </button>
          <div className="connection">
            <span className={`connection-dot ${health.isSuccess ? 'live' : ''}`} />
            <span>{health.isSuccess ? 'API ĐÃ KẾT NỐI' : 'API CHƯA KẾT NỐI'}</span>
          </div>
          <small>Công cụ học thuật, không phải khuyến nghị đầu tư.</small>
        </div>
      </aside>
      <main className="main-area">
        <section className="page-content">
          <TopHeader
            module={currentTab.module}
            subtitle={currentTab.subtitle}
            title={currentTab.label}
            description={currentTab.description}
            isDarkMode={darkMode}
            onToggleDarkMode={() => setDarkMode((mode) => !mode)}
            onToggleMenu={() => setMobileOpen((open) => !open)}
          />
          {activeTab === 'overview' && <OverviewTab symbol={symbol} horizonDays={horizonDays} sample={sample} onNavigateTab={(tab) => setActiveTab(tab as TabId)} />}
          {activeTab === 'market' && <MarketDataTab symbol={symbol} />}
          {activeTab === 'forecast' && <VolatilityForecastTab symbol={symbol} horizonDays={horizonDays} sample={sample} />}
          {activeTab === 'risk' && <RiskEconomicValueTab symbol={symbol} sample={sample} />}
          {activeTab === 'method' && <MethodologyTab onNavigateTab={(tab) => setActiveTab(tab)} />}
          <footer className="page-footer"><span><Wifi size={13} /> {health.isSuccess ? `API hoạt động · Snapshot ${health.data.data_snapshot ?? '—'}` : 'Đang chờ API · UTC'}</span><span>Research snapshot · UTC</span></footer>
        </section>
      </main>
    </div>
  )
}

export default App

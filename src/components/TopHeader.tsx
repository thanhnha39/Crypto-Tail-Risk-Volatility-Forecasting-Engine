import { Menu, Moon, Sun } from 'lucide-react'
import './top-header.css'

interface TopHeaderProps {
  module: string
  subtitle: string
  title: string
  description: string
  isDarkMode: boolean
  onToggleDarkMode: () => void
  onToggleMenu: () => void
}

export default function TopHeader({
  module,
  subtitle,
  title,
  description,
  isDarkMode,
  onToggleDarkMode,
  onToggleMenu,
}: TopHeaderProps) {
  const ModeIcon = isDarkMode ? Moon : Sun
  const modeLabel = isDarkMode ? 'Chế độ tối' : 'Chế độ sáng'

  return (
    <header className="research-header">
      <button type="button" className="research-header-menu" onClick={onToggleMenu} aria-label="Mở menu">
        <Menu size={19} />
      </button>
      <div className="research-header-copy">
        <div className="research-header-meta">
          <span className="research-header-module">{module}</span>
          <span className="research-header-subtitle">{subtitle}</span>
        </div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <button
        type="button"
        className="research-header-theme"
        onClick={onToggleDarkMode}
        title={isDarkMode ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}
        aria-label={isDarkMode ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}
        aria-pressed={isDarkMode}
      >
        <ModeIcon size={16} />
        <span>{modeLabel}</span>
        <span className={`research-header-switch ${isDarkMode ? 'on' : ''}`} aria-hidden="true">
          <span />
        </span>
      </button>
    </header>
  )
}

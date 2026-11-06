import { NAV_ICONS } from './Icons'
import { NAV_ITEMS, canSeeNavItem } from '../constants/prompts'
import { IconShield } from './Icons'

export default function Sidebar({ active, onNavigate, profile, model, isAdmin, mobileOpen, onToggleMobile, onCloseMobile, branding }) {
  const visible = NAV_ITEMS.filter((item) => canSeeNavItem(item.id, null, isAdmin))
  const brandName = branding?.brand_name || 'JurisGuard'

  return (
    <>
      <button type="button" className="mobile-nav-toggle" onClick={onToggleMobile} aria-label="Open menu">
        ☰
      </button>
      {mobileOpen && <button type="button" className="sidebar-backdrop" aria-label="Close menu" onClick={onCloseMobile} />}
      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <IconShield className="sidebar-logo" />
          <div>
            <strong>{brandName}</strong>
            <small>Legal Intelligence</small>
          </div>
        </div>

        <nav className="sidebar-nav">
          {visible.map((item) => {
            const Icon = NAV_ICONS[item.id] || NAV_ICONS.research
            return (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${active === item.id ? 'active' : ''}`}
                onClick={() => { onNavigate(item.id); onCloseMobile?.() }}
              >
                <Icon className="nav-icon" />
                <span className="nav-text">
                  <span>{item.label}</span>
                  <small>{item.desc}</small>
                </span>
              </button>
            )
          })}
        </nav>

        <div className="sidebar-foot">
          <div className={`profile-chip ${profile === 'airgap' ? 'airgap' : 'dev'}`}>
            <span className="dot" />
            {profile === 'airgap' ? 'Air-gap profile' : 'Dev profile'}
          </div>
          {model && <small className="model-tag">{model}</small>}
        </div>
      </aside>
    </>
  )
}

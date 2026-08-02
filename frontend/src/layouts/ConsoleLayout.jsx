import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { endpoints } from '../services/apiClient'
import { useAuthStore } from '../store/authStore'

const NAV = [
  { to: '/app', label: 'Overview', end: true, icon: '◈' },
  { to: '/app/products', label: 'Products', icon: '▣' },
  { to: '/app/leads', label: 'Leads', icon: '◎' },
  { to: '/app/analytics', label: 'Analytics', icon: '◔' },
]

/**
 * Surfaces server-side configuration problems (missing Groq key, unreachable
 * database) at the top of the console. Without this the first symptom a founder
 * sees is the AI silently falling back mid-demo.
 */
function SetupBanner() {
  const [warnings, setWarnings] = useState([])
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    endpoints
      .health()
      .then((health) => setWarnings(health?.warnings || []))
      .catch(() => setWarnings([]))
  }, [])

  if (dismissed || warnings.length === 0) return null

  return (
    <div className="setup-banner">
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <span aria-hidden="true">⚠</span>
        <div className="grow stack stack-2">
          <strong className="small">Setup needs attention</strong>
          <ul className="small" style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          <span className="tiny">
            See <code className="mono">SETUP.md</code> for the fix. The console works meanwhile;
            the AI will use fallback replies until a key is configured.
          </span>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDismissed(true)}>
          ✕
        </button>
      </div>
    </div>
  )
}

export default function ConsoleLayout() {
  const founder = useAuthStore((s) => s.founder)
  const logout = useAuthStore((s) => s.logout)
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="console">
      <aside className={`console-sidebar${menuOpen ? ' open' : ''}`}>
        <div className="console-brand">
          <span className="brand-mark">◆</span>
          <span>DemoPilot</span>
        </div>

        <nav className="console-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `console-nav-link${isActive ? ' active' : ''}`}
            >
              <span className="console-nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="console-footer">
          <div className="stack stack-2">
            <span className="tiny dim truncate">{founder?.email}</span>
            <button type="button" className="btn btn-sm btn-block" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="console-main">
        <header className="console-topbar">
          <button
            type="button"
            className="btn btn-ghost btn-sm console-menu-btn"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            ☰
          </button>
          <span className="small muted">
            Signed in as <strong>{founder?.full_name || founder?.email}</strong>
          </span>
        </header>

        <main className="console-content">
          <SetupBanner />
          <Outlet />
        </main>
      </div>

      {menuOpen && <div className="console-scrim" onClick={() => setMenuOpen(false)} />}
    </div>
  )
}

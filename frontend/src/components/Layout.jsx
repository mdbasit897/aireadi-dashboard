import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Users, Activity, Database } from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/overview', icon: LayoutDashboard, label: 'Overview' },
  { to: '/explorer', icon: Users,           label: 'Patients' },
]

function NavItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
          isActive
            ? 'bg-brand-600/20 text-brand-300 border border-brand-600/30'
            : 'text-[var(--c-muted)] hover:text-[var(--c-text)] hover:bg-white/[0.04]'
        )
      }
    >
      <Icon size={16} strokeWidth={1.8} />
      {label}
    </NavLink>
  )
}

export default function Layout() {
  return (
    <div className="flex h-full min-h-screen">

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside
        className="w-56 flex-shrink-0 flex flex-col border-r py-6 px-3"
        style={{ borderColor: 'var(--c-border)', background: 'var(--c-surface)' }}
      >
        {/* Logo / project name */}
        <div className="px-3 mb-8">
          <div className="flex items-center gap-2.5 mb-1">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
              style={{ background: 'var(--c-accent)', color: '#fff' }}
            >
              AI
            </div>
            <span
              className="text-sm font-semibold tracking-tight"
              style={{ fontFamily: 'Syne, sans-serif' }}
            >
              AI-READI
            </span>
          </div>
          <p className="text-xs" style={{ color: 'var(--c-muted)' }}>
            Clinical Dashboard v3.0
          </p>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 flex-1">
          <p
            className="px-3 mb-2 text-xs uppercase tracking-widest"
            style={{ color: 'var(--c-muted)' }}
          >
            Navigation
          </p>
          {navItems.map(item => <NavItem key={item.to} {...item} />)}
        </nav>

        {/* Footer */}
        <div className="px-3 pt-4 border-t" style={{ borderColor: 'var(--c-border)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Database size={12} style={{ color: 'var(--c-muted)' }} />
            <span className="text-xs" style={{ color: 'var(--c-muted)' }}>
              AI-READI v3.0.0
            </span>
          </div>
          <p className="text-xs" style={{ color: 'var(--c-muted)', lineHeight: '1.4' }}>
            2,280 participants<br />
            T2D research use only
          </p>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto" style={{ background: 'var(--c-bg)' }}>
        <Outlet />
      </main>
    </div>
  )
}

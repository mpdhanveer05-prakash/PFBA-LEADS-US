import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/leads', label: 'Leads', icon: '◈' },
  { to: '/map', label: 'Map View', icon: '◎' },
  { to: '/verification', label: 'Verification', icon: '✓' },
  { to: '/sync', label: 'Sync Center', icon: '⟳' },
  { to: '/counties', label: 'Counties', icon: '◉' },
  { to: '/appeals', label: 'Appeals', icon: '◷' },
  { to: '/outreach', label: 'Outreach', icon: '✉' },
  { to: '/packets', label: 'Appeal Packets', icon: '⬡' },
]

export default function Layout() {
  const { logout, user } = useAuth()
  return (
    <div className="min-h-screen flex" style={{ minWidth: '1024px' }}>
      <aside className="w-56 bg-gray-900 text-gray-100 flex flex-col flex-shrink-0">
        <div className="px-6 py-5 border-b border-gray-700">
          <p className="text-xl font-bold tracking-tight">Pathfinder</p>
          <p className="text-xs text-gray-400 mt-0.5">Tax Appeal Intelligence</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-4 border-t border-gray-700 space-y-2">
          {user && (
            <div className="px-3 py-1.5">
              <p className="text-xs font-medium text-gray-200">{user.username}</p>
              <p className="text-xs text-gray-400 capitalize">{user.role}</p>
            </div>
          )}
          <button
            onClick={logout}
            className="w-full text-left px-3 py-2 rounded-md text-sm text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}

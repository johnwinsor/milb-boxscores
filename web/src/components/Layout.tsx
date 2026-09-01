import { NavLink, Outlet } from 'react-router-dom'
import { formatTimestamp, hoursSince } from '../lib/format'
import { useMeta } from '../lib/useData'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm transition-colors ${
    isActive ? 'bg-neutral-800 text-neutral-100' : 'text-neutral-400 hover:text-neutral-200'
  }`

export function Layout() {
  const { data: meta } = useMeta()
  const updated = formatTimestamp(meta?.last_ingest?.finished_at)
  const age = hoursSince(meta?.last_ingest?.finished_at)
  const stale = age !== null && age > 36

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-2.5">
          <NavLink to="/" className="mr-2 font-semibold tracking-tight text-neutral-100">
            Prospect Box Scores
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={linkClass}>Daily</NavLink>
            <NavLink to="/teams" className={linkClass}>Teams</NavLink>
            <NavLink to="/admin" className={linkClass}>Admin</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-xs text-neutral-500">
            {meta?.players_unresolved ? (
              <NavLink to="/admin" className="text-amber-500 hover:underline">
                {meta.players_unresolved} unresolved
              </NavLink>
            ) : null}
            {updated && (
              <span className={stale ? 'text-amber-500' : ''} title={stale ? 'Data is more than 36 hours old' : undefined}>
                updated {updated}
              </span>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5">
        <Outlet />
      </main>
    </div>
  )
}

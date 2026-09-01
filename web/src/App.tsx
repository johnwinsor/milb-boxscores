import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Loading } from './components/Status'
import { Daily } from './pages/Daily'
import { Teams } from './pages/Teams'

// Recharts is ~400kB and only the player page uses it; the admin editor is
// only ever opened by one person. Both load on demand so the daily report --
// the page everyone actually opens -- stays small.
const Player = lazy(() => import('./pages/Player').then((m) => ({ default: m.Player })))
const Admin = lazy(() => import('./pages/Admin').then((m) => ({ default: m.Admin })))

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Daily />} />
        <Route path="teams" element={<Teams />} />
        <Route
          path="player/:personId"
          element={<Suspense fallback={<Loading what="player" />}><Player /></Suspense>}
        />
        <Route
          path="admin"
          element={<Suspense fallback={<Loading what="admin" />}><Admin /></Suspense>}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

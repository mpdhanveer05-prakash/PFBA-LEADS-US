import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import LeadsPage from './pages/LeadsPage'
import MapPage from './pages/MapPage'
import VerificationPage from './pages/VerificationPage'
import SyncCenterPage from './pages/SyncCenterPage'
import CountiesPage from './pages/CountiesPage'
import AppealsPage from './pages/AppealsPage'
import OutreachPage from './pages/OutreachPage'
import AppealPacketsPage from './pages/AppealPacketsPage'
import LoginPage from './pages/LoginPage'
import { useAuth } from './hooks/useAuth'
import { ToastProvider } from './components/Toast'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/verification" element={<VerificationPage />} />
          <Route path="/sync" element={<SyncCenterPage />} />
          <Route path="/counties" element={<CountiesPage />} />
          <Route path="/appeals" element={<AppealsPage />} />
          <Route path="/outreach" element={<OutreachPage />} />
          <Route path="/packets" element={<AppealPacketsPage />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}

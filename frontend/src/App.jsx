import { CircularProgress, Stack } from '@mui/material'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ServicesPage from './pages/ServicesPage'
import ServiceDetailPage from './pages/ServiceDetailPage'
import ComparisonsPage from './pages/ComparisonsPage'
import ComparisonDetailPage from './pages/ComparisonDetailPage'
import ConsumersPage from './pages/ConsumersPage'
import PublishingPage from './pages/PublishingPage'
import NotificationsPage from './pages/NotificationsPage'

function Protected({ children }) {
  const { user, initializing } = useAuth()
  if (initializing) {
    return (
      <Stack mt={10} sx={{ alignItems: 'center' }}>
        <CircularProgress />
      </Stack>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}

function GuestOnly({ children }) {
  const { user, initializing } = useAuth()
  if (initializing) {
    return (
      <Stack mt={10} sx={{ alignItems: 'center' }}>
        <CircularProgress />
      </Stack>
    )
  }
  if (user) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      {/* auth pages are rendered bare (no nav bar) */}
      <Route
        path="/login"
        element={
          <GuestOnly>
            <LoginPage />
          </GuestOnly>
        }
      />
      <Route
        path="/register"
        element={
          <GuestOnly>
            <RegisterPage />
          </GuestOnly>
        }
      />

      {/* everything else lives inside the app shell and requires auth */}
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/services" element={<ServicesPage />} />
        <Route path="/services/:serviceId" element={<ServiceDetailPage />} />
        <Route path="/comparisons" element={<ComparisonsPage />} />
        <Route path="/comparisons/:comparisonId" element={<ComparisonDetailPage />} />
        <Route path="/consumers" element={<ConsumersPage />} />
        <Route path="/publishing" element={<PublishingPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

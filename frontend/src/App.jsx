import { CircularProgress, Stack } from '@mui/material'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

function Protected({ children }) {
  const { user, initializing } = useAuth()
  if (initializing) {
    return (
      <Stack alignItems="center" mt={10}>
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
      <Stack alignItems="center" mt={10}>
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

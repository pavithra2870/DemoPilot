import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { LoadingPage } from './components/ui'
import ConsoleLayout from './layouts/ConsoleLayout'
import Analytics from './pages/Analytics'
import LandingPage from './pages/LandingPage'
import LeadDetail from './pages/LeadDetail'
import Leads from './pages/Leads'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import Overview from './pages/Overview'
import ProductEditor from './pages/ProductEditor'
import ProductNew from './pages/ProductNew'
import Products from './pages/Products'
import PublicDemo from './pages/PublicDemo'
import Register from './pages/Register'
import { useAuthStore } from './store/authStore'

function RequireAuth({ children }) {
  const token = useAuthStore((s) => s.token)
  const founder = useAuthStore((s) => s.founder)
  const checking = useAuthStore((s) => s.checking)
  const location = useLocation()

  if (checking) return <LoadingPage label="Checking your session…" />
  if (!token || !founder) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

function RedirectIfAuthed({ children }) {
  const token = useAuthStore((s) => s.token)
  const checking = useAuthStore((s) => s.checking)
  if (checking) return <LoadingPage />
  if (token) return <Navigate to="/app" replace />
  return children
}

export default function App() {
  const bootstrap = useAuthStore((s) => s.bootstrap)

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />

      {/* Public demo — no auth, the link is the credential. */}
      <Route path="/d/:slug" element={<PublicDemo />} />

      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <Login />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <Register />
          </RedirectIfAuthed>
        }
      />

      <Route
        path="/app"
        element={
          <RequireAuth>
            <ConsoleLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Overview />} />
        <Route path="products" element={<Products />} />
        <Route path="products/new" element={<ProductNew />} />
        <Route path="products/:productId" element={<ProductEditor />} />
        <Route path="leads" element={<Leads />} />
        <Route path="leads/:sessionId" element={<LeadDetail />} />
        <Route path="analytics" element={<Analytics />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

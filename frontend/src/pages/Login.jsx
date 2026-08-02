import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Alert, Field, Spinner } from '../components/ui'
import { useAuthStore } from '../store/authStore'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, submitting, error, clearError } = useAuthStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    const ok = await login(email.trim(), password)
    if (ok) navigate(location.state?.from || '/app', { replace: true })
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="stack stack-2" style={{ marginBottom: '1.4rem' }}>
          <Link to="/" className="row" style={{ gap: '0.45rem', color: 'var(--text)' }}>
            <span style={{ color: 'var(--accent)', fontSize: '1.1rem' }}>◆</span>
            <strong>DemoPilot</strong>
          </Link>
          <h1 style={{ fontSize: '1.3rem', marginTop: '0.6rem' }}>Welcome back</h1>
          <p className="small muted">Sign in to your founder console.</p>
        </div>

        <form className="stack stack-4" onSubmit={submit}>
          {error && (
            <Alert kind="error" onDismiss={clearError}>
              {error}
            </Alert>
          )}

          <Field label="Email" required>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
              required
            />
          </Field>

          <Field label="Password" required>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </Field>

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting && <Spinner light />}
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="small muted center" style={{ marginTop: '1.15rem' }}>
          No account yet? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Alert, Field, Spinner } from '../components/ui'
import { useAuthStore } from '../store/authStore'

export default function Register() {
  const navigate = useNavigate()
  const { register, submitting, error, clearError } = useAuthStore()

  const [form, setForm] = useState({ fullName: '', email: '', password: '' })
  const [localError, setLocalError] = useState('')

  const update = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setLocalError('')
    if (form.password.length < 8) {
      setLocalError('Password must be at least 8 characters.')
      return
    }
    const ok = await register(form.email.trim(), form.password, form.fullName.trim())
    if (ok) navigate('/app', { replace: true })
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="stack stack-2" style={{ marginBottom: '1.4rem' }}>
          <Link to="/" className="row" style={{ gap: '0.45rem', color: 'var(--text)' }}>
            <span style={{ color: 'var(--accent)', fontSize: '1.1rem' }}>◆</span>
            <strong>DemoPilot</strong>
          </Link>
          <h1 style={{ fontSize: '1.3rem', marginTop: '0.6rem' }}>Create your account</h1>
          <p className="small muted">
            Set up an AI Sales Engineer that demos your product while you sleep.
          </p>
        </div>

        <form className="stack stack-4" onSubmit={submit}>
          {(error || localError) && (
            <Alert
              kind="error"
              onDismiss={() => {
                clearError()
                setLocalError('')
              }}
            >
              {localError || error}
            </Alert>
          )}

          <Field label="Your name">
            <input
              className="input"
              value={form.fullName}
              onChange={update('fullName')}
              placeholder="Alex Rivera"
              autoComplete="name"
            />
          </Field>

          <Field label="Email" required>
            <input
              className="input"
              type="email"
              value={form.email}
              onChange={update('email')}
              placeholder="you@company.com"
              autoComplete="email"
              required
            />
          </Field>

          <Field label="Password" hint="At least 8 characters." required>
            <input
              className="input"
              type="password"
              value={form.password}
              onChange={update('password')}
              placeholder="••••••••"
              autoComplete="new-password"
              minLength={8}
              required
            />
          </Field>

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting && <Spinner light />}
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="small muted center" style={{ marginTop: '1.15rem' }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}

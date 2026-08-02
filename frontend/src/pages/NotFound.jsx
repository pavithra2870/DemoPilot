import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="auth-page">
      <div className="auth-card center">
        <h1 style={{ fontSize: '2.4rem', marginBottom: '0.4rem' }}>404</h1>
        <p className="muted small" style={{ marginBottom: '1.2rem' }}>
          That page doesn’t exist.
        </p>
        <Link to="/" className="btn btn-primary">
          Back to home
        </Link>
      </div>
    </div>
  )
}

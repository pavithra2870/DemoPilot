/**
 * Shared presentational primitives.
 *
 * Small on purpose: these are the pieces repeated across the console, so they
 * live in one file rather than a folder of one-export modules.
 */

import { useEffect, useState } from 'react'

export function Spinner({ light = false }) {
  return <span className={`spinner${light ? ' spinner-light' : ''}`} aria-hidden="true" />
}

export function LoadingPage({ label = 'Loading…' }) {
  return (
    <div className="loading-page" role="status">
      <Spinner />
      <span className="small muted">{label}</span>
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="empty">
      <span className="empty-icon">⚠</span>
      <span className="empty-title">{title}</span>
      {message && <span className="empty-text">{message}</span>}
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon = '○', title, text, action }) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      {title && <span className="empty-title">{title}</span>}
      {text && <span className="empty-text">{text}</span>}
      {action}
    </div>
  )
}

export function Alert({ kind = 'info', children, onDismiss }) {
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <div className="grow">{children}</div>
      {onDismiss && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onDismiss}>
          ✕
        </button>
      )}
    </div>
  )
}

export function Field({ label, hint, error, children, required }) {
  return (
    <div className="field">
      {label && (
        <label className="label">
          {label}
          {required && <span style={{ color: 'var(--danger)' }}> *</span>}
        </label>
      )}
      {children}
      {error ? (
        <span className="hint" style={{ color: 'var(--danger)' }}>
          {error}
        </span>
      ) : (
        hint && <span className="hint">{hint}</span>
      )}
    </div>
  )
}

export function Card({ title, description, actions, children, footer }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-header">
          <div>
            {title && <h3>{title}</h3>}
            {description && (
              <p className="small muted" style={{ marginTop: '0.15rem' }}>
                {description}
              </p>
            )}
          </div>
          {actions && <div className="row">{actions}</div>}
        </header>
      )}
      <div className="card-body">{children}</div>
      {footer && <div className="card-header" style={{ borderBottom: 'none', borderTop: '1px solid var(--border)' }}>{footer}</div>}
    </section>
  )
}

export function IntentBadge({ classification, score }) {
  const key = (classification || '').toLowerCase().includes('high')
    ? 'high'
    : (classification || '').toLowerCase().includes('medium')
      ? 'medium'
      : 'low'
  return (
    <span className={`badge intent-${key}`}>
      {typeof score === 'number' && <strong>{score}</strong>}
      {classification || 'Unscored'}
    </span>
  )
}

/** Horizontal 0-100 meter used for score breakdowns. */
export function ScoreBar({ value, max, color }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  const tone = color || (pct >= 70 ? 'var(--intent-high)' : pct >= 40 ? 'var(--intent-medium)' : 'var(--intent-low)')
  return (
    <div
      style={{
        height: 6,
        background: 'var(--surface-3)',
        borderRadius: 100,
        overflow: 'hidden',
      }}
      role="img"
      aria-label={`${value} out of ${max}`}
    >
      <div style={{ width: `${pct}%`, height: '100%', background: tone, transition: 'width 300ms' }} />
    </div>
  )
}

/** Editable list of short strings (benefits, keywords, ICP industries…). */
export function TagInput({ value = [], onChange, placeholder = 'Add and press Enter' }) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const item = draft.trim()
    if (!item) return
    if (!value.includes(item)) onChange([...value, item])
    setDraft('')
  }

  return (
    <div className="stack stack-2">
      <div className="row row-wrap" style={{ gap: '0.35rem' }}>
        {value.map((item) => (
          <span key={item} className="chip chip-removable">
            {item}
            <button type="button" onClick={() => onChange(value.filter((v) => v !== item))} aria-label={`Remove ${item}`}>
              ✕
            </button>
          </span>
        ))}
        {value.length === 0 && <span className="tiny dim">Nothing added yet.</span>}
      </div>
      <input
        className="input"
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add()
          }
        }}
        onBlur={add}
      />
    </div>
  )
}

export function Modal({ open, title, onClose, children, width = 480 }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="modal" style={{ maxWidth: width }} role="dialog" aria-modal="true" aria-label={title}>
        <header className="card-header">
          <h3>{title}</h3>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="card-body">{children}</div>
      </div>
    </div>
  )
}

export function CopyButton({ text, label = 'Copy', className = 'btn btn-sm' }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard API needs a secure context; fall back to a selectable prompt.
      window.prompt('Copy this link:', text)
      return
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <button type="button" className={className} onClick={copy}>
      {copied ? '✓ Copied' : label}
    </button>
  )
}

export function StatTile({ label, value, sub, tone }) {
  return (
    <div className="card card-pad stat-tile">
      <span className="tiny dim" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
      <strong style={{ fontSize: '1.75rem', lineHeight: 1.1, color: tone || 'var(--text)' }}>
        {value}
      </strong>
      {sub && <span className="tiny muted">{sub}</span>}
    </div>
  )
}

/** Simple horizontal bar list — used for section engagement and top questions. */
export function BarList({ items, emptyText = 'No data yet.' }) {
  if (!items?.length) return <p className="small dim">{emptyText}</p>
  const max = Math.max(...items.map((i) => i.count), 1)

  return (
    <div className="stack stack-3">
      {items.map((item, index) => (
        <div key={`${item.label}-${index}`} className="stack stack-2">
          <div className="row-between" style={{ gap: '0.5rem' }}>
            <span className="small" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
              {item.label}
            </span>
            <span className="small bold nowrap">{item.count}</span>
          </div>
          <ScoreBar value={item.count} max={max} color="var(--accent)" />
          {item.extra && <span className="tiny dim">{item.extra}</span>}
        </div>
      ))}
    </div>
  )
}

export function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds || 0))
  if (s < 60) return `${s}s`
  const minutes = Math.floor(s / 60)
  if (minutes < 60) return `${minutes}m ${s % 60}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export function formatRelative(iso) {
  if (!iso) return '—'
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return '—'
  const diff = (Date.now() - then.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function titleCase(text) {
  return (text || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

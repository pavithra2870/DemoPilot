import { useState } from 'react'

import { Field, Spinner } from '../ui'
import { useDemoStore } from '../../store/demoStore'

export default function ContactModal() {
  const open = useDemoStore((s) => s.contactOpen)
  const config = useDemoStore((s) => s.config)
  const qualification = useDemoStore((s) => s.qualification)
  const closeContact = useDemoStore((s) => s.closeContact)
  const submitContact = useDemoStore((s) => s.submitContact)

  const [form, setForm] = useState({ name: '', email: '', company: '', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (!open) return null

  const cta = config?.cta || {}
  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    if (!form.email.trim()) {
      setError('An email is required so the team can reach you.')
      return
    }
    setBusy(true)
    setError(null)
    // Anything the AI already learned is sent along, so the founder gets the
    // full picture even if the prospect only fills in an email here.
    const result = await submitContact({
      name: form.name || qualification.name || '',
      email: form.email,
      company: form.company || qualification.company || '',
      job_title: qualification.job_title || '',
      note: form.note,
      cta_type: cta.type || 'contact',
    })
    setBusy(false)
    if (!result.ok) setError(result.error)
  }

  return (
    <div
      className="demo-modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && closeContact()}
    >
      <div className="demo-modal" role="dialog" aria-modal="true" aria-label="Contact details">
        <div className="stack stack-4">
          <div>
            <h2 style={{ fontSize: '1.15rem' }}>{cta.label || 'Get in touch'}</h2>
            <p className="small" style={{ color: 'var(--demo-text-2)', margin: '0.3rem 0 0' }}>
              {cta.note ||
                'Leave your details and the team will follow up with everything you asked about.'}
            </p>
          </div>

          {error && <div className="demo-error" style={{ margin: 0 }}>{error}</div>}

          <form className="stack stack-3" onSubmit={submit}>
            <Field label="Name">
              <input
                className="input"
                value={form.name || qualification.name || ''}
                onChange={update('name')}
                placeholder="Alex Rivera"
                autoComplete="name"
              />
            </Field>

            <Field label="Work email" required>
              <input
                className="input"
                type="email"
                value={form.email || qualification.email || ''}
                onChange={update('email')}
                placeholder="alex@company.com"
                autoComplete="email"
                required
                autoFocus
              />
            </Field>

            <Field label="Company">
              <input
                className="input"
                value={form.company || qualification.company || ''}
                onChange={update('company')}
                placeholder="ScaleUp"
                autoComplete="organization"
              />
            </Field>

            <Field label="Anything else?">
              <textarea
                className="input"
                rows={2}
                value={form.note}
                onChange={update('note')}
                placeholder="We'd want to see the Zendesk integration in detail."
              />
            </Field>

            <div className="row" style={{ marginTop: '0.3rem' }}>
              <button type="submit" className="demo-btn demo-btn-primary" disabled={busy}>
                {busy && <Spinner light />}
                {busy ? 'Sending…' : cta.label || 'Send'}
              </button>
              <button type="button" className="demo-btn" onClick={closeContact}>
                Not now
              </button>
            </div>
          </form>

          {cta.url && (
            <a
              href={cta.url}
              target="_blank"
              rel="noreferrer"
              className="small center"
              style={{ color: 'var(--demo-accent)' }}
            >
              Or book a time directly →
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

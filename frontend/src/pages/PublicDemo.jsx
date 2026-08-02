import { useEffect } from 'react'
import { useParams } from 'react-router-dom'

import ContactModal from '../components/demo/ContactModal'
import DemoChat from '../components/demo/DemoChat'
import DemoStage from '../components/demo/DemoStage'
import { Spinner } from '../components/ui'
import { useDemoStore } from '../store/demoStore'

export default function PublicDemo() {
  const { slug } = useParams()
  const {
    config, sessionId, loading, loadError, ended, contactSubmitted, leadScore,
    load, start, reset, openContact, finish,
  } = useDemoStore()

  useEffect(() => {
    load(slug)
    return () => reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug])

  if (loading) {
    return (
      <div className="demo-start">
        <div className="row" style={{ color: 'var(--demo-text-2)' }}>
          <Spinner light />
          <span>Loading demo…</span>
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="demo-start">
        <div className="demo-start-card">
          <h1>Demo unavailable</h1>
          <p style={{ color: 'var(--demo-text-2)' }}>{loadError}</p>
        </div>
      </div>
    )
  }

  if (!sessionId) return <StartScreen config={config} onStart={start} />
  if (ended) return <EndScreen config={config} leadScore={leadScore} contactSubmitted={contactSubmitted} />

  return (
    <div className="demo">
      <header className="demo-header">
        <div className="demo-brand">
          <span className="demo-logo">{(config?.name || 'D')[0].toUpperCase()}</span>
          <div style={{ minWidth: 0 }}>
            <div className="demo-title truncate">{config?.name}</div>
            <div className="demo-subtitle truncate">
              {config?.tagline || 'Interactive product demo'}
            </div>
          </div>
        </div>

        <div className="demo-header-actions">
          {!contactSubmitted ? (
            <button type="button" className="demo-btn demo-btn-primary" onClick={openContact}>
              {config?.cta?.label || 'Get in touch'}
            </button>
          ) : (
            <span className="badge badge-success">✓ Details sent</span>
          )}
          <button type="button" className="demo-btn" onClick={finish}>
            End demo
          </button>
        </div>
      </header>

      <div className="demo-body">
        <DemoStage />
        <DemoChat />
      </div>

      <ContactModal />
    </div>
  )
}

function StartScreen({ config, onStart }) {
  const benefits = (config?.main_benefits || []).slice(0, 4)

  return (
    <div className="demo-start">
      <div className="demo-start-card">
        <span className="demo-logo" style={{ margin: '0 auto 1rem' }}>
          {(config?.name || 'D')[0].toUpperCase()}
        </span>

        <h1>{config?.name}</h1>
        <p style={{ color: 'var(--demo-text-2)', margin: '0 0 0.4rem' }}>
          {config?.tagline || config?.description}
        </p>

        {config?.main_problem && (
          <p className="small" style={{ color: 'var(--demo-text-2)' }}>
            {config.main_problem}
          </p>
        )}

        {benefits.length > 0 && (
          <div className="demo-benefits">
            {benefits.map((benefit) => (
              <div key={benefit} className="demo-benefit">
                {benefit}
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="demo-btn demo-btn-primary"
          style={{ width: '100%', padding: '0.7rem', fontSize: '0.95rem' }}
          onClick={() => onStart()}
        >
          Start the demo
        </button>

        <p className="tiny" style={{ color: 'var(--demo-text-2)', marginTop: '0.9rem', marginBottom: 0 }}>
          An AI Sales Engineer will walk you through it — ask anything, and it will show you the
          parts that matter for your situation. No signup, no calendar.
        </p>
      </div>
    </div>
  )
}

function EndScreen({ config, leadScore, contactSubmitted }) {
  const cta = config?.cta || {}

  return (
    <div className="demo-end">
      <div className="demo-start-card">
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✓</div>
        <h1>Thanks for taking a look</h1>

        <p style={{ color: 'var(--demo-text-2)' }}>
          {contactSubmitted
            ? 'Your details are with the team — they’ll follow up with everything you asked about.'
            : `That’s the tour of ${config?.name || 'the product'}. Reach out whenever you’re ready to go deeper.`}
        </p>

        {leadScore?.reasons?.length > 0 && (
          <div
            className="stack stack-2"
            style={{
              textAlign: 'left',
              margin: '1.25rem 0',
              padding: '0.9rem',
              border: '1px solid var(--demo-border)',
              borderRadius: 'var(--radius)',
            }}
          >
            <span className="tiny" style={{ color: 'var(--demo-text-2)' }}>
              What the team will see about your session
            </span>
            {leadScore.reasons.slice(0, 4).map((reason) => (
              <span key={reason} className="small">
                · {reason}
              </span>
            ))}
          </div>
        )}

        <div className="row" style={{ justifyContent: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {cta.url && (
            <a href={cta.url} target="_blank" rel="noreferrer" className="demo-btn demo-btn-primary">
              {cta.label || 'Book a call'}
            </a>
          )}
          <button
            type="button"
            className="demo-btn"
            onClick={() => window.location.reload()}
          >
            Start over
          </button>
        </div>
      </div>
    </div>
  )
}

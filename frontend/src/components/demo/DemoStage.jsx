import { useEffect, useState } from 'react'

import { useDemoStore } from '../../store/demoStore'

/**
 * The product surface the AI drives.
 *
 * Every visual here is rendered from founder-supplied section data — the
 * "screenshot" is a described placeholder, not a real image, because the MVP
 * should work before a founder has uploaded any assets. When the AI issues a
 * `highlight`, that lands as a pill plus a flash on matching highlight cards.
 */
export default function DemoStage() {
  const config = useDemoStore((s) => s.config)
  const activeSection = useDemoStore((s) => s.activeSection)
  const visited = useDemoStore((s) => s.visited)
  const highlight = useDemoStore((s) => s.highlight)
  const panel = useDemoStore((s) => s.panel)
  const goToSection = useDemoStore((s) => s.goToSection)
  const setPanel = useDemoStore((s) => s.setPanel)
  const clearHighlight = useDemoStore((s) => s.clearHighlight)

  const sections = config?.sections || []
  const current = sections.find((s) => s.section_key === activeSection) || sections[0]

  // A highlight is an attention cue, not a mode — it fades on its own.
  useEffect(() => {
    if (!highlight) return undefined
    const timer = setTimeout(clearHighlight, 5000)
    return () => clearTimeout(timer)
  }, [highlight, clearHighlight])

  if (!current && sections.length === 0) {
    return (
      <div className="demo-stage">
        <div className="demo-screen">
          <div className="demo-visual">
            <div className="demo-visual-body">
              <span className="demo-visual-icon">◇</span>
              <p style={{ color: 'var(--demo-text-2)', margin: 0 }}>
                This demo has no sections configured yet.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const highlightLabel = highlight?.label?.toLowerCase() || ''

  return (
    <div className="demo-stage">
      <nav className="demo-tabs" aria-label="Demo sections">
        {sections.map((section) => (
          <button
            key={section.id}
            type="button"
            className={[
              'demo-tab',
              section.section_key === current?.section_key ? 'active' : '',
              visited.includes(section.section_key) ? 'visited' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => goToSection(section.section_key, 'user')}
          >
            {section.title}
          </button>
        ))}
      </nav>

      <div className="demo-screen">
        <div className={`demo-visual${highlight ? ' highlighted' : ''}`}>
          {highlight && <span className="highlight-pill">▸ {highlight.label}</span>}
          <div className="demo-visual-chrome">
            <span className="demo-dot" />
            <span className="demo-dot" />
            <span className="demo-dot" />
            <span className="demo-visual-label">
              {config?.name?.toLowerCase().replace(/\s+/g, '')}.app/{current?.section_key}
            </span>
          </div>
          <div className="demo-visual-body">
            <span className="demo-visual-icon">▦</span>
            <strong style={{ fontSize: '0.95rem' }}>
              {current?.visual_placeholder || current?.title}
            </strong>
            <span className="small" style={{ color: 'var(--demo-text-2)' }}>
              {current?.description}
            </span>
          </div>
        </div>

        <div className="stack stack-2">
          <h2 className="demo-section-title">{current?.title}</h2>
          {current?.description && <p className="demo-section-desc">{current.description}</p>}
        </div>

        {current?.feature_explanation && (
          <div className="demo-explain">{current.feature_explanation}</div>
        )}

        {current?.highlights?.length > 0 && (
          <div className="demo-highlights">
            {current.highlights.map((item, index) => {
              const label = (item.label || '').toLowerCase()
              const flash =
                highlightLabel &&
                label &&
                (highlightLabel.includes(label) || label.includes(highlightLabel))
              return (
                <div key={index} className={`demo-highlight-card${flash ? ' flash' : ''}`}>
                  <strong className="small">{item.label}</strong>
                  {item.detail && (
                    <p className="small" style={{ color: 'var(--demo-text-2)', margin: '0.2rem 0 0' }}>
                      {item.detail}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <PanelStrip config={config} panel={panel} setPanel={setPanel} />
      </div>
    </div>
  )
}

function PanelStrip({ config, panel, setPanel }) {
  const hasPricing = (config?.pricing_plans || []).length > 0 || config?.pricing_model
  const hasFaq = (config?.faqs || []).length > 0
  const hasIntegrations = (config?.integrations || []).length > 0

  if (!hasPricing && !hasFaq && !hasIntegrations) return null

  return (
    <div className="stack stack-3">
      <div className="row" style={{ gap: '0.4rem', flexWrap: 'wrap' }}>
        {hasPricing && (
          <button
            type="button"
            className={`demo-tab${panel === 'pricing' ? ' active' : ''}`}
            onClick={() => setPanel('pricing')}
          >
            Pricing
          </button>
        )}
        {hasFaq && (
          <button
            type="button"
            className={`demo-tab${panel === 'faq' ? ' active' : ''}`}
            onClick={() => setPanel('faq')}
          >
            FAQ
          </button>
        )}
        {hasIntegrations && (
          <button
            type="button"
            className={`demo-tab${panel === 'integrations' ? ' active' : ''}`}
            onClick={() => setPanel('integrations')}
          >
            Integrations
          </button>
        )}
      </div>

      {panel === 'pricing' && <PricingPanel config={config} onClose={() => setPanel(null)} />}
      {panel === 'faq' && <FaqPanel config={config} onClose={() => setPanel(null)} />}
      {panel === 'integrations' && (
        <IntegrationsPanel config={config} onClose={() => setPanel(null)} />
      )}
    </div>
  )
}

function PanelShell({ title, onClose, children }) {
  return (
    <div className="demo-panel">
      <div className="demo-panel-head">
        <span>{title}</span>
        <button type="button" className="demo-btn" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="demo-panel-body">{children}</div>
    </div>
  )
}

function PricingPanel({ config, onClose }) {
  const plans = config.pricing_plans || []
  return (
    <PanelShell title="Pricing" onClose={onClose}>
      {plans.length === 0 ? (
        <p className="small" style={{ color: 'var(--demo-text-2)', margin: 0 }}>
          {config.pricing_model
            ? `Pricing model: ${config.pricing_model}. Ask the AI for details.`
            : 'Pricing has not been published — ask the AI and it will tell you what it knows.'}
        </p>
      ) : (
        <div className="plan-grid">
          {plans.map((plan, index) => (
            <div key={index} className="plan-card">
              <div className="small bold">{plan.name}</div>
              <div className="plan-price">
                {plan.price}
                <span className="small" style={{ color: 'var(--demo-text-2)', fontWeight: 400 }}>
                  {' '}
                  {config.pricing_currency}/{plan.period || 'mo'}
                </span>
              </div>
              {plan.best_for && (
                <div className="tiny" style={{ color: 'var(--demo-text-2)', marginTop: '0.2rem' }}>
                  {plan.best_for}
                </div>
              )}
              {plan.includes?.length > 0 && (
                <ul className="plan-includes">
                  {plan.includes.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
      {(config.free_trial || config.pricing_notes) && (
        <p className="small" style={{ color: 'var(--demo-text-2)', marginTop: '0.85rem', marginBottom: 0 }}>
          {config.free_trial && <>Free trial: {config.free_trial}. </>}
          {config.pricing_notes}
        </p>
      )}
    </PanelShell>
  )
}

function FaqPanel({ config, onClose }) {
  return (
    <PanelShell title="Frequently asked" onClose={onClose}>
      {(config.faqs || []).map((faq, index) => (
        <div key={index} className="faq-item">
          <div className="faq-q">{faq.question}</div>
          <div className="faq-a">{faq.answer}</div>
        </div>
      ))}
    </PanelShell>
  )
}

function IntegrationsPanel({ config, onClose }) {
  return (
    <PanelShell title="Integrations" onClose={onClose}>
      <div className="demo-highlights">
        {(config.integrations || []).map((integration, index) => (
          <div key={index} className="demo-highlight-card">
            <strong className="small">{integration.name}</strong>
            {integration.description && (
              <p className="small" style={{ color: 'var(--demo-text-2)', margin: '0.2rem 0 0' }}>
                {integration.description}
              </p>
            )}
          </div>
        ))}
      </div>
      {config.security_info && (
        <p className="small" style={{ color: 'var(--demo-text-2)', marginTop: '0.85rem', marginBottom: 0 }}>
          {config.security_info}
        </p>
      )}
    </PanelShell>
  )
}

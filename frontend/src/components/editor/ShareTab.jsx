import { useEffect, useState } from 'react'

import { endpoints } from '../../services/apiClient'
import { Alert, Card, CopyButton, Spinner } from '../ui'

/**
 * Publishing is gated on a readiness check rather than a bare toggle: an empty
 * demo link is worse than no demo link, so the blockers are shown as a checklist.
 */
export default function ShareTab({ product, onProductChange }) {
  const [check, setCheck] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    endpoints
      .publishCheck(product.id)
      .then(setCheck)
      .catch((err) => setError(err.message))
  }

  useEffect(load, [product.id])

  const toggle = async (published) => {
    setBusy(true)
    setError(null)
    try {
      const updated = await endpoints.publishProduct(product.id, published)
      onProductChange(updated)
      load()
    } catch (err) {
      setError(
        err.details?.blockers
          ? `${err.message} ${err.details.blockers.join(' ')}`
          : err.message,
      )
    } finally {
      setBusy(false)
    }
  }

  const url = product.demo_url

  return (
    <div className="stack stack-4">
      {error && (
        <Alert kind="error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card
        title="Public demo link"
        description="Share this anywhere. No login, no scheduling — the AI handles the call."
      >
        <div className="stack stack-4">
          <div className="row-between">
            <div className="row" style={{ gap: '0.5rem' }}>
              <span className={`badge ${product.is_published ? 'badge-success' : 'badge-outline'}`}>
                {product.is_published ? '● Live' : '○ Draft'}
              </span>
              <span className="small muted">
                {product.is_published
                  ? 'Anyone with the link can start a demo.'
                  : 'Not visible to prospects yet.'}
              </span>
            </div>
            <button
              type="button"
              className={`btn btn-sm ${product.is_published ? '' : 'btn-primary'}`}
              onClick={() => toggle(!product.is_published)}
              disabled={busy || (!product.is_published && check && !check.ready)}
            >
              {busy && <Spinner light={!product.is_published} />}
              {product.is_published ? 'Unpublish' : 'Publish demo'}
            </button>
          </div>

          <div className="link-box">
            <span>{url}</span>
            <CopyButton text={url} className="btn btn-sm" />
          </div>

          {product.is_published && (
            <div className="row">
              <a href={`/d/${product.slug}`} target="_blank" rel="noreferrer" className="btn btn-sm">
                Open the demo →
              </a>
              <span className="tiny dim">Opens in a new tab as a prospect would see it.</span>
            </div>
          )}
        </div>
      </Card>

      <Card title="Readiness">
        {!check ? (
          <div className="row">
            <Spinner />
            <span className="small muted">Checking…</span>
          </div>
        ) : check.ready ? (
          <Alert kind="success">
            Everything is in place. Your AI Sales Engineer knows the product, has screens to show,
            and has an indexed knowledge base to answer from.
          </Alert>
        ) : (
          <div className="stack stack-3">
            <p className="small muted" style={{ margin: 0 }}>
              Finish these before publishing:
            </p>
            <ul className="small" style={{ margin: 0, paddingLeft: '1.2rem', lineHeight: 1.9 }}>
              {check.blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <Card title="Where to put the link">
        <ul className="small muted" style={{ margin: 0, paddingLeft: '1.2rem', lineHeight: 1.95 }}>
          <li>
            Replace “Book a demo” on your site — prospects get one immediately instead of a
            scheduling form.
          </li>
          <li>Send it in cold outreach so replies arrive already qualified.</li>
          <li>Add it to Product Hunt, your README, or your email signature.</li>
          <li>Drop it in a Slack or Discord community where scheduling a call is friction.</li>
        </ul>
      </Card>
    </div>
  )
}

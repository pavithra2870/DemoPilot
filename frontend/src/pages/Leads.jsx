import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  Card,
  EmptyState,
  ErrorState,
  IntentBadge,
  LoadingPage,
  formatRelative,
} from '../components/ui'
import { endpoints } from '../services/apiClient'

const INTENTS = ['All', 'High Intent', 'Medium Intent', 'Low Intent']

export default function Leads() {
  const navigate = useNavigate()
  const [leads, setLeads] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [productId, setProductId] = useState('')
  const [intent, setIntent] = useState('All')
  const [search, setSearch] = useState('')
  const [includeBounced, setIncludeBounced] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      endpoints.listLeads({
        product_id: productId || undefined,
        intent: intent === 'All' ? undefined : intent,
        include_bounced: includeBounced || undefined,
      }),
      endpoints.listProducts(),
    ])
      .then(([leadData, productData]) => {
        setLeads(leadData)
        setProducts(productData)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [productId, intent, includeBounced])

  // Search filters client-side: the list is already scoped to one founder and
  // capped, so a round-trip per keystroke would be pure latency.
  const visible = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return leads
    return leads.filter((lead) =>
      [lead.name, lead.company, lead.email, lead.pain_point, lead.industry]
        .filter(Boolean)
        .some((field) => field.toLowerCase().includes(query)),
    )
  }, [leads, search])

  if (loading && leads.length === 0) return <LoadingPage label="Loading leads…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Leads</h1>
          <p>
            Every prospect who had a real conversation, scored against your ideal customer profile.
          </p>
        </div>
      </div>

      <Card>
        <div className="row row-wrap" style={{ gap: '0.6rem' }}>
          <input
            className="input"
            style={{ maxWidth: 240 }}
            placeholder="Search name, company, pain point…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select
            className="select"
            style={{ maxWidth: 200 }}
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          >
            <option value="">All products</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>

          <select
            className="select"
            style={{ maxWidth: 170 }}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          >
            {INTENTS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>

          <label className="row small muted" style={{ gap: '0.35rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={includeBounced}
              onChange={(e) => setIncludeBounced(e.target.checked)}
            />
            Include visitors who left immediately
          </label>

          <div className="spacer" />
          <span className="small dim nowrap">
            {visible.length} {visible.length === 1 ? 'lead' : 'leads'}
          </span>
        </div>
      </Card>

      <Card>
        {visible.length === 0 ? (
          <EmptyState
            icon="◎"
            title={leads.length === 0 ? 'No leads yet' : 'Nothing matches those filters'}
            text={
              leads.length === 0
                ? 'Share a published demo link. Anyone who talks to your AI Sales Engineer shows up here with a score and a recommended next step.'
                : 'Try widening the filters or clearing the search.'
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Lead</th>
                  <th>Company</th>
                  <th>Industry</th>
                  <th>Pain point</th>
                  <th>Score</th>
                  <th>Recommended action</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((lead) => (
                  <tr
                    key={lead.session_id}
                    className="clickable"
                    onClick={() => navigate(`/app/leads/${lead.session_id}`)}
                  >
                    <td>
                      <div className="row" style={{ gap: '0.4rem' }}>
                        <span className="bold small">{lead.name}</span>
                        {lead.contact_requested && (
                          <span className="badge badge-success tiny">contacted</span>
                        )}
                      </div>
                      {lead.email && <div className="tiny dim">{lead.email}</div>}
                    </td>
                    <td className="small">{lead.company || '—'}</td>
                    <td className="small muted">{lead.industry || '—'}</td>
                    <td className="small muted" style={{ maxWidth: 220 }}>
                      <div className="truncate">{lead.pain_point || '—'}</div>
                    </td>
                    <td>
                      <IntentBadge classification={lead.classification} score={lead.score} />
                    </td>
                    <td className="small muted" style={{ maxWidth: 240 }}>
                      <div className="truncate">{lead.recommended_action}</div>
                    </td>
                    <td className="tiny dim nowrap">{formatRelative(lead.last_activity_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

import { useEffect, useState } from 'react'

import {
  BarList,
  Card,
  EmptyState,
  ErrorState,
  LoadingPage,
  ScoreBar,
  StatTile,
  formatDuration,
} from '../components/ui'
import { endpoints } from '../services/apiClient'

export default function Analytics() {
  const [data, setData] = useState(null)
  const [products, setProducts] = useState([])
  const [productId, setProductId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([endpoints.analytics(productId || undefined), endpoints.listProducts()])
      .then(([analytics, productList]) => {
        setData(analytics)
        setProducts(productList)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [productId])

  if (loading && !data) return <LoadingPage label="Loading analytics…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  const distribution = data?.score_distribution || {}
  const totalScored = Object.values(distribution).reduce((sum, n) => sum + n, 0)
  const maxDaily = Math.max(...(data?.daily_sessions || []).map((d) => d.count), 1)

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p>What prospects actually care about — which is rarely what you expect.</p>
        </div>
        <select
          className="select"
          style={{ maxWidth: 220 }}
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
      </div>

      {!data || data.sessions === 0 ? (
        <div className="card">
          <EmptyState
            icon="◔"
            title="No demo data yet"
            text="Once prospects start running through your demo, this page shows which sections they visit, what they ask, what they object to, and how their scores are distributed."
          />
        </div>
      ) : (
        <>
          <div className="stat-grid">
            <StatTile label="Sessions" value={data.sessions} />
            <StatTile
              label="Completed"
              value={data.completed_sessions}
              sub="Reached a natural end"
            />
            <StatTile label="Avg. duration" value={formatDuration(data.average_duration_seconds)} />
            <StatTile label="Avg. messages" value={data.average_messages} />
            <StatTile
              label="Contact conversion"
              value={`${data.contact_conversion_rate}%`}
              tone={data.contact_conversion_rate > 0 ? 'var(--intent-high)' : undefined}
            />
          </div>

          <div className="grid grid-2">
            <Card
              title="Section engagement"
              description="Where the AI took prospects, and where they went themselves."
            >
              <BarList
                items={data.section_views}
                emptyText="No section views recorded yet."
              />
            </Card>

            <Card title="Lead score distribution">
              {totalScored === 0 ? (
                <p className="small dim">No scored sessions yet.</p>
              ) : (
                <div className="stack stack-4">
                  {['High Intent', 'Medium Intent', 'Low Intent'].map((label) => {
                    const count = distribution[label] || 0
                    const pct = Math.round((count / totalScored) * 100)
                    const color = label.startsWith('High')
                      ? 'var(--intent-high)'
                      : label.startsWith('Medium')
                        ? 'var(--intent-medium)'
                        : 'var(--intent-low)'
                    return (
                      <div key={label} className="stack stack-2">
                        <div className="row-between">
                          <span className="small">{label}</span>
                          <span className="small bold">
                            {count} <span className="dim">({pct}%)</span>
                          </span>
                        </div>
                        <ScoreBar value={count} max={totalScored} color={color} />
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>
          </div>

          <div className="grid grid-2">
            <Card
              title="Most asked questions"
              description="Grouped by meaning, not exact wording. Gaps here belong in your FAQs."
            >
              <BarList
                items={data.top_questions}
                emptyText="No questions recorded yet."
              />
            </Card>

            <Card
              title="Most common objections"
              description="Add responses for these on the Profile tab so the AI handles them your way."
            >
              <BarList
                items={data.top_objections}
                emptyText="No objections recorded yet."
              />
            </Card>
          </div>

          <div className="grid grid-2">
            <Card title="Conversation intents" description="What the AI spent its turns doing.">
              <BarList items={data.intents} emptyText="No intent data yet." />
            </Card>

            <Card title="Sessions over time">
              {data.daily_sessions.length === 0 ? (
                <p className="small dim">No sessions recorded yet.</p>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-end',
                    gap: 3,
                    height: 130,
                    paddingTop: '0.5rem',
                  }}
                >
                  {data.daily_sessions.map((day) => (
                    <div
                      key={day.label}
                      title={`${day.label}: ${day.count} session${day.count === 1 ? '' : 's'}`}
                      style={{
                        flex: 1,
                        minWidth: 4,
                        height: `${Math.max(4, (day.count / maxDaily) * 100)}%`,
                        background: 'var(--accent)',
                        borderRadius: '2px 2px 0 0',
                        opacity: 0.85,
                      }}
                    />
                  ))}
                </div>
              )}
              {data.daily_sessions.length > 0 && (
                <div className="row-between tiny dim" style={{ marginTop: '0.4rem' }}>
                  <span>{data.daily_sessions[0].label}</span>
                  <span>{data.daily_sessions[data.daily_sessions.length - 1].label}</span>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}

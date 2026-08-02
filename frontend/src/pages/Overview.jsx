import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  Card,
  EmptyState,
  ErrorState,
  IntentBadge,
  LoadingPage,
  StatTile,
  formatDuration,
  formatRelative,
} from '../components/ui'
import { endpoints } from '../services/apiClient'

export default function Overview() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    endpoints
      .overview()
      .then(setStats)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return <LoadingPage label="Loading your dashboard…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  const noProducts = stats.products === 0
  const noSessions = stats.total_sessions === 0

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Overview</h1>
          <p>Everything your AI Sales Engineer has done while you were doing something else.</p>
        </div>
        <Link to="/app/products/new" className="btn btn-primary">
          + New product
        </Link>
      </div>

      {noProducts ? (
        <div className="card">
          <EmptyState
            icon="◆"
            title="Let’s build your first demo"
            text="Create a product profile, add your knowledge, and share the link. Prospects get a guided walkthrough; you get qualified leads."
            action={
              <Link to="/app/products/new" className="btn btn-primary btn-sm">
                Create a product
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <div className="stat-grid">
            <StatTile label="Demo sessions" value={stats.total_sessions} />
            <StatTile
              label="Prospects"
              value={stats.total_prospects}
              sub="Visitors who identified themselves"
            />
            <StatTile
              label="Qualified"
              value={stats.qualified_leads}
              sub="Score 40+"
              tone={stats.qualified_leads > 0 ? 'var(--intent-medium)' : undefined}
            />
            <StatTile
              label="High intent"
              value={stats.high_intent_leads}
              sub="Score 70+"
              tone={stats.high_intent_leads > 0 ? 'var(--intent-high)' : undefined}
            />
            <StatTile
              label="Conversion"
              value={`${stats.conversion_rate}%`}
              sub={`${stats.contact_requests} contact requests`}
            />
            <StatTile
              label="Avg. session"
              value={formatDuration(stats.average_duration_seconds)}
              sub={`Avg. score ${stats.average_score}`}
            />
          </div>

          {noSessions && (
            <div className="alert alert-info">
              <div>
                <strong className="small">No demo sessions yet.</strong>
                <p className="small" style={{ margin: '0.2rem 0 0' }}>
                  {stats.published_products === 0
                    ? 'Publish a product from its Share tab to get a public demo link.'
                    : 'Your demo is live — share the link and prospects will start showing up here.'}
                </p>
              </div>
            </div>
          )}

          <Card
            title="Recent leads"
            actions={
              <Link to="/app/leads" className="btn btn-sm">
                View all
              </Link>
            }
          >
            {stats.recent_leads.length === 0 ? (
              <EmptyState
                icon="◎"
                text="Leads appear here as soon as someone has a real conversation with your AI Sales Engineer."
              />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Lead</th>
                      <th>Company</th>
                      <th>Pain point</th>
                      <th>Score</th>
                      <th>Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_leads.map((lead) => (
                      <tr
                        key={lead.session_id}
                        className="clickable"
                        onClick={() => navigate(`/app/leads/${lead.session_id}`)}
                      >
                        <td>
                          <div className="bold small">{lead.name}</div>
                          {lead.email && <div className="tiny dim">{lead.email}</div>}
                        </td>
                        <td className="small">{lead.company || '—'}</td>
                        <td className="small muted" style={{ maxWidth: 260 }}>
                          <div className="truncate">{lead.pain_point || '—'}</div>
                        </td>
                        <td>
                          <IntentBadge classification={lead.classification} score={lead.score} />
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
      )}
    </>
  )
}

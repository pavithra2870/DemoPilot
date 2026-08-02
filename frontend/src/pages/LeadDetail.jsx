import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  Alert,
  Card,
  EmptyState,
  ErrorState,
  IntentBadge,
  LoadingPage,
  ScoreBar,
  Spinner,
  formatDuration,
  formatRelative,
  titleCase,
} from '../components/ui'
import { endpoints } from '../services/apiClient'

const URGENCY_LABEL = {
  now: 'Follow up now',
  this_week: 'Follow up this week',
  this_month: 'Follow up this month',
  nurture: 'Nurture',
}

export default function LeadDetail() {
  const { sessionId } = useParams()
  const [lead, setLead] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    endpoints
      .getLead(sessionId)
      .then(setLead)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [sessionId])

  const generateReport = async () => {
    setGenerating(true)
    setGenerateError(null)
    try {
      const report = await endpoints.regenerateReport(sessionId)
      setLead((current) => ({ ...current, report }))
    } catch (err) {
      setGenerateError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <LoadingPage label="Loading lead…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!lead) return null

  const { qualification: q, lead_score: score, report } = lead
  const displayName = q.name || (q.company ? `Visitor from ${q.company}` : 'Anonymous visitor')

  return (
    <>
      <div className="stack stack-2">
        <Link to="/app/leads" className="back-link">
          ← Leads
        </Link>
        <div className="page-header">
          <div>
            <div className="row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
              <h1>{displayName}</h1>
              <IntentBadge classification={score.classification} score={score.score} />
              {lead.contact_requested && <span className="badge badge-success">Requested contact</span>}
              <span className="badge badge-outline">{lead.status}</span>
            </div>
            <p>
              {[q.job_title, q.company, q.industry].filter(Boolean).join(' · ') ||
                'No identity details collected'}
              {' — '}
              {lead.product_name}
            </p>
          </div>
          <div className="row">
            {q.email && (
              <a
                className="btn btn-primary btn-sm"
                href={`mailto:${q.email}?subject=${encodeURIComponent(`Following up on your ${lead.product_name} demo`)}${
                  report?.suggested_opening_line
                    ? `&body=${encodeURIComponent(report.suggested_opening_line)}`
                    : ''
                }`}
              >
                Email {q.name?.split(' ')[0] || 'them'}
              </a>
            )}
            <button type="button" className="btn btn-sm" onClick={generateReport} disabled={generating}>
              {generating && <Spinner />}
              {report ? 'Regenerate brief' : 'Generate brief'}
            </button>
          </div>
        </div>
      </div>

      {generateError && (
        <Alert kind="error" onDismiss={() => setGenerateError(null)}>
          {generateError}
        </Alert>
      )}

      <div className="lead-layout">
        {/* ---- Left column -------------------------------------------------- */}
        <div className="stack stack-4">
          <Card
            title="AI lead brief"
            description="Generated from the transcript. Written for a founder deciding where to spend an hour."
          >
            {!report ? (
              <EmptyState
                icon="✎"
                text="No brief yet. Generate one to get a summary, what they engaged with, and a specific recommended next step."
                action={
                  <button type="button" className="btn btn-primary btn-sm" onClick={generateReport} disabled={generating}>
                    {generating && <Spinner light />}
                    Generate brief
                  </button>
                }
              />
            ) : (
              <div className="stack stack-4">
                <p style={{ fontSize: '0.92rem', lineHeight: 1.65 }}>{report.summary}</p>

                <div className="row" style={{ gap: '0.4rem', flexWrap: 'wrap' }}>
                  <span className={`badge ${report.should_follow_up ? 'badge-success' : 'badge-outline'}`}>
                    {report.should_follow_up ? '✓ Worth following up' : 'Low priority'}
                  </span>
                  <span className="badge badge-accent">
                    {URGENCY_LABEL[report.follow_up_urgency] || report.follow_up_urgency}
                  </span>
                </div>

                {report.recommended_action && (
                  <div
                    style={{
                      padding: '0.75rem 0.9rem',
                      background: 'var(--accent-soft)',
                      border: '1px solid var(--accent-border)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div className="tiny bold" style={{ color: 'var(--accent-hover)', marginBottom: '0.2rem' }}>
                      RECOMMENDED ACTION
                    </div>
                    <div className="small">{report.recommended_action}</div>
                  </div>
                )}

                <div className="grid grid-2">
                  {report.interests?.length > 0 && (
                    <ListBlock title="Engaged with" items={report.interests} />
                  )}
                  {report.concerns?.length > 0 && (
                    <ListBlock title="Concerns raised" items={report.concerns} />
                  )}
                </div>

                {report.key_takeaways?.length > 0 && (
                  <ListBlock title="Key takeaways" items={report.key_takeaways} />
                )}

                {report.suggested_opening_line && (
                  <div>
                    <div className="tiny dim bold" style={{ marginBottom: '0.25rem' }}>
                      SUGGESTED OPENING LINE
                    </div>
                    <p className="small" style={{ fontStyle: 'italic', margin: 0 }}>
                      “{report.suggested_opening_line}”
                    </p>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card
            title="Conversation"
            description={`${lead.transcript.length} messages · ${formatDuration(lead.duration_seconds)}`}
          >
            <div className="transcript">
              {lead.transcript.map((message) => (
                <div key={message.id} className="transcript-turn">
                  <span className="transcript-role">
                    {message.role === 'user' ? 'Prospect' : 'AI Sales Engineer'}
                  </span>
                  <div
                    className={`transcript-bubble ${
                      message.role === 'user' ? 'transcript-user' : 'transcript-assistant'
                    }`}
                  >
                    {message.content}
                  </div>
                  {message.role === 'assistant' && (
                    <div className="transcript-meta">
                      {message.stage && <span className="badge">{message.stage}</span>}
                      {message.intent && <span className="badge">{message.intent.replace(/_/g, ' ')}</span>}
                      {message.action?.type && message.action.type !== 'none' && (
                        <span className="badge badge-accent">
                          {message.action.type}
                          {message.action.target ? ` → ${message.action.target}` : ''}
                        </span>
                      )}
                      {message.confidence === 'low' && (
                        <span className="badge badge-warning">low confidence</span>
                      )}
                      {message.sources?.map((source) => (
                        <span key={source.id} className="badge badge-outline" title={source.snippet}>
                          {source.label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ---- Right column ------------------------------------------------- */}
        <div className="stack stack-4">
          <Card title="Lead score" description="Computed from your ICP — every point is explained.">
            <div className="stack stack-4">
              <div className="score-headline">
                <span
                  className="score-number"
                  style={{
                    color:
                      score.score >= 70
                        ? 'var(--intent-high)'
                        : score.score >= 40
                          ? 'var(--intent-medium)'
                          : 'var(--intent-low)',
                  }}
                >
                  {score.score}
                </span>
                <span className="muted">/ 100</span>
                <div className="spacer" />
                <IntentBadge classification={score.classification} />
              </div>

              <div>
                {Object.entries(score.breakdown || {}).map(([key, part]) => (
                  <div key={key} className="score-row">
                    <div className="row-between" style={{ gap: '0.5rem' }}>
                      <span className="small bold">{titleCase(key)}</span>
                      <span className="small mono nowrap">
                        {part.points}/{part.max}
                      </span>
                    </div>
                    <ScoreBar value={part.points} max={part.max} />
                    <span className="tiny muted">{part.reason}</span>
                  </div>
                ))}
              </div>

              {score.missing_signals?.length > 0 && (
                <div className="alert alert-warning">
                  <div>
                    <strong className="small">Never established:</strong>{' '}
                    <span className="small">
                      {score.missing_signals.map((s) => s.replace(/_/g, ' ')).join(', ')}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card title="Qualification">
            {Object.keys(q).filter((k) => q[k]).length === 0 ? (
              <p className="small dim">Nothing was learned about this prospect.</p>
            ) : (
              <dl className="kv">
                {Object.entries(q)
                  .filter(([, value]) => value)
                  .map(([key, value]) => (
                    <div key={key} style={{ display: 'contents' }}>
                      <dt>{titleCase(key)}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
              </dl>
            )}
          </Card>

          <Card title="Demo engagement">
            <div className="stack stack-4">
              <dl className="kv">
                <dt>Started</dt>
                <dd>{formatRelative(lead.started_at)}</dd>
                <dt>Duration</dt>
                <dd>{formatDuration(lead.duration_seconds)}</dd>
                <dt>Final stage</dt>
                <dd className="capitalize">{lead.stage}</dd>
              </dl>

              {lead.sections_visited?.length > 0 && (
                <div>
                  <div className="tiny dim bold" style={{ marginBottom: '0.3rem' }}>
                    SECTIONS VISITED
                  </div>
                  <div className="row row-wrap" style={{ gap: '0.25rem' }}>
                    {lead.sections_visited.map((section) => (
                      <span key={section} className="badge badge-accent">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {lead.questions_asked?.length > 0 && (
                <div>
                  <div className="tiny dim bold" style={{ marginBottom: '0.3rem' }}>
                    QUESTIONS ASKED
                  </div>
                  <ul className="small muted" style={{ margin: 0, paddingLeft: '1.1rem', lineHeight: 1.7 }}>
                    {lead.questions_asked.slice(0, 8).map((question, index) => (
                      <li key={index}>{question}</li>
                    ))}
                  </ul>
                </div>
              )}

              {lead.objections_raised?.length > 0 && (
                <div>
                  <div className="tiny dim bold" style={{ marginBottom: '0.3rem' }}>
                    OBJECTIONS RAISED
                  </div>
                  <ul className="small muted" style={{ margin: 0, paddingLeft: '1.1rem', lineHeight: 1.7 }}>
                    {lead.objections_raised.map((objection, index) => (
                      <li key={index}>{objection}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </>
  )
}

function ListBlock({ title, items }) {
  return (
    <div>
      <div className="tiny dim bold" style={{ marginBottom: '0.3rem' }}>
        {title.toUpperCase()}
      </div>
      <ul className="small" style={{ margin: 0, paddingLeft: '1.1rem', lineHeight: 1.7 }}>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'

import { endpoints } from '../../services/apiClient'
import { Alert, Card, EmptyState, Spinner, formatRelative } from '../ui'

const ACCEPT = '.pdf,.docx,.txt,.md,.csv'

function formatBytes(bytes) {
  if (!bytes) return '0 KB'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function KnowledgeTab({ productId }) {
  const [documents, setDocuments] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [reindexing, setReindexing] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef(null)

  const load = async () => {
    try {
      const [docs, knowledge] = await Promise.all([
        endpoints.listDocuments(productId),
        endpoints.knowledgeStatus(productId),
      ])
      setDocuments(docs)
      setStatus(knowledge)
      return docs
    } catch (err) {
      setError(err.message)
      return []
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId])

  // Ingestion runs in a background task, so poll while anything is in flight.
  useEffect(() => {
    const pending = documents.some((d) => d.status === 'pending' || d.status === 'processing')
    if (!pending) return undefined
    const timer = setInterval(load, 2000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents])

  const upload = async (files) => {
    const list = Array.from(files || [])
    if (list.length === 0) return
    setUploading(true)
    setError(null)
    for (const file of list) {
      try {
        await endpoints.uploadDocument(productId, file)
      } catch (err) {
        setError(`${file.name}: ${err.message}`)
      }
    }
    setUploading(false)
    await load()
  }

  const remove = async (doc) => {
    if (!window.confirm(`Remove "${doc.filename}" from the knowledge base?`)) return
    try {
      await endpoints.deleteDocument(productId, doc.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const reindex = async () => {
    setReindexing(true)
    setError(null)
    try {
      await endpoints.reindex(productId)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setReindexing(false)
    }
  }

  return (
    <div className="stack stack-4">
      {error && (
        <Alert kind="error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card
        title="Knowledge base"
        description="What the AI is allowed to answer from. Anything not in here gets an honest “I can't confirm that”."
        actions={
          <button type="button" className="btn btn-sm" onClick={reindex} disabled={reindexing}>
            {reindexing && <Spinner />}
            {reindexing ? 'Rebuilding…' : 'Rebuild index'}
          </button>
        }
      >
        {loading ? (
          <div className="row">
            <Spinner />
            <span className="small muted">Loading…</span>
          </div>
        ) : (
          <div className="stack stack-4">
            <div className="stat-grid">
              <div>
                <span className="tiny dim">Indexed chunks</span>
                <div className="bold" style={{ fontSize: '1.35rem' }}>
                  {status?.chunks_total ?? 0}
                </div>
              </div>
              <div>
                <span className="tiny dim">From your profile</span>
                <div className="bold" style={{ fontSize: '1.35rem' }}>
                  {status?.profile_chunks ?? 0}
                </div>
              </div>
              <div>
                <span className="tiny dim">Documents</span>
                <div className="bold" style={{ fontSize: '1.35rem' }}>
                  {status?.documents_indexed ?? 0}/{status?.documents_total ?? 0}
                </div>
              </div>
              <div>
                <span className="tiny dim">Search ready</span>
                <div style={{ marginTop: '0.3rem' }}>
                  <span className={`badge ${status?.ready ? 'badge-success' : 'badge-warning'}`}>
                    {status?.ready ? 'Yes' : 'Not yet'}
                  </span>
                </div>
              </div>
            </div>

            <div className="tiny dim">
              Embeddings: <code className="mono">{status?.embedding_model || '—'}</code> · Vector
              store: <code className="mono">{status?.vector_backend || '—'}</code>
            </div>

            {status?.profile_chunks > 0 && status?.documents_total === 0 && (
              <Alert kind="success">
                Your product profile is already indexed — the AI can answer from your features,
                pricing, FAQs and objections without any upload. Add documents below for deeper
                technical answers.
              </Alert>
            )}
          </div>
        )}
      </Card>

      <Card title="Documents" description="PDF, DOCX, TXT, Markdown or CSV. Up to 10 MB each.">
        <div className="stack stack-4">
          <div
            className={`dropzone${dragging ? ' dragging' : ''}`}
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              upload(e.dataTransfer.files)
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && fileInput.current?.click()}
          >
            {uploading ? (
              <div className="row" style={{ justifyContent: 'center' }}>
                <Spinner />
                <span className="small">Uploading…</span>
              </div>
            ) : (
              <>
                <div style={{ fontSize: '1.5rem', opacity: 0.5 }}>↑</div>
                <div className="small bold">Drop files here or click to browse</div>
                <div className="tiny dim">
                  Docs are extracted, cleaned, chunked and embedded automatically.
                </div>
              </>
            )}
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                upload(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          {documents.length === 0 ? (
            <EmptyState
              icon="◫"
              text="No documents yet. Your product profile is still indexed, so the demo works — uploads just make the answers deeper."
            />
          ) : (
            <div>
              {documents.map((doc) => (
                <div key={doc.id} className="doc-row">
                  <span className={`status-dot status-${doc.status}`} title={doc.status} />
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="small bold truncate">{doc.filename}</div>
                    <div className="tiny dim">
                      {formatBytes(doc.size_bytes)}
                      {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                      {' · '}
                      {formatRelative(doc.created_at)}
                    </div>
                    {doc.error && (
                      <div
                        className="tiny"
                        style={{
                          color: doc.status === 'failed' ? 'var(--danger)' : 'var(--warning)',
                          marginTop: '0.15rem',
                        }}
                      >
                        {doc.error}
                      </div>
                    )}
                  </div>
                  <span className={`badge ${doc.status === 'indexed' ? 'badge-success' : doc.status === 'failed' ? 'badge-danger' : 'badge-warning'}`}>
                    {doc.status}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => remove(doc)}
                    aria-label={`Remove ${doc.filename}`}
                    style={{ color: 'var(--danger)' }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}

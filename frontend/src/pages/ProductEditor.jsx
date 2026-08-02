import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import IcpTab from '../components/editor/IcpTab'
import KnowledgeTab from '../components/editor/KnowledgeTab'
import ProfileTab from '../components/editor/ProfileTab'
import SectionsTab from '../components/editor/SectionsTab'
import ShareTab from '../components/editor/ShareTab'
import { Alert, ErrorState, LoadingPage, Spinner } from '../components/ui'
import { endpoints } from '../services/apiClient'

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'icp', label: 'Ideal customer' },
  { id: 'sections', label: 'Demo sections' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'share', label: 'Share' },
]

// Fields the profile/ICP tabs own. Sent on save; everything else is managed by
// its own dedicated endpoint.
const EDITABLE_FIELDS = [
  'name', 'tagline', 'description', 'category', 'target_customers', 'main_problem',
  'main_benefits', 'features', 'pricing', 'integrations', 'security_info', 'faqs',
  'objections', 'case_studies', 'icp', 'cta', 'welcome_message',
]

export default function ProductEditor() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'profile'

  const [product, setProduct] = useState(null)
  const [sections, setSections] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [savedAt, setSavedAt] = useState(null)

  const savedTimer = useRef(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const [productData, sectionData] = await Promise.all([
        endpoints.getProduct(productId),
        endpoints.listSections(productId),
      ])
      setProduct(productData)
      setSections(sectionData)
      setDirty(false)
    } catch (err) {
      setLoadError(err.message)
    } finally {
      setLoading(false)
    }
  }, [productId])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const reloadSections = useCallback(async () => {
    setSections(await endpoints.listSections(productId))
  }, [productId])

  // Warn on navigating away with unsaved profile edits.
  useEffect(() => {
    if (!dirty) return undefined
    const handler = (event) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  useEffect(() => () => clearTimeout(savedTimer.current), [])

  const patch = (partial) => {
    setProduct((current) => ({ ...current, ...partial }))
    setDirty(true)
    setSaveError(null)
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const payload = Object.fromEntries(
        EDITABLE_FIELDS.map((field) => [field, product[field]]).filter(
          ([, value]) => value !== undefined && value !== null,
        ),
      )
      const updated = await endpoints.updateProduct(productId, payload)
      setProduct(updated)
      setDirty(false)
      setSavedAt(Date.now())
      clearTimeout(savedTimer.current)
      savedTimer.current = setTimeout(() => setSavedAt(null), 2600)
    } catch (err) {
      setSaveError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeProduct = async () => {
    if (
      !window.confirm(
        `Delete "${product.name}"? This removes its demo link, knowledge base, sessions and leads. This cannot be undone.`,
      )
    ) {
      return
    }
    try {
      await endpoints.deleteProduct(productId)
      navigate('/app/products', { replace: true })
    } catch (err) {
      setSaveError(err.message)
    }
  }

  if (loading) return <LoadingPage label="Loading product…" />
  if (loadError) return <ErrorState message={loadError} onRetry={loadAll} />
  if (!product) return null

  const showSaveBar = tab === 'profile' || tab === 'icp'

  return (
    <>
      <div className="stack stack-2">
        <Link to="/app/products" className="back-link">
          ← Products
        </Link>
        <div className="page-header">
          <div>
            <div className="row" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
              <h1>{product.name}</h1>
              <span className={`badge ${product.is_published ? 'badge-success' : 'badge-outline'}`}>
                {product.is_published ? 'Live' : 'Draft'}
              </span>
            </div>
            <p>{product.tagline || 'Add a tagline on the Profile tab.'}</p>
          </div>
          <div className="row">
            {product.is_published && (
              <a href={`/d/${product.slug}`} target="_blank" rel="noreferrer" className="btn btn-sm">
                Preview demo
              </a>
            )}
            <button type="button" className="btn btn-sm btn-danger" onClick={removeProduct}>
              Delete
            </button>
          </div>
        </div>
      </div>

      <nav className="tabs">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tab${tab === item.id ? ' active' : ''}`}
            onClick={() => setSearchParams({ tab: item.id })}
          >
            {item.label}
            {item.id === 'sections' && sections.length > 0 && (
              <span className="tab-badge">{sections.length}</span>
            )}
          </button>
        ))}
      </nav>

      {saveError && (
        <Alert kind="error" onDismiss={() => setSaveError(null)}>
          {saveError}
        </Alert>
      )}

      {tab === 'profile' && <ProfileTab product={product} patch={patch} />}
      {tab === 'icp' && <IcpTab product={product} patch={patch} />}
      {tab === 'sections' && (
        <SectionsTab productId={productId} sections={sections} onReload={reloadSections} />
      )}
      {tab === 'knowledge' && <KnowledgeTab productId={productId} />}
      {tab === 'share' && <ShareTab product={product} onProductChange={setProduct} />}

      {showSaveBar && (
        <div
          className="card card-pad row-between"
          style={{ position: 'sticky', bottom: '1rem', boxShadow: 'var(--shadow-lg)' }}
        >
          <span className="small muted">
            {dirty
              ? 'Unsaved changes — saving also refreshes the knowledge index.'
              : savedAt
                ? '✓ Saved and reindexed'
                : 'Everything is saved.'}
          </span>
          <button type="button" className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving && <Spinner light />}
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      )}
    </>
  )
}

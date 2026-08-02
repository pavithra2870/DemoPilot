import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { CopyButton, EmptyState, ErrorState, LoadingPage, formatRelative } from '../components/ui'
import { endpoints } from '../services/apiClient'

export default function Products() {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    endpoints
      .listProducts()
      .then(setProducts)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return <LoadingPage label="Loading products…" />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Products</h1>
          <p>Each product gets its own knowledge base, demo walkthrough and public link.</p>
        </div>
        <Link to="/app/products/new" className="btn btn-primary">
          + New product
        </Link>
      </div>

      {products.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="▣"
            title="No products yet"
            text="Create a product profile, describe what it does, and DemoPilot builds an AI-guided demo around it."
            action={
              <Link to="/app/products/new" className="btn btn-primary btn-sm">
                Create your first product
              </Link>
            }
          />
        </div>
      ) : (
        <div className="grid grid-auto">
          {products.map((product) => (
            <article key={product.id} className="product-card">
              <div className="row-between" style={{ gap: '0.5rem' }}>
                <div style={{ minWidth: 0 }}>
                  <h3 className="truncate">{product.name}</h3>
                  {product.tagline && (
                    <p className="small muted truncate" style={{ margin: 0 }}>
                      {product.tagline}
                    </p>
                  )}
                </div>
                <span className={`badge ${product.is_published ? 'badge-success' : 'badge-outline'}`}>
                  {product.is_published ? 'Live' : 'Draft'}
                </span>
              </div>

              <div className="product-stats">
                <span>
                  <strong>{product.section_count}</strong> sections
                </span>
                <span>
                  <strong>{product.document_count}</strong> docs
                </span>
                <span>
                  <strong>{product.chunk_count}</strong> chunks
                </span>
                <span>
                  <strong>{product.session_count}</strong> demos
                </span>
              </div>

              {product.is_published && (
                <div className="link-box">
                  <span>{product.demo_url}</span>
                  <CopyButton text={product.demo_url} className="btn btn-sm btn-ghost" />
                </div>
              )}

              <div className="row-between">
                <span className="tiny dim">Updated {formatRelative(product.updated_at)}</span>
                <div className="row" style={{ gap: '0.35rem' }}>
                  {product.is_published && (
                    <a
                      href={`/d/${product.slug}`}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-sm"
                    >
                      Preview
                    </a>
                  )}
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() => navigate(`/app/products/${product.id}`)}
                  >
                    Edit
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  )
}

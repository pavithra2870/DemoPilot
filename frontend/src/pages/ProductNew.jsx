import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Alert, Field, Spinner } from '../components/ui'
import { endpoints } from '../services/apiClient'

/**
 * Deliberately minimal: name + what it does + who it's for + the problem.
 * That is enough for the AI to hold a coherent first conversation, and the full
 * editor handles everything else. A 30-field form on step one is how founders
 * abandon setup.
 */
export default function ProductNew() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    tagline: '',
    description: '',
    target_customers: '',
    main_problem: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const update = (key) => (event) => setForm((f) => ({ ...f, [key]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const product = await endpoints.createProduct(form)
      navigate(`/app/products/${product.id}`, { replace: true })
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="stack stack-2">
        <Link to="/app/products" className="back-link">
          ← Products
        </Link>
        <div className="page-header">
          <div>
            <h1>New product</h1>
            <p>
              Start with the essentials. You can add features, pricing, FAQs, documents and demo
              sections next.
            </p>
          </div>
        </div>
      </div>

      <form className="card card-pad stack stack-4" style={{ maxWidth: 660 }} onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}

        <Field label="Product name" required>
          <input
            className="input"
            value={form.name}
            onChange={update('name')}
            placeholder="HelpFlow"
            maxLength={120}
            required
            autoFocus
          />
        </Field>

        <Field label="Tagline" hint="One line a prospect would understand instantly.">
          <input
            className="input"
            value={form.tagline}
            onChange={update('tagline')}
            placeholder="Resolve support tickets before your team wakes up"
          />
        </Field>

        <Field
          label="What does it do?"
          hint="Two or three sentences. The AI uses this in every conversation."
        >
          <textarea
            className="textarea"
            value={form.description}
            onChange={update('description')}
            placeholder="HelpFlow is an AI support automation layer that sits on top of your existing helpdesk and resolves repetitive tickets automatically…"
            rows={4}
          />
        </Field>

        <Field label="Who is it for?">
          <input
            className="input"
            value={form.target_customers}
            onChange={update('target_customers')}
            placeholder="B2B SaaS companies with 20-500 employees"
          />
        </Field>

        <Field
          label="What problem does it solve?"
          hint="Used to score how well each prospect's pain matches your product."
        >
          <textarea
            className="textarea"
            value={form.main_problem}
            onChange={update('main_problem')}
            placeholder="Support teams drown in repetitive tickets and response times slip."
            rows={3}
          />
        </Field>

        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={submitting || !form.name.trim()}>
            {submitting && <Spinner light />}
            {submitting ? 'Creating…' : 'Create product'}
          </button>
          <Link to="/app/products" className="btn btn-ghost">
            Cancel
          </Link>
        </div>
      </form>
    </>
  )
}

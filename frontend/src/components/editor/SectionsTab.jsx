import { useState } from 'react'

import { endpoints } from '../../services/apiClient'
import RepeatableList from '../RepeatableList'
import { Alert, Card, EmptyState, Field, Modal, Spinner, TagInput } from '../ui'

const blankSection = () => ({
  section_key: '',
  title: '',
  description: '',
  feature_explanation: '',
  visual_placeholder: '',
  highlights: [],
  keywords: [],
})

/**
 * Demo sections are the screens the AI can drive. `section_key` is the action
 * target the model emits, so the editor surfaces it explicitly rather than
 * hiding it — a founder debugging "why didn't it navigate?" needs to see the id.
 */
export default function SectionsTab({ productId, sections, onReload }) {
  const [editing, setEditing] = useState(null)
  const [draft, setDraft] = useState(blankSection())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const openNew = () => {
    setDraft(blankSection())
    setEditing('new')
    setError(null)
  }

  const openEdit = (section) => {
    setDraft({ ...blankSection(), ...section })
    setEditing(section.id)
    setError(null)
  }

  const save = async () => {
    if (!draft.title.trim()) {
      setError('A title is required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const payload = {
        ...draft,
        section_key: draft.section_key.trim() || draft.title,
        order_index: draft.order_index ?? sections.length,
      }
      if (editing === 'new') await endpoints.createSection(productId, payload)
      else await endpoints.updateSection(productId, editing, payload)
      setEditing(null)
      await onReload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (section) => {
    if (!window.confirm(`Delete the "${section.title}" section?`)) return
    setBusy(true)
    try {
      await endpoints.deleteSection(productId, section.id)
      await onReload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const reorder = async (index, delta) => {
    const target = index + delta
    if (target < 0 || target >= sections.length) return
    const ids = sections.map((s) => s.id)
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    setBusy(true)
    try {
      await endpoints.reorderSections(productId, ids)
      await onReload()
    } finally {
      setBusy(false)
    }
  }

  const seed = async () => {
    setBusy(true)
    setError(null)
    try {
      await endpoints.seedSections(productId)
      await onReload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
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
        title="Demo sections"
        description="The screens your AI can navigate to. Order is the default walkthrough path."
        actions={
          <>
            {sections.length === 0 && (
              <button type="button" className="btn btn-sm" onClick={seed} disabled={busy}>
                {busy && <Spinner />} Generate from profile
              </button>
            )}
            <button type="button" className="btn btn-sm btn-primary" onClick={openNew}>
              + Add section
            </button>
          </>
        }
      >
        {sections.length === 0 ? (
          <EmptyState
            icon="▢"
            title="No sections yet"
            text="Without sections the AI can talk but cannot show anything. Generate a starter set from your product profile, then edit it."
            action={
              <button type="button" className="btn btn-primary btn-sm" onClick={seed} disabled={busy}>
                {busy && <Spinner light />} Generate from profile
              </button>
            }
          />
        ) : (
          <div className="stack stack-3">
            {sections.map((section, index) => (
              <div key={section.id} className="repeat-item">
                <div className="row-between" style={{ gap: '0.6rem', alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: '0.45rem', flexWrap: 'wrap' }}>
                      <strong className="small">{section.title}</strong>
                      <code className="mono badge badge-outline">{section.section_key}</code>
                    </div>
                    {section.description && (
                      <p className="small muted" style={{ margin: '0.25rem 0 0' }}>
                        {section.description}
                      </p>
                    )}
                    {section.keywords?.length > 0 && (
                      <div className="row row-wrap" style={{ gap: '0.25rem', marginTop: '0.4rem' }}>
                        {section.keywords.slice(0, 8).map((keyword) => (
                          <span key={keyword} className="badge">
                            {keyword}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="row" style={{ gap: '0.15rem' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => reorder(index, -1)}
                      disabled={index === 0 || busy}
                      aria-label="Move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => reorder(index, 1)}
                      disabled={index === sections.length - 1 || busy}
                      aria-label="Move down"
                    >
                      ↓
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => openEdit(section)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ color: 'var(--danger)' }}
                      onClick={() => remove(section)}
                      disabled={busy}
                      aria-label="Delete"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={Boolean(editing)}
        title={editing === 'new' ? 'New demo section' : 'Edit demo section'}
        onClose={() => setEditing(null)}
        width={620}
      >
        <div className="stack stack-4">
          {error && <Alert kind="error">{error}</Alert>}

          <div className="grid grid-2">
            <Field label="Title" required>
              <input
                className="input"
                value={draft.title}
                onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
                placeholder="Analytics Dashboard"
              />
            </Field>
            <Field
              label="Section id"
              hint="What the AI uses as an action target. Auto-generated if blank."
            >
              <input
                className="input mono"
                value={draft.section_key}
                onChange={(e) => setDraft((d) => ({ ...d, section_key: e.target.value }))}
                placeholder="analytics"
              />
            </Field>
          </div>

          <Field label="Short description" hint="One line shown under the section title.">
            <input
              className="input"
              value={draft.description}
              onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
              placeholder="Monitor performance and identify trends."
            />
          </Field>

          <Field
            label="Feature explanation"
            hint="The detail the AI draws on when walking a prospect through this screen."
          >
            <textarea
              className="textarea"
              rows={4}
              value={draft.feature_explanation}
              onChange={(e) => setDraft((d) => ({ ...d, feature_explanation: e.target.value }))}
            />
          </Field>

          <Field
            label="Visual placeholder"
            hint="Describes the mock screen shown on the demo stage."
          >
            <input
              className="input"
              value={draft.visual_placeholder}
              onChange={(e) => setDraft((d) => ({ ...d, visual_placeholder: e.target.value }))}
              placeholder="Analytics dashboard with deflection rate chart"
            />
          </Field>

          <Field
            label="Keywords"
            hint="Words that should make the AI navigate here. This is how it maps intent to screens."
          >
            <TagInput
              value={draft.keywords}
              onChange={(keywords) => setDraft((d) => ({ ...d, keywords }))}
              placeholder="analytics, reports, metrics…"
            />
          </Field>

          <div>
            <span className="label">Highlights</span>
            <p className="hint" style={{ marginBottom: '0.5rem' }}>
              Individual elements the AI can call attention to within this screen.
            </p>
            <RepeatableList
              items={draft.highlights || []}
              onChange={(highlights) => setDraft((d) => ({ ...d, highlights }))}
              newItem={{ id: '', label: '', detail: '' }}
              addLabel="Add highlight"
              itemLabel="Highlight"
              renderItem={(item, set) => (
                <div className="stack stack-3">
                  <Field label="Label">
                    <input
                      className="input"
                      value={item.label || ''}
                      onChange={(e) => set({ label: e.target.value })}
                      placeholder="Deflection rate"
                    />
                  </Field>
                  <Field label="Detail">
                    <input
                      className="input"
                      value={item.detail || ''}
                      onChange={(e) => set({ detail: e.target.value })}
                      placeholder="Share of tickets resolved without an agent."
                    />
                  </Field>
                </div>
              )}
            />
          </div>

          <div className="row">
            <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>
              {busy && <Spinner light />}
              {busy ? 'Saving…' : 'Save section'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>
              Cancel
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

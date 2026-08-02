import { EmptyState } from './ui'

/**
 * Generic editor for a list of objects (features, FAQs, pricing plans, objections…).
 *
 * The parent supplies a `renderItem(item, patch)` function; `patch` merges a partial
 * object into that row. Keeping the list mechanics here means each tab only
 * describes its own fields.
 */
export default function RepeatableList({
  items = [],
  onChange,
  newItem,
  renderItem,
  addLabel = 'Add item',
  itemLabel = 'Item',
  emptyText,
}) {
  const update = (index, partial) => {
    const next = items.map((item, i) => (i === index ? { ...item, ...partial } : item))
    onChange(next)
  }

  const remove = (index) => onChange(items.filter((_, i) => i !== index))

  const move = (index, delta) => {
    const target = index + delta
    if (target < 0 || target >= items.length) return
    const next = [...items]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <div className="stack stack-3">
      {items.length === 0 && emptyText && (
        <EmptyState icon="＋" text={emptyText} />
      )}

      {items.map((item, index) => (
        <div key={index} className="repeat-item">
          <div className="repeat-head">
            <span className="repeat-index">
              {itemLabel} {index + 1}
            </span>
            <div className="row" style={{ gap: '0.15rem' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => move(index, -1)}
                disabled={index === 0}
                aria-label="Move up"
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => move(index, 1)}
                disabled={index === items.length - 1}
                aria-label="Move down"
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => remove(index)}
                aria-label="Remove"
                style={{ color: 'var(--danger)' }}
              >
                ✕
              </button>
            </div>
          </div>
          {renderItem(item, (partial) => update(index, partial), index)}
        </div>
      ))}

      <div>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => onChange([...items, structuredClone(newItem)])}
        >
          + {addLabel}
        </button>
      </div>
    </div>
  )
}

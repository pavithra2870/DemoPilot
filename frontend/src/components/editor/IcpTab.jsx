import { Card, Field, TagInput } from '../ui'

const CTA_TYPES = [
  { value: 'book_call', label: 'Book a call' },
  { value: 'request_trial', label: 'Start a trial' },
  { value: 'contact', label: 'Contact the founder' },
  { value: 'waitlist', label: 'Join the waitlist' },
  { value: 'pricing', label: 'Request pricing' },
]

/**
 * The ICP is not decoration — it is the reference every lead score is measured
 * against, and it drives which qualification questions the agent prioritises.
 * The copy here says so, because an empty ICP quietly makes scores meaningless.
 */
export default function IcpTab({ product, patch }) {
  const icp = product.icp || {}
  const cta = product.cta || {}

  const patchIcp = (partial) => patch({ icp: { ...icp, ...partial } })
  const patchCta = (partial) => patch({ cta: { ...cta, ...partial } })

  const numeric = (value) => {
    if (value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  return (
    <div className="stack stack-4">
      <div className="alert alert-info">
        <div>
          <strong className="small">This drives your lead scores.</strong>
          <p className="small" style={{ margin: '0.2rem 0 0' }}>
            Company fit, budget fit and timeline are all measured against these values. Leave
            a field empty and that signal is scored neutrally rather than guessed at.
          </p>
        </div>
      </div>

      <Card title="Who is a good fit" description="Matched against what the AI learns about each prospect.">
        <div className="stack stack-4">
          <Field label="Target industries" hint="Matched against the prospect's stated industry.">
            <TagInput
              value={icp.industries || []}
              onChange={(industries) => patchIcp({ industries })}
              placeholder="SaaS — press Enter"
            />
          </Field>

          <Field
            label="Company sizes"
            hint="Use ranges like 11-50, 51-200. Head counts are bucketed automatically."
          >
            <TagInput
              value={icp.company_sizes || []}
              onChange={(company_sizes) => patchIcp({ company_sizes })}
              placeholder="51-200 — press Enter"
            />
          </Field>

          <Field label="Buyer job titles">
            <TagInput
              value={icp.job_titles || []}
              onChange={(job_titles) => patchIcp({ job_titles })}
              placeholder="Head of Support — press Enter"
            />
          </Field>

          <Field
            label="Typical pain points"
            hint="A prospect describing one of these scores full problem fit."
          >
            <TagInput
              value={icp.pain_points || []}
              onChange={(pain_points) => patchIcp({ pain_points })}
              placeholder="support ticket overload — press Enter"
            />
          </Field>

          <Field label="Tools they usually come from">
            <TagInput
              value={icp.current_alternatives || []}
              onChange={(current_alternatives) => patchIcp({ current_alternatives })}
              placeholder="Zendesk — press Enter"
            />
          </Field>
        </div>
      </Card>

      <Card title="Budget & timing">
        <div className="stack stack-4">
          <div className="grid grid-3">
            <Field label="Budget minimum" hint="Per month, in your currency.">
              <input
                className="input"
                type="number"
                min="0"
                value={icp.budget_min ?? ''}
                onChange={(e) => patchIcp({ budget_min: numeric(e.target.value) })}
                placeholder="100"
              />
            </Field>
            <Field label="Budget maximum">
              <input
                className="input"
                type="number"
                min="0"
                value={icp.budget_max ?? ''}
                onChange={(e) => patchIcp({ budget_max: numeric(e.target.value) })}
                placeholder="2000"
              />
            </Field>
            <Field label="Typical buying window" hint="In days. Leave empty to skip.">
              <input
                className="input"
                type="number"
                min="0"
                value={icp.ideal_timeline_days ?? ''}
                onChange={(e) => patchIcp({ ideal_timeline_days: numeric(e.target.value) })}
                placeholder="90"
              />
            </Field>
          </div>

          <Field label="Budget note">
            <input
              className="input"
              value={icp.budget_note || ''}
              onChange={(e) => patchIcp({ budget_note: e.target.value })}
              placeholder="Most customers land around $400/month."
            />
          </Field>
        </div>
      </Card>

      <Card
        title="Qualification criteria"
        description="What you need to know before spending time on a lead."
      >
        <div className="stack stack-4">
          <Field label="Must establish">
            <TagInput
              value={icp.qualification_criteria || []}
              onChange={(qualification_criteria) => patchIcp({ qualification_criteria })}
              placeholder="Has an existing helpdesk — press Enter"
            />
          </Field>

          <Field
            label="Disqualifiers"
            hint="A prospect matching one of these is capped at 30 and flagged in the score."
          >
            <TagInput
              value={icp.disqualifiers || []}
              onChange={(disqualifiers) => patchIcp({ disqualifiers })}
              placeholder="students, no budget — press Enter"
            />
          </Field>
        </div>
      </Card>

      <Card title="Call to action" description="What the AI recommends when a prospect is ready.">
        <div className="stack stack-4">
          <div className="grid grid-2">
            <Field label="Type">
              <select
                className="select"
                value={cta.type || 'book_call'}
                onChange={(e) => patchCta({ type: e.target.value })}
              >
                {CTA_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Button label">
              <input
                className="input"
                value={cta.label || ''}
                onChange={(e) => patchCta({ label: e.target.value })}
                placeholder="Book a 20-minute call"
              />
            </Field>
          </div>

          <Field label="Link" hint="Optional — a Cal.com or Calendly URL, for example.">
            <input
              className="input"
              type="url"
              value={cta.url || ''}
              onChange={(e) => patchCta({ url: e.target.value })}
              placeholder="https://cal.com/you/20min"
            />
          </Field>

          <Field label="Note">
            <input
              className="input"
              value={cta.note || ''}
              onChange={(e) => patchCta({ note: e.target.value })}
              placeholder="I'll walk you through your specific setup."
            />
          </Field>
        </div>
      </Card>
    </div>
  )
}

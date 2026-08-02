import { Card, Field, TagInput } from '../ui'
import RepeatableList from '../RepeatableList'

/**
 * Everything the AI needs to know about the product itself.
 * This is the single biggest driver of demo quality — it is injected into every
 * system prompt and also indexed for retrieval.
 */
export default function ProfileTab({ product, patch }) {
  const pricing = product.pricing || {}

  const patchPricing = (partial) => patch({ pricing: { ...pricing, ...partial } })

  return (
    <div className="stack stack-4">
      <Card title="Basics" description="Injected into every conversation the AI has.">
        <div className="stack stack-4">
          <div className="grid grid-2">
            <Field label="Product name" required>
              <input
                className="input"
                value={product.name || ''}
                onChange={(e) => patch({ name: e.target.value })}
                maxLength={120}
              />
            </Field>
            <Field label="Category">
              <input
                className="input"
                value={product.category || ''}
                onChange={(e) => patch({ category: e.target.value })}
                placeholder="Customer Support Automation"
              />
            </Field>
          </div>

          <Field label="Tagline">
            <input
              className="input"
              value={product.tagline || ''}
              onChange={(e) => patch({ tagline: e.target.value })}
              placeholder="Resolve support tickets before your team wakes up"
            />
          </Field>

          <Field label="Description" hint="What it is, in two or three sentences.">
            <textarea
              className="textarea"
              rows={4}
              value={product.description || ''}
              onChange={(e) => patch({ description: e.target.value })}
            />
          </Field>

          <div className="grid grid-2">
            <Field label="Target customers">
              <input
                className="input"
                value={product.target_customers || ''}
                onChange={(e) => patch({ target_customers: e.target.value })}
                placeholder="B2B SaaS companies with 20-500 employees"
              />
            </Field>
            <Field
              label="Welcome message"
              hint="Optional. The AI's opening line — leave blank to have it write one."
            >
              <input
                className="input"
                value={product.welcome_message || ''}
                onChange={(e) => patch({ welcome_message: e.target.value })}
                placeholder="Hi! What brought you here today?"
              />
            </Field>
          </div>

          <Field
            label="Main problem solved"
            hint="Used to score how well each prospect's stated pain matches your product."
          >
            <textarea
              className="textarea"
              rows={3}
              value={product.main_problem || ''}
              onChange={(e) => patch({ main_problem: e.target.value })}
            />
          </Field>

          <Field label="Key benefits" hint="Short outcome statements.">
            <TagInput
              value={product.main_benefits || []}
              onChange={(main_benefits) => patch({ main_benefits })}
              placeholder="Cut first-response time by 80% — press Enter"
            />
          </Field>
        </div>
      </Card>

      <Card
        title="Features"
        description="Each one becomes retrievable knowledge and can seed a demo section."
      >
        <RepeatableList
          items={product.features || []}
          onChange={(features) => patch({ features })}
          newItem={{ name: '', description: '', keywords: [] }}
          addLabel="Add feature"
          itemLabel="Feature"
          emptyText="No features yet. Add the two or three that actually win deals."
          renderItem={(item, set) => (
            <div className="stack stack-3">
              <Field label="Name">
                <input
                  className="input"
                  value={item.name || ''}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder="Auto-resolution"
                />
              </Field>
              <Field label="Description">
                <textarea
                  className="textarea"
                  rows={2}
                  value={item.description || ''}
                  onChange={(e) => set({ description: e.target.value })}
                  placeholder="Answers repetitive tickets directly from your documentation."
                />
              </Field>
              <Field label="Keywords" hint="Words a prospect might use when asking about this.">
                <TagInput
                  value={item.keywords || []}
                  onChange={(keywords) => set({ keywords })}
                  placeholder="automation, deflection…"
                />
              </Field>
            </div>
          )}
        />
      </Card>

      <Card title="Pricing" description="The AI answers pricing questions from exactly this.">
        <div className="stack stack-4">
          <div className="grid grid-3">
            <Field label="Pricing model">
              <input
                className="input"
                value={pricing.model || ''}
                onChange={(e) => patchPricing({ model: e.target.value })}
                placeholder="per seat"
              />
            </Field>
            <Field label="Currency">
              <input
                className="input"
                value={pricing.currency || 'USD'}
                onChange={(e) => patchPricing({ currency: e.target.value })}
                maxLength={8}
              />
            </Field>
            <Field label="Free trial">
              <input
                className="input"
                value={pricing.free_trial || ''}
                onChange={(e) => patchPricing({ free_trial: e.target.value })}
                placeholder="14 days, no card"
              />
            </Field>
          </div>

          <RepeatableList
            items={pricing.plans || []}
            onChange={(plans) => patchPricing({ plans })}
            newItem={{ name: '', price: '', period: 'month', includes: [], best_for: '' }}
            addLabel="Add plan"
            itemLabel="Plan"
            emptyText="No plans yet. Without these the AI will say it cannot confirm pricing."
            renderItem={(item, set) => (
              <div className="stack stack-3">
                <div className="grid grid-3">
                  <Field label="Name">
                    <input
                      className="input"
                      value={item.name || ''}
                      onChange={(e) => set({ name: e.target.value })}
                      placeholder="Growth"
                    />
                  </Field>
                  <Field label="Price">
                    <input
                      className="input"
                      value={item.price || ''}
                      onChange={(e) => set({ price: e.target.value })}
                      placeholder="199"
                    />
                  </Field>
                  <Field label="Per">
                    <input
                      className="input"
                      value={item.period || ''}
                      onChange={(e) => set({ period: e.target.value })}
                      placeholder="month"
                    />
                  </Field>
                </div>
                <Field label="Best for">
                  <input
                    className="input"
                    value={item.best_for || ''}
                    onChange={(e) => set({ best_for: e.target.value })}
                    placeholder="Scaling support teams"
                  />
                </Field>
                <Field label="Includes">
                  <TagInput
                    value={item.includes || []}
                    onChange={(includes) => set({ includes })}
                    placeholder="10 seats — press Enter"
                  />
                </Field>
              </div>
            )}
          />

          <Field label="Pricing notes">
            <textarea
              className="textarea"
              rows={2}
              value={pricing.notes || ''}
              onChange={(e) => patchPricing({ notes: e.target.value })}
              placeholder="Annual billing saves 20%. Volume discounts above 50 seats."
            />
          </Field>
        </div>
      </Card>

      <Card title="Integrations">
        <RepeatableList
          items={product.integrations || []}
          onChange={(integrations) => patch({ integrations })}
          newItem={{ name: '', description: '' }}
          addLabel="Add integration"
          itemLabel="Integration"
          emptyText='Add these so "does it work with X?" gets a real answer.'
          renderItem={(item, set) => (
            <div className="grid grid-2">
              <Field label="Name">
                <input
                  className="input"
                  value={item.name || ''}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder="Zendesk"
                />
              </Field>
              <Field label="What it does">
                <input
                  className="input"
                  value={item.description || ''}
                  onChange={(e) => set({ description: e.target.value })}
                  placeholder="Two-way ticket sync"
                />
              </Field>
            </div>
          )}
        />
      </Card>

      <Card title="Security & compliance">
        <Field hint="Certifications, data residency, encryption. Technical buyers always ask.">
          <textarea
            className="textarea"
            rows={3}
            value={product.security_info || ''}
            onChange={(e) => patch({ security_info: e.target.value })}
            placeholder="SOC 2 Type II certified. Data encrypted at rest and in transit. EU and US data residency."
          />
        </Field>
      </Card>

      <Card title="FAQs" description="Indexed individually, so a matching question retrieves its answer.">
        <RepeatableList
          items={product.faqs || []}
          onChange={(faqs) => patch({ faqs })}
          newItem={{ question: '', answer: '' }}
          addLabel="Add FAQ"
          itemLabel="FAQ"
          emptyText="Add the questions you answer on every single call."
          renderItem={(item, set) => (
            <div className="stack stack-3">
              <Field label="Question">
                <input
                  className="input"
                  value={item.question || ''}
                  onChange={(e) => set({ question: e.target.value })}
                  placeholder="Does it replace my helpdesk?"
                />
              </Field>
              <Field label="Answer">
                <textarea
                  className="textarea"
                  rows={2}
                  value={item.answer || ''}
                  onChange={(e) => set({ answer: e.target.value })}
                />
              </Field>
            </div>
          )}
        />
      </Card>

      <Card
        title="Objection handling"
        description="Your playbook. The AI uses your wording rather than improvising."
      >
        <RepeatableList
          items={product.objections || []}
          onChange={(objections) => patch({ objections })}
          newItem={{ objection: '', response: '' }}
          addLabel="Add objection"
          itemLabel="Objection"
          emptyText="Too expensive · we already use X · switching is hard · is it secure?"
          renderItem={(item, set) => (
            <div className="stack stack-3">
              <Field label="What they say">
                <input
                  className="input"
                  value={item.objection || ''}
                  onChange={(e) => set({ objection: e.target.value })}
                  placeholder="It's too expensive"
                />
              </Field>
              <Field label="How to respond" hint="Be honest — the AI will not oversell for you.">
                <textarea
                  className="textarea"
                  rows={2}
                  value={item.response || ''}
                  onChange={(e) => set({ response: e.target.value })}
                />
              </Field>
            </div>
          )}
        />
      </Card>

      <Card title="Case studies">
        <RepeatableList
          items={product.case_studies || []}
          onChange={(case_studies) => patch({ case_studies })}
          newItem={{ title: '', customer: '', outcome: '', details: '' }}
          addLabel="Add case study"
          itemLabel="Case study"
          emptyText="Real outcomes are the most persuasive thing the AI can cite."
          renderItem={(item, set) => (
            <div className="stack stack-3">
              <div className="grid grid-2">
                <Field label="Title">
                  <input
                    className="input"
                    value={item.title || ''}
                    onChange={(e) => set({ title: e.target.value })}
                  />
                </Field>
                <Field label="Customer">
                  <input
                    className="input"
                    value={item.customer || ''}
                    onChange={(e) => set({ customer: e.target.value })}
                  />
                </Field>
              </div>
              <Field label="Outcome">
                <input
                  className="input"
                  value={item.outcome || ''}
                  onChange={(e) => set({ outcome: e.target.value })}
                  placeholder="Cut response time from 9 hours to 40 minutes"
                />
              </Field>
              <Field label="Details">
                <textarea
                  className="textarea"
                  rows={2}
                  value={item.details || ''}
                  onChange={(e) => set({ details: e.target.value })}
                />
              </Field>
            </div>
          )}
        />
      </Card>
    </div>
  )
}

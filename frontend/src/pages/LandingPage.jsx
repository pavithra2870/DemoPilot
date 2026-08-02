import { Link } from 'react-router-dom'

const FEATURES = [
  {
    title: 'It drives the demo, not just the chat',
    body: 'The AI returns structured actions — navigate, highlight, open pricing — and the demo interface executes them. Prospects are shown the product, not told about it.',
  },
  {
    title: 'Grounded in your knowledge, not the model’s',
    body: 'Your docs, FAQs, pricing and objection playbook are chunked, embedded and retrieved per question. When the answer isn’t there, it says so instead of inventing one.',
  },
  {
    title: 'Personalised, not scripted',
    body: 'A stage machine decides each turn’s job — discover, demonstrate, handle, qualify — so the walkthrough adapts to the prospect instead of marching through slides.',
  },
  {
    title: 'Qualification that feels like a conversation',
    body: 'One question at a time, never repeating what it already knows. Budget, timeline, authority and pain are collected the way a good sales engineer would.',
  },
  {
    title: 'Lead scores you can actually audit',
    body: 'Every score is computed deterministically from five components, each with the sentence explaining it. No black-box number you have to trust.',
  },
  {
    title: 'A brief waiting in the morning',
    body: 'Full transcript, qualification answers, score breakdown, what they engaged with, and a specific recommended next step.',
  },
]

export default function LandingPage() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="row" style={{ gap: '0.45rem' }}>
          <span style={{ color: 'var(--accent)', fontSize: '1.15rem' }}>◆</span>
          <strong>DemoPilot</strong>
        </div>
        <div className="row" style={{ gap: '0.5rem' }}>
          <Link to="/login" className="btn btn-sm">
            Sign in
          </Link>
          <Link to="/register" className="btn btn-sm btn-primary">
            Get started
          </Link>
        </div>
      </nav>

      <header className="landing-hero">
        <span className="badge badge-accent" style={{ marginBottom: '1rem' }}>
          AI Sales Engineer
        </span>
        <h1>Your product demo, running at 2am without you</h1>
        <p>
          You have a full-time job, a different timezone, or simply no capacity for another
          discovery call. DemoPilot gives every prospect an interactive walkthrough that
          understands their problem, shows the parts that matter, answers from your real
          documentation, handles objections, and hands you a qualified lead in the morning.
        </p>
        <div className="row" style={{ justifyContent: 'center', gap: '0.6rem' }}>
          <Link to="/register" className="btn btn-primary btn-lg">
            Build your demo
          </Link>
          <Link to="/login" className="btn btn-lg">
            Sign in
          </Link>
        </div>
      </header>

      <section className="landing-grid">
        {FEATURES.map((feature) => (
          <article key={feature.title} className="landing-feature">
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </article>
        ))}
      </section>

      <footer className="center small dim" style={{ padding: '0 1.5rem 2.5rem' }}>
        Runs on free tiers — Groq for inference, local embeddings, FAISS, Supabase.
      </footer>
    </div>
  )
}

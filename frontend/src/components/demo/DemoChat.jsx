import { useEffect, useRef, useState } from 'react'

import { useDemoStore } from '../../store/demoStore'

export default function DemoChat() {
  const messages = useDemoStore((s) => s.messages)
  const sending = useDemoStore((s) => s.sending)
  const statusText = useDemoStore((s) => s.statusText)
  const suggested = useDemoStore((s) => s.suggestedReplies)
  const turnError = useDemoStore((s) => s.turnError)
  const degraded = useDemoStore((s) => s.degraded)
  const ended = useDemoStore((s) => s.ended)
  const send = useDemoStore((s) => s.send)

  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages, sending, statusText])

  const submit = (text) => {
    const message = (text ?? draft).trim()
    if (!message || sending || ended) return
    setDraft('')
    send(message)
    inputRef.current?.focus()
  }

  return (
    <section className="demo-chat" aria-label="AI Sales Engineer">
      <header className="demo-chat-head">
        <span className="demo-avatar">AI</span>
        <div className="grow" style={{ minWidth: 0 }}>
          <div className="small bold">AI Sales Engineer</div>
          <div className="row" style={{ gap: '0.35rem' }}>
            {!ended && <span className="live-dot" />}
            <span className="tiny" style={{ color: 'var(--demo-text-2)' }}>
              {ended ? 'Session ended' : 'Answers from this product’s documentation'}
            </span>
          </div>
        </div>
      </header>

      <div className="demo-messages" ref={scrollRef}>
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}

        {sending && (
          <div className="typing">
            <span className="typing-dots">
              <i />
              <i />
              <i />
            </span>
            <span>{statusText || 'Thinking…'}</span>
          </div>
        )}
      </div>

      {degraded && (
        <div className="demo-notice">
          The AI model is unreachable right now, so replies are limited. Your answers are still
          being recorded.
        </div>
      )}

      {turnError && <div className="demo-error">{turnError}</div>}

      {suggested.length > 0 && !sending && !ended && (
        <div className="suggested">
          {suggested.map((reply) => (
            <button key={reply} type="button" onClick={() => submit(reply)}>
              {reply}
            </button>
          ))}
        </div>
      )}

      <form
        className="demo-composer"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <textarea
          ref={inputRef}
          className="demo-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder={ended ? 'This session has ended.' : 'Ask anything, or say what you’re trying to solve…'}
          rows={1}
          maxLength={4000}
          disabled={ended}
          aria-label="Message the AI Sales Engineer"
        />
        <button
          type="submit"
          className="demo-send"
          disabled={!draft.trim() || sending || ended}
          aria-label="Send"
        >
          ↑
        </button>
      </form>
    </section>
  )
}

function Message({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`msg ${isUser ? 'msg-user' : 'msg-assistant'}`}>
      <div className="msg-bubble">{message.content}</div>

      {!isUser && message.sources?.length > 0 && (
        <div className="msg-sources">
          {message.sources.map((source) => (
            <span
              key={source.id}
              className={`source-chip${source.kind === 'profile' ? ' profile' : ''}`}
              title={`${source.label}\n\n${source.snippet}`}
            >
              {source.label}
            </span>
          ))}
        </div>
      )}

      {!isUser && message.confidence === 'low' && (
        <span className="msg-flag">Low confidence — this may need confirming with the team.</span>
      )}
    </div>
  )
}

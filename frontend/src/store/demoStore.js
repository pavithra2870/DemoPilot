/**
 * Public demo runtime.
 *
 * Holds the conversation, the stage the prospect is looking at, and the live
 * qualification/score readout. Critically, it is also where AI actions are
 * *executed* — see `executeAction`, which validates every command against a
 * whitelist and against the founder's real sections before touching the UI.
 */

import { create } from 'zustand'
import { endpoints, websocketUrl } from '../services/apiClient'

// The only actions the UI will ever perform. Anything else is ignored.
export const ALLOWED_ACTIONS = new Set([
  'navigate',
  'highlight',
  'open_pricing',
  'show_faq',
  'show_integration',
  'request_contact',
  'end_demo',
  'none',
])

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

export const useDemoStore = create((set, get) => ({
  // -- config / lifecycle --------------------------------------------------
  slug: null,
  config: null,
  sessionId: null,
  loading: true,
  loadError: null,
  ended: false,

  // -- conversation --------------------------------------------------------
  messages: [],
  sending: false,
  statusText: '',
  suggestedReplies: [],
  turnError: null,
  degraded: false,

  // -- demo stage ----------------------------------------------------------
  activeSection: null,
  highlight: null,
  panel: null, // 'pricing' | 'faq' | 'integrations' | null
  visited: [],

  // -- qualification -------------------------------------------------------
  qualification: {},
  leadScore: null,
  contactOpen: false,
  contactSubmitted: false,

  // -- transport -----------------------------------------------------------
  socket: null,
  socketReady: false,

  reset() {
    get().closeSocket()
    set({
      slug: null, config: null, sessionId: null, loading: true, loadError: null,
      ended: false, messages: [], sending: false, statusText: '', suggestedReplies: [],
      turnError: null, degraded: false, activeSection: null, highlight: null, panel: null,
      visited: [], qualification: {}, leadScore: null, contactOpen: false,
      contactSubmitted: false, socket: null, socketReady: false,
    })
  },

  async load(slug) {
    set({ loading: true, loadError: null, slug })
    try {
      const config = await endpoints.getDemo(slug)
      set({ config, loading: false })
      return config
    } catch (err) {
      set({ loadError: err.message, loading: false })
      return null
    }
  },

  async start(prefill = {}) {
    const { slug } = get()
    if (!slug) return
    set({ sending: true, statusText: 'Starting your demo…', turnError: null })
    try {
      const data = await endpoints.startSession(slug, {
        referrer: document.referrer || '',
        ...prefill,
      })
      set({
        sessionId: data.session_id,
        config: data.config,
        sending: false,
        statusText: '',
      })
      get().applyTurn(data.opening)
      get().connectSocket(data.session_id)
    } catch (err) {
      set({ sending: false, statusText: '', turnError: err.message })
    }
  },

  // -- action execution ----------------------------------------------------

  /**
   * Execute one validated action from the AI.
   *
   * Model output is data, never code. Unknown action types are dropped, and a
   * `navigate`/`highlight` target must resolve to a section the founder actually
   * created — so a hallucinated id can never move the prospect somewhere broken.
   */
  executeAction(action) {
    if (!action || !ALLOWED_ACTIONS.has(action.type) || action.type === 'none') return

    const { config } = get()
    const sections = config?.sections || []
    const sectionExists = (key) => sections.some((s) => s.section_key === key)

    switch (action.type) {
      case 'navigate': {
        if (!action.target || !sectionExists(action.target)) return
        get().goToSection(action.target, 'ai')
        set({ highlight: null })
        break
      }
      case 'highlight': {
        if (action.target && sectionExists(action.target)) {
          get().goToSection(action.target, 'ai')
        }
        set({ highlight: { label: action.label || action.target, at: Date.now() } })
        break
      }
      case 'open_pricing':
        set({ panel: 'pricing' })
        if (sectionExists('pricing')) get().goToSection('pricing', 'ai')
        break
      case 'show_faq':
        set({ panel: 'faq' })
        break
      case 'show_integration':
        set({ panel: 'integrations' })
        break
      case 'request_contact':
        if (!get().contactSubmitted) set({ contactOpen: true })
        break
      case 'end_demo':
        get().finish()
        break
      default:
        break
    }
  },

  goToSection(sectionKey, source = 'user') {
    const { activeSection, visited, sessionId } = get()
    if (!sectionKey || sectionKey === activeSection) return

    const nextVisited = visited.includes(sectionKey) ? visited : [...visited, sectionKey]
    set({ activeSection: sectionKey, visited: nextVisited, panel: null })

    if (sessionId && source === 'user') {
      endpoints
        .trackEvent(sessionId, 'section_view', { section: sectionKey, source })
        .catch(() => {})
    }
  },

  setPanel(panel) {
    set({ panel: get().panel === panel ? null : panel })
    const { sessionId } = get()
    if (sessionId && panel) {
      const eventMap = {
        pricing: 'pricing_opened',
        faq: 'faq_opened',
        integrations: 'integration_opened',
      }
      const event = eventMap[panel]
      if (event) endpoints.trackEvent(sessionId, event, {}).catch(() => {})
    }
  },

  clearHighlight() {
    set({ highlight: null })
  },

  // -- turns ---------------------------------------------------------------

  applyTurn(turn) {
    if (!turn) return
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: turn.message_id || uid(),
          role: 'assistant',
          content: turn.message,
          sources: turn.sources || [],
          confidence: turn.confidence,
          intent: turn.intent,
          action: turn.action,
        },
      ],
      qualification: turn.qualification || state.qualification,
      leadScore: turn.lead_score || state.leadScore,
      suggestedReplies: turn.suggested_replies || [],
      degraded: Boolean(turn.degraded),
      sending: false,
      statusText: '',
    }))
    get().executeAction(turn.action)
  },

  async send(text) {
    const message = (text || '').trim()
    const { sessionId, sending, ended } = get()
    if (!message || !sessionId || sending || ended) return

    set((state) => ({
      messages: [...state.messages, { id: uid(), role: 'user', content: message }],
      sending: true,
      statusText: 'Thinking…',
      suggestedReplies: [],
      turnError: null,
    }))

    const { socket, socketReady, activeSection } = get()
    if (socket && socketReady) {
      socket.send(JSON.stringify({ type: 'message', message, active_section: activeSection }))
      return
    }

    // REST fallback — identical behaviour, just without live status updates.
    try {
      const turn = await endpoints.sendMessage(sessionId, {
        message,
        active_section: activeSection,
      })
      get().applyTurn(turn)
    } catch (err) {
      set({ sending: false, statusText: '', turnError: err.message })
    }
  },

  // -- websocket -----------------------------------------------------------

  connectSocket(sessionId) {
    if (get().socket) return
    let socket
    try {
      socket = new WebSocket(websocketUrl(`/ws/demo/${sessionId}`))
    } catch {
      return // REST fallback covers us
    }

    socket.onopen = () => set({ socketReady: true })

    socket.onmessage = (event) => {
      let payload
      try {
        payload = JSON.parse(event.data)
      } catch {
        return
      }
      switch (payload.type) {
        case 'status':
          if (get().sending) set({ statusText: payload.detail || 'Working…' })
          break
        case 'turn':
          get().applyTurn(payload.data)
          break
        case 'ended':
          set({ ended: true, sending: false, statusText: '' })
          if (payload.data?.lead_score) set({ leadScore: payload.data.lead_score })
          break
        case 'error':
          set({ sending: false, statusText: '', turnError: payload.message })
          break
        default:
          break
      }
    }

    socket.onclose = () => set({ socketReady: false, socket: null })
    socket.onerror = () => set({ socketReady: false })

    set({ socket })
  },

  closeSocket() {
    const { socket } = get()
    if (socket) {
      socket.onclose = null
      try {
        socket.close()
      } catch {
        /* already closing */
      }
    }
    set({ socket: null, socketReady: false })
  },

  // -- conversion ----------------------------------------------------------

  openContact() {
    set({ contactOpen: true })
  },
  closeContact() {
    set({ contactOpen: false })
  },

  async submitContact(payload) {
    const { sessionId } = get()
    if (!sessionId) return { ok: false, error: 'No active session.' }
    try {
      const result = await endpoints.submitContact(sessionId, payload)
      set({
        contactSubmitted: true,
        contactOpen: false,
        leadScore: result.lead_score || get().leadScore,
        qualification: {
          ...get().qualification,
          name: payload.name || get().qualification.name,
          email: payload.email || get().qualification.email,
          company: payload.company || get().qualification.company,
        },
      })
      return { ok: true }
    } catch (err) {
      return { ok: false, error: err.message }
    }
  },

  async finish() {
    const { sessionId, ended } = get()
    if (!sessionId || ended) return
    set({ ended: true, sending: false, statusText: '' })
    try {
      const result = await endpoints.endSession(sessionId)
      if (result?.lead_score) set({ leadScore: result.lead_score })
    } catch {
      /* the session is closed client-side regardless */
    }
    get().closeSocket()
  },
}))

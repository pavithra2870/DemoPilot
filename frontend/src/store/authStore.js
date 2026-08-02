import { create } from 'zustand'
import { endpoints, setAuthToken, setUnauthorizedHandler } from '../services/apiClient'

const TOKEN_KEY = 'demopilot.token'

const readToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

const writeToken = (token) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* private browsing — the session simply won't persist */
  }
}

const initialToken = readToken()
setAuthToken(initialToken)

export const useAuthStore = create((set, get) => ({
  token: initialToken,
  founder: null,
  // `checking` starts true when a token exists: we must validate it before
  // deciding whether to render the app or bounce to /login, otherwise a refresh
  // flashes the login screen.
  checking: Boolean(initialToken),
  error: null,
  submitting: false,

  isAuthenticated: () => Boolean(get().token && get().founder),

  async bootstrap() {
    const token = get().token
    if (!token) {
      set({ checking: false })
      return
    }
    try {
      const founder = await endpoints.me()
      set({ founder, checking: false })
    } catch {
      writeToken(null)
      setAuthToken(null)
      set({ token: null, founder: null, checking: false })
    }
  },

  async login(email, password) {
    set({ submitting: true, error: null })
    try {
      const data = await endpoints.login({ email, password })
      writeToken(data.access_token)
      setAuthToken(data.access_token)
      set({ token: data.access_token, founder: data.founder, submitting: false })
      return true
    } catch (err) {
      set({ error: err.message, submitting: false })
      return false
    }
  },

  async register(email, password, fullName) {
    set({ submitting: true, error: null })
    try {
      const data = await endpoints.register({ email, password, full_name: fullName })
      writeToken(data.access_token)
      setAuthToken(data.access_token)
      set({ token: data.access_token, founder: data.founder, submitting: false })
      return true
    } catch (err) {
      set({ error: err.message, submitting: false })
      return false
    }
  },

  logout() {
    writeToken(null)
    setAuthToken(null)
    set({ token: null, founder: null, error: null })
  },

  clearError() {
    set({ error: null })
  },
}))

// Any 401 from anywhere clears the session exactly once.
setUnauthorizedHandler(() => {
  const { token, logout } = useAuthStore.getState()
  if (token) logout()
})

/**
 * Single HTTP entry point for the whole app.
 *
 * Everything goes through `request()` so auth headers, JSON handling and the
 * backend's `{error: {code, message}}` envelope are handled in exactly one
 * place. Components then only ever deal with `ApiError`.
 */

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown', details = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  get isAuthError() {
    return this.status === 401
  }
}

let authToken = null
let onUnauthorized = null

export function setAuthToken(token) {
  authToken = token || null
}

/** Registered by the auth store so an expired token logs the founder out once,
 *  centrally, instead of every screen handling 401 itself. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export function apiUrl(path) {
  return `${BASE_URL}${path}`
}

export function websocketUrl(path) {
  if (BASE_URL) {
    return `${BASE_URL.replace(/^http/, 'ws')}${path}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

async function request(path, { method = 'GET', body, headers = {}, isForm = false, signal } = {}) {
  const finalHeaders = { ...headers }
  if (!isForm && body !== undefined) finalHeaders['Content-Type'] = 'application/json'
  if (authToken) finalHeaders.Authorization = `Bearer ${authToken}`

  let response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: finalHeaders,
      body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError(
      'Could not reach the DemoPilot API. Is the backend running on port 8000?',
      { code: 'network_error' },
    )
  }

  if (response.status === 204) return null

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { error: { code: 'bad_response', message: text.slice(0, 300) } }
    }
  }

  if (!response.ok) {
    const error = payload?.error || {}
    if (response.status === 401 && onUnauthorized) onUnauthorized()
    throw new ApiError(error.message || `Request failed (${response.status})`, {
      status: response.status,
      code: error.code || 'http_error',
      details: error.details || null,
    })
  }

  return payload
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  del: (path, options) => request(path, { ...options, method: 'DELETE' }),
  upload: (path, file) => {
    const form = new FormData()
    form.append('file', file)
    return request(path, { method: 'POST', body: form, isForm: true })
  },
}

// --- Endpoint map ----------------------------------------------------------
// Kept together so a backend route change is a one-line edit here rather than a
// hunt through components.

export const endpoints = {
  health: () => api.get('/api/health'),

  register: (payload) => api.post('/api/auth/register', payload),
  login: (payload) => api.post('/api/auth/login', payload),
  me: () => api.get('/api/auth/me'),

  listProducts: () => api.get('/api/products'),
  createProduct: (payload) => api.post('/api/products', payload),
  getProduct: (id) => api.get(`/api/products/${id}`),
  updateProduct: (id, payload) => api.put(`/api/products/${id}`, payload),
  deleteProduct: (id) => api.del(`/api/products/${id}`),
  publishProduct: (id, published) => api.post(`/api/products/${id}/publish?published=${published}`),
  publishCheck: (id) => api.get(`/api/products/${id}/publish-check`),
  knowledgeStatus: (id) => api.get(`/api/products/${id}/knowledge-status`),

  listSections: (id) => api.get(`/api/products/${id}/sections`),
  createSection: (id, payload) => api.post(`/api/products/${id}/sections`, payload),
  updateSection: (id, sectionId, payload) =>
    api.put(`/api/products/${id}/sections/${sectionId}`, payload),
  deleteSection: (id, sectionId) => api.del(`/api/products/${id}/sections/${sectionId}`),
  reorderSections: (id, orderedIds) =>
    api.post(`/api/products/${id}/sections/reorder`, { ordered_ids: orderedIds }),
  seedSections: (id) => api.post(`/api/products/${id}/sections/seed`),

  listDocuments: (id) => api.get(`/api/products/${id}/documents`),
  uploadDocument: (id, file) => api.upload(`/api/products/${id}/documents`, file),
  deleteDocument: (id, documentId) => api.del(`/api/products/${id}/documents/${documentId}`),
  reindex: (id) => api.post(`/api/products/${id}/documents/reindex`),

  getDemo: (slug) => api.get(`/api/demo/${slug}`),
  startSession: (slug, payload) => api.post(`/api/demo/${slug}/sessions`, payload),
  sendMessage: (sessionId, payload) =>
    api.post(`/api/demo/sessions/${sessionId}/messages`, payload),
  trackEvent: (sessionId, eventType, payload = {}) =>
    api.post(`/api/demo/sessions/${sessionId}/events`, { event_type: eventType, payload }),
  submitContact: (sessionId, payload) =>
    api.post(`/api/demo/sessions/${sessionId}/contact`, payload),
  endSession: (sessionId) => api.post(`/api/demo/sessions/${sessionId}/end`),

  overview: (productId) =>
    api.get(`/api/dashboard/overview${productId ? `?product_id=${productId}` : ''}`),
  listLeads: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
    ).toString()
    return api.get(`/api/leads${query ? `?${query}` : ''}`)
  },
  getLead: (sessionId) => api.get(`/api/leads/${sessionId}`),
  regenerateReport: (sessionId) => api.post(`/api/leads/${sessionId}/report`),

  analytics: (productId) =>
    api.get(`/api/analytics${productId ? `?product_id=${productId}` : ''}`),
}

const API = import.meta.env.VITE_API_URL || ''
const DEBUG_API = import.meta.env.DEV || import.meta.env.VITE_DEBUG_API === 'true'

function traceApi(method, path, status, ms, detail = '') {
  if (!DEBUG_API) return
  const mark = status >= 400 ? 'ERR' : 'OK'
  console.debug(`[api ${mark}] ${method} ${path} ${status} ${ms.toFixed(0)}ms`, detail || '')
}

let onError = null
let onUnauthorized = null
let refreshInFlight = null

export function setApiHandlers({ onError: err, onUnauthorized: unauth }) {
  onError = err
  onUnauthorized = unauth
}

function parseError(text, status) {
  try {
    const j = JSON.parse(text)
    if (j.detail) {
      if (typeof j.detail === 'string') return j.detail
      if (Array.isArray(j.detail)) return j.detail.map((d) => d.msg || String(d)).join('; ')
    }
  } catch {
    /* ignore */
  }
  return text || `HTTP ${status}`
}

export function getToken() {
  return localStorage.getItem('token') || ''
}

export function setToken(token) {
  localStorage.setItem('token', token)
}

export function getRefreshToken() {
  return localStorage.getItem('refresh_token') || ''
}

export function setRefreshToken(token) {
  if (token) localStorage.setItem('refresh_token', token)
  else localStorage.removeItem('refresh_token')
}

export function clearToken() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
}

export function setSession({ accessToken, refreshToken }) {
  if (accessToken) setToken(accessToken)
  if (refreshToken) setRefreshToken(refreshToken)
}

async function tryRefreshSession() {
  const refresh = getRefreshToken()
  if (!refresh) return false
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = (async () => {
    try {
      const r = await fetch(`${API}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      })
      if (!r.ok) return false
      const data = await r.json()
      setToken(data.access_token)
      if (data.refresh_token) setRefreshToken(data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function api(path, opts = {}, _retried = false) {
  const token = getToken()
  const headers = { ...(opts.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const method = opts.method || 'GET'
  const t0 = performance.now()
  let status = 0
  try {
    const r = await fetch(`${API}${path}`, { ...opts, headers })
    status = r.status
    if (r.status === 401 && !_retried) {
      const refreshed = await tryRefreshSession()
      if (refreshed) return api(path, opts, true)
      onUnauthorized?.()
      throw new Error('Session expired — please sign in again.')
    }
    if (r.status === 401) {
      onUnauthorized?.()
      throw new Error('Session expired — please sign in again.')
    }
    if (!r.ok) {
      const text = await r.text()
      const msg = parseError(text, r.status)
      onError?.(msg)
      throw new Error(msg)
    }
    if (r.status === 204) return null
    const ct = r.headers.get('content-type') || ''
    if (ct.includes('application/json')) return r.json()
    return r.blob()
  } finally {
    traceApi(method, path, status || 0, performance.now() - t0)
  }
}

export async function apiStream(path, body, onEvent) {
  const token = getToken()
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  if (r.status === 401) {
    const refreshed = await tryRefreshSession()
    if (refreshed) return apiStream(path, body, onEvent)
    onUnauthorized?.()
    throw new Error('Session expired')
  }
  if (!r.ok) {
    const text = await r.text()
    const msg = parseError(text, r.status)
    onError?.(msg)
    throw new Error(msg)
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)))
          } catch {
            /* ignore */
          }
        }
      }
    }
  }
}

export function isAdminRole(role) {
  return role === 'org_admin' || role === 'owner'
}

export async function pollChatJob(jobId, { intervalMs = 1500, maxAttempts = 120, onProgress } = {}) {
  for (let i = 0; i < maxAttempts; i += 1) {
    const body = await api(`/api/v1/chat/jobs/${jobId}`)
    onProgress?.(body)
    if (body.status === 'completed') return body
    if (body.status === 'failed') throw new Error(body.error || 'Chat job failed')
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error('Chat job timed out')
}

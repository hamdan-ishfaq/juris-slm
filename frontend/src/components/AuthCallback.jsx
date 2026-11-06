import { useEffect } from 'react'
import { setToken } from '../lib/api'

export default function AuthCallback({ onComplete }) {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const code = params.get('code')
    const finish = (t) => {
      if (t) setToken(t)
      window.history.replaceState({}, '', '/')
      onComplete?.(t)
    }
    if (token) {
      finish(token)
      return
    }
    if (code) {
      fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/auth/oidc/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
        .then((r) => r.json())
        .then((data) => finish(data.access_token))
        .catch(() => finish(null))
      return
    }
    finish(null)
  }, [onComplete])

  return (
    <div className="login-shell">
      <div className="login-card">
        <span className="spinner" /> Completing sign-in…
      </div>
    </div>
  )
}

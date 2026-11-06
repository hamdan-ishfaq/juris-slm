import { IconShield } from './Icons'

export default function LoginPage({ email, setEmail, password, setPassword, onLogin, error, loading, ssoStatus, branding }) {
  const apiBase = import.meta.env.VITE_API_URL || ''
  const brandName = branding?.brand_name || 'JurisGuard'
  const brandTagline = branding?.brand_tagline || 'V2 · On-Premise'
  const startSso = (path) => {
    window.location.href = `${apiBase}${path}`
  }
  return (
    <div className="login-shell">
      <aside className="login-brand animate-fade">
        <div className="brand-mark">
          <IconShield className="brand-icon" />
          <div>
            <span className="brand-name">{brandName}</span>
            <span className="brand-edition">{brandTagline}</span>
          </div>
        </div>
        <h1>Legal intelligence that stays inside your perimeter.</h1>
        <p className="lead">
          Grounded Q&A on GDPR, BGB, and matter documents — with citations, audit trail, and zero mandatory cloud dependency.
        </p>
        <ul className="value-list">
          <li><strong>Hybrid retrieval</strong> — vector + full-text + rerank, always local</li>
          <li><strong>Citation panel</strong> — every answer linked to source chunks</li>
          <li><strong>Matter workspace</strong> — upload, analyze, compare, graph extract</li>
          <li><strong>Air-gap ready</strong> — flip one env var, no outbound LLM calls</li>
        </ul>
        <div className="trust-strip">
          <span className="trust-pill">EU GDPR / BGB</span>
          <span className="trust-pill">RBAC + Audit</span>
          <span className="trust-pill">Eval-gated</span>
        </div>
      </aside>
      <main className="login-form-wrap animate-slide-up">
        <div className="login-card">
          <h2>Sign in</h2>
          <p className="muted">Access your organization&apos;s legal workspace</p>
          {error && <div className="alert alert-error">{error}</div>}
          <label className="field">
            <span>Work email</span>
            <input
              type="email"
              aria-label="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@firm.example"
              autoComplete="username"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              aria-label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              onKeyDown={(e) => e.key === 'Enter' && onLogin()}
            />
          </label>
          <button type="button" className="btn btn-primary btn-block" disabled={loading} onClick={onLogin}>
            {loading ? <span className="spinner" /> : 'Sign in'}
          </button>
          {(ssoStatus?.oidc_enabled || ssoStatus?.saml_enabled) && (
            <div className="sso-actions">
              {ssoStatus?.oidc_enabled && (
                <button type="button" className="btn btn-secondary btn-block" onClick={() => startSso('/api/v1/auth/oidc/login')}>
                  Sign in with OIDC SSO
                </button>
              )}
              {ssoStatus?.saml_enabled && (
                <button type="button" className="btn btn-secondary btn-block" onClick={() => startSso('/api/v1/auth/saml/login')}>
                  Sign in with SAML SSO
                </button>
              )}
            </div>
          )}
          <p className="login-foot muted">
            Enterprise SSO when <code>OIDC_ENABLED</code> or <code>SAML_ENABLED</code> is set on the server.
          </p>
        </div>
      </main>
    </div>
  )
}

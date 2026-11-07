import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils.jsx'

const ROLES = ['member', 'matter_lead', 'org_admin']

export default function AdminView({ currentUser }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [memberEmail, setMemberEmail] = useState('')
  const [memberRole, setMemberRole] = useState('viewer')
  const [matterId, setMatterId] = useState('')
  const [matters, setMatters] = useState([])
  const [org, setOrg] = useState(null)
  const [sso, setSso] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const requests = [api('/api/v1/admin/users'), api('/api/v1/matters')]
      if (currentUser?.role === 'owner' || currentUser?.role === 'org_admin') {
        requests.push(api('/api/v1/admin/org'), api('/api/v1/admin/sso'))
      }
      const results = await Promise.all(requests)
      setUsers(results[0])
      setMatters(results[1])
      if (results[2]) setOrg(results[2])
      if (results[3]) setSso(results[3])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const updateRole = async (userId, role) => {
    await api(`/api/v1/admin/users/${userId}/role`, { method: 'PUT', body: JSON.stringify({ role }) })
    await load()
  }

  const inviteMember = async () => {
    if (!matterId || !memberEmail) return
    await api(`/api/v1/matters/${matterId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email: memberEmail, role: memberRole }),
    })
    setMemberEmail('')
  }

  if (loading) return <div className="card"><span className="spinner" /> Loading admin…</div>

  return (
    <div className="admin-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Administration</h2>
          <p className="muted">Org users, roles, and matter membership.</p>
          {org && <p className="muted">Organization: <strong>{org.name}</strong> ({org.slug})</p>}
        </div>
      </header>

      <div className="card">
        <h4>Organization users</h4>
        <table className="audit-table">
          <thead><tr><th>Email</th><th>Role</th><th>Joined</th><th /></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>
                  {currentUser?.role === 'owner' && u.id !== currentUser.id && u.role !== 'owner' ? (
                    <select value={u.role} onChange={(e) => updateRole(u.id, e.target.value)}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  ) : u.role}
                </td>
                <td>{formatDate(u.created_at)}</td>
                <td>
                  {currentUser?.role === 'owner' && u.id !== currentUser.id && u.role !== 'owner' && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={async () => {
                        await api(`/api/v1/admin/users/${u.id}/revoke-sessions`, { method: 'POST' })
                        await load()
                      }}
                    >
                      Revoke sessions
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {sso && (
        <div className="card">
          <h4>SSO / SCIM</h4>
          <p className="muted">OIDC: {sso.oidc_enabled ? 'enabled' : 'disabled'} · SAML: {sso.saml_enabled ? 'enabled' : 'disabled'} · SCIM: {sso.scim_enabled ? 'enabled' : 'disabled'}</p>
          {sso.saml_enabled && <p className="muted">SP metadata: <code>{sso.saml_metadata_url}</code></p>}
          {sso.scim_enabled && currentUser?.role === 'owner' && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={async () => {
                const res = await api('/api/v1/admin/scim-token', { method: 'POST' })
                window.prompt('Copy SCIM bearer token (shown once):', res.token)
              }}
            >
              Generate SCIM token
            </button>
          )}
        </div>
      )}

      <div className="card">
        <h4>Matter members</h4>
        <div className="row">
          <select value={matterId} onChange={(e) => setMatterId(e.target.value)}>
            <option value="">Select matter…</option>
            {matters.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <input type="email" placeholder="user@example.com" value={memberEmail} onChange={(e) => setMemberEmail(e.target.value)} />
          <select value={memberRole} onChange={(e) => setMemberRole(e.target.value)}>
            <option value="viewer">viewer</option>
            <option value="editor">editor</option>
            <option value="owner">owner</option>
          </select>
          <button type="button" className="btn btn-primary" onClick={inviteMember}>Invite</button>
        </div>
      </div>
    </div>
  )
}

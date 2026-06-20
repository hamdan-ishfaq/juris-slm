import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils.jsx'

export default function AuditView({ isAdmin, onForbidden }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [action, setAction] = useState('')
  const [live, setLive] = useState(false)
  const [selected, setSelected] = useState(null)
  const [since, setSince] = useState('')

  const load = async () => {
    if (!isAdmin) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '50' })
      if (action) params.set('action', action)
      if (since) params.set('since', since)
      const data = await api(`/api/v1/audit?${params}`)
      setEvents(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      if (e.message?.includes('403')) onForbidden?.()
      setEvents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [page, action, since, isAdmin])

  useEffect(() => {
    if (!live || !isAdmin) return undefined
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [live, isAdmin, page, action, since])

  const exportCsv = async () => {
    const blob = await api('/api/v1/audit/export')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'audit_export.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!isAdmin) {
    return (
      <div className="audit-layout animate-fade">
        <div className="card alert alert-warn">
          <h2>Audit trail — admin only</h2>
          <p>Your role does not have access to org audit logs. Contact an org_admin or owner.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="audit-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Audit trail</h2>
          <p className="muted">Immutable activity log — uploads, chat queries, exports.</p>
        </div>
        <div className="row">
          <button type="button" className="btn btn-secondary" onClick={exportCsv}>Export CSV</button>
          <button type="button" className={`btn btn-ghost ${live ? 'chip-active' : ''}`} onClick={() => setLive(!live)}>{live ? 'Live on' : 'Live tail'}</button>
        </div>
      </header>

      <div className="card row filters-row">
        <select value={action} onChange={(e) => { setAction(e.target.value); setPage(1) }}>
          <option value="">All actions</option>
          <option value="chat">chat</option>
          <option value="upload">upload</option>
          <option value="analyze">analyze</option>
          <option value="compare">compare</option>
          <option value="legal_hold_place">legal_hold_place</option>
          <option value="legal_hold_release">legal_hold_release</option>
        </select>
        <input type="datetime-local" value={since} onChange={(e) => setSince(e.target.value ? new Date(e.target.value).toISOString() : '')} />
        <span className="muted">{total} events</span>
      </div>

      {loading && <div className="card"><span className="spinner" /> Loading events…</div>}

      {!loading && (
        <div className="card audit-table-wrap">
          <table className="audit-table">
            <thead>
              <tr><th>Time</th><th>Action</th><th>Resource</th><th>Details</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="clickable" onClick={() => setSelected(e)}>
                  <td>{formatDate(e.timestamp)}</td>
                  <td><span className="action-tag">{e.action}</span></td>
                  <td>{e.resource_type}{e.resource_id ? ` · ${String(e.resource_id).slice(0, 8)}` : ''}</td>
                  <td className="details-cell">{e.details ? JSON.stringify(e.details).slice(0, 80) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!events.length && <p className="muted pad">No audit events yet.</p>}
          <div className="row pad">
            <button type="button" className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <span>Page {page}</span>
            <button type="button" className="btn btn-ghost btn-sm" disabled={events.length < 50} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      )}

      {selected && (
        <div className="drawer card animate-slide-in">
          <div className="row spread">
            <h4>Event detail</h4>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSelected(null)}>Close</button>
          </div>
          <pre className="code-block sm">{JSON.stringify(selected, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

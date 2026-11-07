import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils.jsx'

export default function CorpusView({ stats, loading, isAdmin }) {
  const [sources, setSources] = useState([])
  const [uploading, setUploading] = useState(false)
  const [title, setTitle] = useState('')
  const [jurisdiction, setJurisdiction] = useState('eu')
  const fileRef = useRef(null)

  const loadSources = () => {
    if (!isAdmin) return
    api('/api/v1/admin/corpus/sources').then(setSources).catch(() => setSources([]))
  }

  useEffect(() => {
    loadSources()
    const t = setInterval(loadSources, 5000)
    return () => clearInterval(t)
  }, [isAdmin])

  const onUpload = async (file) => {
    if (!file || !title.trim()) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('title', title.trim())
      fd.append('jurisdiction', jurisdiction)
      await api('/api/v1/admin/corpus/upload', { method: 'POST', body: fd })
      setTitle('')
      loadSources()
    } finally {
      setUploading(false)
    }
  }

  const reingest = async (id) => {
    await api(`/api/v1/admin/corpus/sources/${id}/ingest`, { method: 'POST' })
    loadSources()
  }

  if (loading) {
    return <div className="card animate-fade"><span className="spinner" /> Loading corpus stats…</div>
  }
  if (!stats) {
    return <div className="card alert alert-warn">Corpus stats unavailable.</div>
  }

  const bySource = stats.by_source || stats.sources || {}

  return (
    <div className="corpus-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Law corpus</h2>
          <p className="muted">Indexed regulatory text — GDPR, BGB, BDSG, EU AI Act, and admin uploads.</p>
        </div>
      </header>

      <div className="corpus-stats row">
        <div className="stat-card card highlight">
          <span className="stat-num">{stats.total_chunks ?? '—'}</span>
          <span>Total chunks</span>
        </div>
      </div>

      {isAdmin && (
        <div className="card">
          <h4>Upload law corpus</h4>
          <p className="muted">Add jurisdiction-specific regulations (TXT, PDF, or MD). Ingest runs in the background.</p>
          <div className="row" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
            <input type="text" placeholder="Title (e.g. UK GDPR excerpt)" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 2, minWidth: 200 }} />
            <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
              <option value="eu">EU</option>
              <option value="de">Germany</option>
              <option value="uk">UK</option>
              <option value="general">General</option>
            </select>
            <button type="button" className="btn btn-secondary" onClick={() => fileRef.current?.click()} disabled={uploading || !title.trim()}>
              {uploading ? 'Uploading…' : 'Choose file'}
            </button>
          </div>
          <input ref={fileRef} type="file" accept=".txt,.pdf,.md" hidden onChange={(e) => e.target.files[0] && onUpload(e.target.files[0])} />
        </div>
      )}

      {isAdmin && sources.length > 0 && (
        <div className="card">
          <h4>Admin corpus sources</h4>
          <table className="audit-table">
            <thead><tr><th>Title</th><th>Slug</th><th>Jurisdiction</th><th>Status</th><th>Chunks</th><th /></tr></thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id}>
                  <td>{s.title}</td>
                  <td><code>{s.slug}</code></td>
                  <td>{s.jurisdiction}</td>
                  <td><span className={`status-badge status-${s.status}`}>{s.status}</span></td>
                  <td>{s.chunk_count}</td>
                  <td>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => reingest(s.id)}>Re-ingest</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h4>Sources</h4>
        <div className="source-bars">
          {Object.entries(bySource).map(([name, count]) => (
            <div key={name} className="source-bar-row">
              <span>{name}</span>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (count / (stats.total_chunks || 1)) * 100 * 3)}%` }} /></div>
              <strong>{count}</strong>
            </div>
          ))}
          {!Object.keys(bySource).length && <p className="muted">Run <code>make ingest-law</code> or upload corpus above.</p>}
        </div>
      </div>
    </div>
  )
}

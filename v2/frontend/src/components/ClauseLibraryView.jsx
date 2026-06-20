import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils.jsx'

const CLAUSE_TYPES = ['confidentiality', 'indemnity', 'limitation', 'governing_law', 'data_protection', 'termination']

export default function ClauseLibraryView({ matterId, docId, onCompareClause, compareClauseBusy, compareClauseResult }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [clauseType, setClauseType] = useState('confidentiality')
  const [title, setTitle] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [jurisdiction, setJurisdiction] = useState('eu')
  const [selectedId, setSelectedId] = useState('')

  const load = () => api('/api/v1/clause-library').then(setItems).catch(() => setItems([]))

  useEffect(() => {
    setLoading(true)
    load().finally(() => setLoading(false))
  }, [])

  const createClause = async () => {
    if (!title.trim() || !bodyText.trim()) return
    await api('/api/v1/clause-library', {
      method: 'POST',
      body: JSON.stringify({
        clause_type: clauseType,
        title: title.trim(),
        body_text: bodyText.trim(),
        jurisdiction,
      }),
    })
    setTitle('')
    setBodyText('')
    await load()
  }

  const removeClause = async (id) => {
    if (!window.confirm('Delete this clause from the library?')) return
    await api(`/api/v1/clause-library/${id}`, { method: 'DELETE' })
    await load()
  }

  if (loading) return <div className="card"><span className="spinner" /> Loading clause library…</div>

  return (
    <div className="clause-library-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Clause bank</h2>
          <p className="muted">Firm standard clauses — compare uploaded contracts against your playbook.</p>
        </div>
      </header>

      <div className="card">
        <h4>Add standard clause</h4>
        <div className="row" style={{ flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <select value={clauseType} onChange={(e) => setClauseType(e.target.value)}>
            {CLAUSE_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
          </select>
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="eu">EU</option>
            <option value="de">Germany</option>
            <option value="uk">UK</option>
            <option value="general">General</option>
          </select>
        </div>
        <input type="text" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: '100%', marginBottom: '0.5rem' }} />
        <textarea placeholder="Clause body text…" value={bodyText} onChange={(e) => setBodyText(e.target.value)} rows={5} style={{ width: '100%' }} />
        <button type="button" className="btn btn-primary" style={{ marginTop: '0.5rem' }} onClick={createClause}>Save clause</button>
      </div>

      <div className="card">
        <h4>Saved clauses ({items.length})</h4>
        {items.length === 0 && <p className="muted">No clauses yet — add your firm standards above.</p>}
        <table className="audit-table">
          <thead><tr><th>Type</th><th>Title</th><th>Jurisdiction</th><th>Updated</th><th /></tr></thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className={selectedId === c.id ? 'selected' : ''} onClick={() => setSelectedId(c.id)}>
                <td>{c.clause_type}</td>
                <td>{c.title}</td>
                <td>{c.jurisdiction}</td>
                <td>{formatDate(c.updated_at)}</td>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); removeClause(c.id) }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {matterId && docId && selectedId && (
        <div className="card">
          <h4>Compare document to selected clause</h4>
          <button type="button" className="btn btn-secondary" disabled={compareClauseBusy} onClick={() => onCompareClause?.(selectedId)}>
            {compareClauseBusy ? 'Comparing…' : 'Compare to standard'}
          </button>
          {compareClauseResult && (
            <div className="answer-body" style={{ marginTop: '1rem', whiteSpace: 'pre-wrap' }}>
              <span className={`status-badge status-${compareClauseResult.deviation_flag === 'deviates' ? 'failed' : 'processed'}`}>
                {compareClauseResult.deviation_flag}
              </span>
              <div>{compareClauseResult.comparison_result}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'

export default function ContractEditor({
  open,
  onClose,
  filename,
  workspace,
  onSave,
  onExportDocx,
  onAddAnnotation,
  saving,
  readOnly,
}) {
  const [text, setText] = useState('')
  const [versionNumber, setVersionNumber] = useState(null)
  const [comment, setComment] = useState('')
  const [selectedClause, setSelectedClause] = useState('')

  useEffect(() => {
    if (workspace) {
      setText(workspace.content_text || '')
      setVersionNumber(workspace.version_number)
    }
  }, [workspace])

  if (!open) return null

  const clauses = workspace?.clauses || []

  return (
    <div className="modal-overlay" role="dialog" aria-label="Contract editor">
      <div className="modal card contract-editor">
        <header className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h3>Contract editor</h3>
            <p className="muted">{filename} · v{versionNumber || 1}{readOnly ? ' · read-only (legal hold)' : ''}</p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
        </header>
        <div className="contract-editor-body">
          <aside className="clause-sidebar">
            <h4>Clauses</h4>
            <ul>
              {clauses.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`clause-link ${selectedClause === c.id ? 'active' : ''}`}
                    onClick={() => setSelectedClause(c.id)}
                  >
                    {c.title || c.id}
                  </button>
                </li>
              ))}
              {!clauses.length && <li className="muted">No structured clauses detected</li>}
            </ul>
          </aside>
          <div className="editor-main">
            <textarea
              className="contract-textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              readOnly={readOnly}
              rows={18}
            />
            {!readOnly && (
              <div className="row" style={{ marginTop: '0.75rem' }}>
                <input
                  type="text"
                  placeholder="Annotation on selected clause…"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  style={{ flex: 1 }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={!comment.trim() || !selectedClause}
                  onClick={() => {
                    onAddAnnotation?.(selectedClause, comment.trim())
                    setComment('')
                  }}
                >
                  Add note
                </button>
              </div>
            )}
          </div>
        </div>
        <footer className="row" style={{ marginTop: '1rem' }}>
          {!readOnly && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={saving || !text.trim()}
              onClick={() => onSave?.(text, versionNumber)}
            >
              {saving ? 'Saving…' : 'Save version'}
            </button>
          )}
          <button type="button" className="btn btn-secondary" onClick={onExportDocx}>Export DOCX</button>
        </footer>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { MATTER_PROMPTS, CONFIDENTIALITY_LEVELS, canUploadLevel } from '../constants/prompts'
import { formatDate, riskColor } from '../lib/utils.jsx'

export default function MattersView({
  matters,
  matterId,
  setMatterId,
  documents,
  docId,
  setDocId,
  onCreateMatter,
  onDeleteMatter,
  onUpload,
  onBulkUpload,
  onBulkFiles,
  analyzeQ,
  setAnalyzeQ,
  analyzeResult,
  compareResult,
  analyzeBusy,
  compareBusy,
  onAnalyze,
  onCompare,
  onExportAnalyze,
  onExportCompare,
  onOpenEditor,
  gapBusy,
  gapStep,
  gapReport,
  onGapAnalysis,
  userRole,
  legalHolds,
  onPlaceHold,
  onReleaseHold,
  holdReason,
  setHoldReason,
  docStatuses,
  pollDocStatus,
  uploadConfidentiality,
  setUploadConfidentiality,
  bulkProgress,
  clauseItems,
  selectedClauseId,
  setSelectedClauseId,
  onCompareClause,
  compareClauseBusy,
  compareClauseResult,
  deadlines,
  deadlineTitle,
  setDeadlineTitle,
  deadlineDate,
  setDeadlineDate,
  onAddDeadline,
  onToggleDeadline,
}) {
  const fileRef = useRef(null)
  const multiRef = useRef(null)
  const zipRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const docStatusesRef = useRef(docStatuses)
  docStatusesRef.current = docStatuses

  useEffect(() => {
    if (!documents.length || !pollDocStatus) return undefined

    const tick = () => {
      documents.forEach((d) => {
        const raw = docStatusesRef.current?.[d.id]
        const st = (typeof raw === 'string' ? raw : raw?.status) || d.ingest_status || d.status
        if (st !== 'processed' && st !== 'ready' && st !== 'failed') {
          pollDocStatus(d.id)
        }
      })
    }
    tick()
    const id = setInterval(tick, 2500)
    return () => clearInterval(id)
  }, [documents, pollDocStatus])

  const structured = analyzeResult?.structured
  const risk = analyzeResult?.risk
  const playbook = analyzeResult?.playbook
  const uploadLevels = CONFIDENTIALITY_LEVELS.filter((c) => canUploadLevel(userRole || 'member', c.value))
  const isAdmin = userRole === 'owner' || userRole === 'org_admin'
  const activeHolds = (legalHolds || []).filter((h) => h.status === 'active')
  const activeMatterHold = activeHolds.find((h) => h.matter_id && !h.document_id)

  const statusBadge = (doc) => {
    const raw = docStatuses?.[doc.id]
    const polled = typeof raw === 'string' ? raw : raw?.status
    const fromDoc = doc.ingest_status || doc.status
    const st =
      fromDoc === 'processed' || fromDoc === 'failed' || fromDoc === 'ready'
        ? fromDoc
        : polled || fromDoc || 'pending'
    const ocr = typeof raw === 'object' && raw?.ocr_used
    return (
      <span className="status-cell">
        <span className={`status-badge status-${st}`}>{st}</span>
        {ocr && <span className="trust-pill" style={{ marginLeft: '0.35rem' }}>OCR</span>}
      </span>
    )
  }

  return (
    <div className="matters-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Matter workspace</h2>
          <p className="muted">Upload contracts, run clause analysis, and compare against GDPR/BGB baseline.</p>
        </div>
        <div className="row">
          <button type="button" className="btn btn-primary" onClick={onCreateMatter}>+ New matter</button>
          {matterId && (
            <button type="button" className="btn btn-ghost" onClick={() => onDeleteMatter?.(matterId)}>Delete matter</button>
          )}
        </div>
      </header>

      <div className="matters-toolbar card">
        <label className="field-inline">
          <span>Matter</span>
          <select value={matterId} onChange={(e) => setMatterId(e.target.value)}>
            <option value="">Select matter…</option>
            {matters.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          <span>Document</span>
          <select value={docId} onChange={(e) => setDocId(e.target.value)} disabled={!matterId}>
            <option value="">Select document…</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>{d.filename || d.id.slice(0, 8)} ({docStatuses?.[d.id] || d.status || 'pending'})</option>
            ))}
          </select>
        </label>
        {matterId && (
          <label className="field-inline">
            <span>Confidentiality</span>
            <select value={uploadConfidentiality} onChange={(e) => setUploadConfidentiality(e.target.value)}>
              {uploadLevels.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </label>
        )}
      </div>

      {matterId && activeMatterHold && (
        <div className="card alert alert-warn">
          <strong>Legal hold active</strong> — {activeMatterHold.reason}
          {isAdmin && (
            <button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: '1rem' }} onClick={() => onReleaseHold?.(activeMatterHold.id)}>
              Release hold
            </button>
          )}
        </div>
      )}

      {matterId && isAdmin && !activeMatterHold && (
        <div className="card row">
          <input
            type="text"
            placeholder="Legal hold reason…"
            value={holdReason || ''}
            onChange={(e) => setHoldReason?.(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="button" className="btn btn-secondary" disabled={!holdReason?.trim()} onClick={() => onPlaceHold?.()}>
            Place legal hold
          </button>
        </div>
      )}

      {matterId && (
        <div
          className={`dropzone card ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const f = e.dataTransfer.files[0]
            if (f) onUpload(f)
          }}
        >
          <p><strong>Drop files here</strong> or upload individually / as zip bulk ingest</p>
          {bulkProgress && <p className="muted">{bulkProgress}</p>}
          <div className="row">
            <button type="button" className="btn btn-secondary" onClick={() => fileRef.current?.click()}>Upload document</button>
            <button type="button" className="btn btn-secondary" onClick={() => multiRef.current?.click()}>Upload folder</button>
            <button type="button" className="btn btn-secondary" onClick={() => zipRef.current?.click()}>Bulk zip</button>
          </div>
          <input ref={fileRef} type="file" hidden onChange={(e) => e.target.files[0] && onUpload(e.target.files[0])} />
          <input ref={multiRef} type="file" multiple hidden onChange={(e) => e.target.files?.length && onBulkFiles?.(e.target.files)} />
          <input ref={zipRef} type="file" accept=".zip" hidden onChange={(e) => e.target.files[0] && onBulkUpload(e.target.files[0])} />
        </div>
      )}

      {matterId && (
        <div className="card">
          <h4>Deadlines</h4>
          <div className="row" style={{ flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <input type="text" placeholder="Deadline title" value={deadlineTitle || ''} onChange={(e) => setDeadlineTitle?.(e.target.value)} style={{ flex: 2, minWidth: 160 }} />
            <input type="date" value={deadlineDate || ''} onChange={(e) => setDeadlineDate?.(e.target.value)} />
            <button type="button" className="btn btn-secondary btn-sm" disabled={!deadlineTitle?.trim() || !deadlineDate} onClick={() => onAddDeadline?.()}>Add</button>
          </div>
          {(deadlines || []).length === 0 && <p className="muted">No deadlines for this matter.</p>}
          <ul className="value-list">
            {(deadlines || []).map((d) => (
              <li key={d.id}>
                <strong>{d.title}</strong> — {d.due_date}
                <span className={`status-badge status-${d.status === 'done' ? 'processed' : 'processing'}`} style={{ marginLeft: '0.5rem' }}>{d.status}</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onToggleDeadline?.(d.id, d.status === 'done' ? 'open' : 'done')}>
                  {d.status === 'done' ? 'Reopen' : 'Done'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {documents.length > 0 && (
        <div className="doc-table card">
          <table>
            <thead>
              <tr><th>File</th><th>Status</th><th>Confidentiality</th><th>Uploaded</th></tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id} className={d.id === docId ? 'selected' : ''} onClick={() => setDocId(d.id)}>
                  <td>{d.filename}</td>
                  <td>{statusBadge(d)}</td>
                  <td>{d.confidentiality || 'internal'}</td>
                  <td>{formatDate(d.uploaded_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {docId && ((typeof docStatuses?.[docId] === 'object' ? docStatuses[docId]?.status : docStatuses?.[docId]) === 'processed' || documents.find((d) => d.id === docId)?.ingest_status === 'processed' || documents.find((d) => d.id === docId)?.status === 'processed') && (
        <div className="analyze-section card">
          <h3>Document analysis</h3>
          <div className="prompt-row">
            {MATTER_PROMPTS.map((p) => (
              <button key={p.label} type="button" className="prompt-chip sm" onClick={() => setAnalyzeQ(p.text)}>{p.label}</button>
            ))}
          </div>
          <textarea value={analyzeQ} onChange={(e) => setAnalyzeQ(e.target.value)} rows={2} />
          <div className="row">
            <button type="button" className="btn btn-primary" disabled={analyzeBusy} onClick={onAnalyze}>Analyze clauses</button>
            <button type="button" className="btn btn-secondary" disabled={compareBusy} onClick={onCompare}>Compare vs law baseline</button>
            {clauseItems?.length > 0 && (
              <>
                <select className="select-compact" value={selectedClauseId || ''} onChange={(e) => setSelectedClauseId?.(e.target.value)}>
                  <option value="">Standard clause…</option>
                  {clauseItems.map((c) => (
                    <option key={c.id} value={c.id}>{c.title} ({c.clause_type})</option>
                  ))}
                </select>
                <button type="button" className="btn btn-secondary" disabled={compareClauseBusy || !selectedClauseId} onClick={() => onCompareClause?.(selectedClauseId)}>
                  Compare to standard
                </button>
              </>
            )}
            <button type="button" className="btn btn-secondary" disabled={gapBusy} onClick={onGapAnalysis}>Run gap analysis</button>
            <button type="button" className="btn btn-secondary" onClick={onOpenEditor}>Open contract editor</button>
          </div>
          {gapBusy && gapStep && <p className="muted">Workflow: {gapStep}</p>}
        </div>
      )}

      {gapReport && (
        <div className="card">
          <h3>Regulatory gap report</h3>
          <p className="muted">{gapReport.summary}</p>
          <table className="audit-table">
            <thead><tr><th>Severity</th><th>Law ref</th><th>Gap</th><th>Recommendation</th></tr></thead>
            <tbody>
              {(gapReport.gaps || []).map((g, i) => (
                <tr key={i}>
                  <td><span className={`status-badge status-${g.severity === 'aligned' ? 'processed' : g.severity === 'missing' ? 'failed' : 'processing'}`}>{g.severity}</span></td>
                  <td>{g.law_reference}</td>
                  <td>{g.gap_description}</td>
                  <td>{g.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {docId && docStatuses?.[docId] !== 'processed' && documents.find((d) => d.id === docId)?.status !== 'processed' && (
        <div className="card alert alert-warn">Document still processing — analyze/compare unlock when status is <strong>processed</strong>.</div>
      )}

      {analyzeResult && (
        <div className="results-grid">
          {risk && (
            <div className="card risk-card">
              <h4>Clause risk</h4>
              <div className={`risk-score ${riskColor(risk.risk_level || 'medium')}`}>
                {(risk.risk_level || '—').toUpperCase()}
              </div>
              {risk.high_signals?.length > 0 && <p>High: {risk.high_signals.join(', ')}</p>}
              {risk.medium_signals?.length > 0 && <p>Medium: {risk.medium_signals.join(', ')}</p>}
            </div>
          )}
          {playbook?.length > 0 && (
            <div className="card">
              <h4>Playbook checks</h4>
              <ul className="check-list">
                {playbook.map((item, i) => (
                  <li key={i} className={item.passed ? 'pass' : 'fail'}>
                    {item.passed ? '✓' : '✗'} {item.label}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="card span-2">
            <div className="row spread">
              <h4>Structured analysis</h4>
              <button type="button" className="btn btn-ghost btn-sm" onClick={onExportAnalyze}>Export report</button>
            </div>
            <pre className="code-block">{JSON.stringify(structured || analyzeResult, null, 2)}</pre>
          </div>
        </div>
      )}

      {compareResult && (
        <div className="card compare-result animate-fade-up">
          <div className="row spread">
            <h4>Baseline comparison</h4>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onExportCompare}>Export report</button>
          </div>
          <div className="compare-body">{compareResult.comparison_result || compareResult.answer || JSON.stringify(compareResult)}</div>
        </div>
      )}

      {compareClauseResult && (
        <div className="card compare-result animate-fade-up">
          <h4>Clause library comparison</h4>
          <span className={`status-badge status-${compareClauseResult.deviation_flag === 'deviates' ? 'failed' : 'processed'}`}>
            {compareClauseResult.deviation_flag}
          </span>
          <div className="compare-body">{compareClauseResult.comparison_result}</div>
        </div>
      )}
    </div>
  )
}

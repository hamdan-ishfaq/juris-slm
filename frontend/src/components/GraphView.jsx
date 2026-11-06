export default function GraphView({
  matters,
  matterId,
  setMatterId,
  documents,
  docId,
  setDocId,
  graph,
  onLoad,
  onExtract,
  loading,
  extractLoading,
  loadError,
}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const processedDocs = documents.filter(
    (d) => (d.ingest_status || d.status) === 'processed' || (d.ingest_status || d.status) === 'ready',
  )
  const hasGraph = nodes.length > 0 || edges.length > 0
  const selectedMatter = matters.find((m) => m.id === matterId)

  return (
    <div className="graph-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>Knowledge graph</h2>
          <p className="muted">Contract entities extracted from processed documents.</p>
        </div>
        <div className="row">
          <button type="button" className="btn btn-secondary" disabled={!docId || extractLoading} onClick={onExtract}>
            {extractLoading ? 'Extracting…' : 'Extract graph'}
          </button>
          <button type="button" className="btn btn-primary" disabled={!docId || loading} onClick={onLoad}>
            {loading ? 'Loading…' : 'Load graph'}
          </button>
        </div>
      </header>

      {!matters.length && (
        <div className="card alert alert-warn">
          No matters yet. Go to <strong>Matters</strong> → <strong>+ New matter</strong>, upload a contract, then return here.
        </div>
      )}

      <div className="matters-toolbar card">
        <label className="field-inline">
          <span>Matter</span>
          <select value={matterId} onChange={(e) => { setMatterId(e.target.value); setDocId('') }}>
            <option value="">Select…</option>
            {matters.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          <span>Document</span>
          <select value={docId} onChange={(e) => setDocId(e.target.value)} disabled={!matterId}>
            <option value="">{processedDocs.length ? 'Select…' : 'No processed docs'}</option>
            {processedDocs.map((d) => (
              <option key={d.id} value={d.id}>{d.filename}</option>
            ))}
          </select>
        </label>
        {selectedMatter && (
          <span className="muted">{processedDocs.length} processed document{processedDocs.length === 1 ? '' : 's'}</span>
        )}
      </div>

      {matterId && !processedDocs.length && (
        <div className="card alert alert-warn">
          No processed documents in <strong>{selectedMatter?.name || 'this matter'}</strong>.
          Upload a contract in Matters and wait for status <strong>processed</strong>.
        </div>
      )}

      {loadError && (
        <div className="card alert alert-warn">{loadError}</div>
      )}

      <div className="graph-stats row">
        <div className="stat-card card"><span className="stat-num">{nodes.length}</span><span>Entities</span></div>
        <div className="stat-card card"><span className="stat-num">{edges.length}</span><span>Relationships</span></div>
      </div>

      {!hasGraph ? (
        <div className="empty-graph card" data-testid="graph-empty">
          <div className="graph-empty-icon" aria-hidden>◇</div>
          <p className="muted graph-empty-text">
            {docId
              ? <>Document selected. Click <strong>Extract graph</strong>, then <strong>Load graph</strong>.</>
              : <>Select a matter and processed document above to begin.</>}
          </p>
        </div>
      ) : (
        <div className="graph-panels">
          <div className="card">
            <h4>Entities</h4>
            <ul className="entity-list">
              {nodes.map((n, i) => (
                <li key={n.id || i} className="animate-fade-up" style={{ animationDelay: `${i * 40}ms` }}>
                  <span className="entity-type">{n.type || 'entity'}</span>
                  <strong>{n.name}</strong>
                  {n.description && <p>{n.description}</p>}
                </li>
              ))}
            </ul>
          </div>
          <div className="card">
            <h4>Edges</h4>
            <ul className="edge-list">
              {edges.map((e, i) => (
                <li key={e.id || i}>
                  <code>{e.type || e.relation}</code>
                  <span>{String(e.source).slice(0, 8)} → {String(e.target).slice(0, 8)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

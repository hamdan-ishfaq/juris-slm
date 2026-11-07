import { highlightSnippet, confidenceLevel } from '../lib/utils.jsx'

export default function SourcePanel({ sources, query, activeIdx, onSelect }) {
  if (!sources?.length) {
    return (
      <aside className="source-panel empty">
        <header>
          <h3>Sources</h3>
          <p className="muted">Citations appear here after each answer — click to inspect the retrieved chunk.</p>
        </header>
        <div className="source-empty-art">
          <div className="citation-stack">
            <div className="cite-card ghost" style={{ animationDelay: '0ms' }} />
            <div className="cite-card ghost" style={{ animationDelay: '120ms' }} />
            <div className="cite-card ghost" style={{ animationDelay: '240ms' }} />
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="source-panel">
      <header>
        <h3>Sources</h3>
        <span className="count-badge">{sources.length}</span>
      </header>
      <div className="source-list">
        {sources.map((s, i) => {
          const conf = confidenceLevel(s.rerank_score)
          const isActive = activeIdx === i
          return (
            <button
              type="button"
              key={i}
              className={`source-card animate-slide-in ${isActive ? 'active' : ''}`}
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => onSelect(i)}
            >
              <div className="source-head">
                <span className="source-idx">[{i + 1}]</span>
                <strong>{s.label || s.source || 'Source'}</strong>
              </div>
              <div className="source-meta">
                <span className={`conf-pill ${conf.cls}`}>{conf.label}</span>
                {conf.pct != null && (
                  <div className="conf-bar" title={`Rerank: ${s.rerank_score ?? 'n/a'}`}>
                    <div className="conf-fill" style={{ width: `${conf.pct}%` }} />
                  </div>
                )}
              </div>
              <p className="source-snippet">{highlightSnippet(s.content || '', query)}</p>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

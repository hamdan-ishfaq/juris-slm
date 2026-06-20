import { useEffect, useState } from 'react'
import { api, isAdminRole } from '../lib/api'

export default function SystemView({ status, currentUser, evalStatus, onRunEval }) {
  const [evalData, setEvalData] = useState(evalStatus)

  useEffect(() => {
    if (!isAdminRole(currentUser?.role)) return
    api('/api/v1/admin/eval-status').then(setEvalData).catch(() => {})
  }, [currentUser, evalStatus])

  if (!status) {
    return <div className="card"><span className="spinner" /> Loading system status…</div>
  }

  const tiers = status.model_tiers || {}
  const retrieval = status.retrieval || {}
  const reports = evalData?.reports || {}
  const logical = reports.logical
  const ragasNative = reports.ragas_native || reports.ragas
  const latency = reports.latency

  return (
    <div className="system-layout animate-fade">
      <header className="view-header">
        <div>
          <h2>System</h2>
          <p className="muted">Model tiers, retrieval stack, and quality metrics.</p>
        </div>
        <span className={`profile-banner ${status.llm_profile === 'airgap' ? 'airgap' : 'dev'}`}>
          {status.llm_profile === 'airgap' ? '● Air-gap — zero cloud LLM' : '● Dev — OpenRouter generation'}
        </span>
      </header>

      <div className="tier-grid">
        <div className="tier-card card">
          <span className="tier-label">T0 Retrieval</span>
          <strong>Local always</strong>
          <ul>
            <li>Embedding: {status.models?.embedding_ready ? 'ready' : 'loading'}</li>
            <li>Reranker: {status.models?.reranker_ready ? 'ready' : 'loading'}</li>
            <li>Hybrid FTS: {retrieval.hybrid_search ? 'on' : 'off'}</li>
            <li>Cache hit rate: {status.query_cache?.hit_rate != null ? `${(status.query_cache.hit_rate * 100).toFixed(1)}%` : '—'}</li>
          </ul>
        </div>
        <div className="tier-card card">
          <span className="tier-label">T1 Aux</span>
          <strong>{tiers.aux?.model || status.aux_llm?.model || '—'}</strong>
          <p>{status.aux_llm?.reachable ? 'Reachable' : 'Unreachable'}</p>
          <small>HyDE · decompose · graph extract</small>
        </div>
        <div className="tier-card card accent">
          <span className="tier-label">T2 Generation</span>
          <strong>{tiers.generation?.model || status.llm?.model || '—'}</strong>
          <p>{status.llm?.reachable ? 'Reachable' : 'Unreachable'}</p>
          <small>RAG answers · analyze · compare</small>
        </div>
        <div className="tier-card card">
          <span className="tier-label">T3 Fallback</span>
          <strong>Extractive</strong>
          <p>When model refuses context</p>
        </div>
      </div>

      {status.hardware && (
        <div className="card" data-testid="hardware-panel">
          <h4>Hardware / ML devices</h4>
          <ul className="value-list">
            <li>
              <strong>CUDA</strong> — {status.hardware.cuda_available ? 'available' : 'not available'}
            </li>
            <li>
              <strong>Embedding</strong> — {status.hardware.embedding_device || '—'}
              {status.hardware.embedding_device_config && (
                <span className="muted"> (config: {status.hardware.embedding_device_config})</span>
              )}
            </li>
            <li>
              <strong>Reranker</strong> — {status.hardware.reranker_device || '—'}
            </li>
            {status.hardware.airgap_latency_profile && (
              <li><strong>Air-gap latency profile</strong> — enabled</li>
            )}
          </ul>
          {!status.hardware.cuda_available && (
            <p className="muted">For GPU embed/rerank in Docker: <code>make up-gpu</code>. For chat on GPU: host Ollama + <code>LLM_PROVIDER=ollama</code>.</p>
          )}
        </div>
      )}

      {isAdminRole(currentUser?.role) && status.environment === 'development' && (
        <div className="card quality-panel">
          <div className="row spread">
            <h4>Quality dashboard</h4>
            <button type="button" className="btn btn-primary btn-sm" disabled={evalData?.running} onClick={onRunEval}>
              {evalData?.running ? 'Running…' : 'Run full test suite'}
            </button>
          </div>
          <div className="corpus-stats row">
            <div className="stat-card card">
              <span className="stat-num">{logical?.pass_rate != null ? `${(logical.pass_rate * 100).toFixed(1)}%` : logical?.passed != null ? `${logical.passed}/${logical.total}` : '—'}</span>
              <span>Logical eval</span>
            </div>
            <div className="stat-card card">
              <span className="stat-num">{ragasNative?.metrics?.faithfulness?.toFixed?.(2) ?? '—'}</span>
              <span>RAGAS faithfulness</span>
            </div>
            <div className="stat-card card">
              <span className="stat-num">{latency?.p95_ms != null ? `${latency.p95_ms}ms` : '—'}</span>
              <span>Latency p95</span>
            </div>
          </div>
          {evalData?.log?.length > 0 && (
            <pre className="code-block sm">{evalData.log.slice(-8).join('\n')}</pre>
          )}
        </div>
      )}

      <div className="card">
        <h4>Build</h4>
        <p className="muted">Hash: {status.build_hash || '—'}</p>
      </div>
    </div>
  )
}

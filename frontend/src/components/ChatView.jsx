import { useEffect, useState } from 'react'
import { LAW_PROMPTS } from '../constants/prompts'
import SourcePanel from './SourcePanel'

export default function ChatView({
  message,
  setMessage,
  answer,
  sources,
  busy,
  lang,
  threads,
  threadId,
  setThreadId,
  onSend,
  onFeedback,
  onExport,
  onExportMd,
  lowConfidence,
  useHyde,
  setUseHyde,
  useLawCorpus,
  setUseLawCorpus,
  chatHistory,
  brandName,
}) {
  const [activeSource, setActiveSource] = useState(0)

  const handleSend = async () => {
    if (!message.trim() || busy) return
    await onSend()
  }

  const applyPrompt = (text) => {
    const prefix = lang === 'de' ? '[DE] ' : ''
    setMessage(prefix + text)
  }

  return (
    <div className="chat-layout">
      <div className="chat-main">
        <div className="chat-toolbar">
          <select className="select-compact" value={threadId} onChange={(e) => setThreadId(e.target.value)}>
            <option value="">New conversation</option>
            {threads.map((t) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
          <button type="button" className={`chip ${useHyde ? 'chip-active' : ''}`} onClick={() => setUseHyde(!useHyde)}>HyDE</button>
          <button type="button" className={`chip chip-teal ${useLawCorpus ? 'chip-active' : ''}`} onClick={() => setUseLawCorpus(!useLawCorpus)}>Law corpus</button>
        </div>

        <div className="chat-scroll">
          {chatHistory?.map((m, idx) => (
            <div key={idx} className={`bubble bubble-${m.role === 'user' ? 'user' : 'assistant'} animate-fade-up`}>
              <span className="bubble-label">{m.role === 'user' ? 'You' : (brandName || 'JurisGuard')}</span>
              <div className="answer-body">{m.content}</div>
            </div>
          ))}

          {!answer && !busy && !chatHistory?.length && (
            <div className="welcome animate-fade">
              <h2>Research assistant</h2>
              <p>Ask about GDPR, BGB, BDSG, or EU AI Act. Answers are grounded in your indexed corpus with verifiable sources.</p>
              <div className="prompt-grid">
                {LAW_PROMPTS.map((p, i) => (
                  <button
                    key={p.label}
                    type="button"
                    className="prompt-chip animate-fade-up"
                    style={{ animationDelay: `${i * 50}ms` }}
                    onClick={() => applyPrompt(p.text)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {busy && (
            <div className="bubble bubble-assistant loading animate-fade">
              <span className="bubble-label">{brandName || 'JurisGuard'}</span>
              <div className="typing"><span /><span /><span /></div>
              <p className="muted">Retrieving · reranking · generating…</p>
            </div>
          )}

          {answer && !busy && (
            <div className="bubble bubble-assistant animate-fade-up">
              <span className="bubble-label">Answer</span>
              {lowConfidence && (
                <div className="alert alert-warn">
                  Low retrieval confidence — verify citations before relying on this response.
                </div>
              )}
              <div className="answer-body">{answer}</div>
              <div className="answer-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onFeedback('up')}>Helpful</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => onFeedback('down')}>Not helpful</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={onExport}>Export PDF</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={onExportMd}>Export MD</button>
              </div>
            </div>
          )}
        </div>

        <div className="composer">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={lang === 'de' ? 'Rechtsfrage stellen…' : 'Ask a legal research question…'}
            rows={2}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          <button type="button" className="btn btn-primary" disabled={busy || !message.trim()} onClick={handleSend}>
            {busy ? <span className="spinner" /> : 'Send'}
          </button>
        </div>
      </div>

      <SourcePanel sources={sources} query={message} activeIdx={activeSource} onSelect={setActiveSource} />
    </div>
  )
}

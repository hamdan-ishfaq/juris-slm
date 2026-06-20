import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, apiStream, clearToken, getToken, isAdminRole, pollChatJob, setApiHandlers, setSession, setToken } from './lib/api'
import LoginPage from './components/LoginPage'
import AuthCallback from './components/AuthCallback'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import MattersView from './components/MattersView'
import ContractEditor from './components/ContractEditor'
import GraphView from './components/GraphView'
import CorpusView from './components/CorpusView'
import ClauseLibraryView from './components/ClauseLibraryView'
import AuditView from './components/AuditView'
import SystemView from './components/SystemView'
import AdminView from './components/AdminView'
import HelpView from './components/HelpView'
import ExportModal from './components/ExportModal'
import Toast from './components/Toast'

const DEFAULT_EMAIL = import.meta.env.VITE_DEV_EMAIL || ''
const DEFAULT_PASSWORD = import.meta.env.VITE_DEV_PASSWORD || ''

export default function App() {
  const [email, setEmail] = useState(DEFAULT_EMAIL)
  const [password, setPassword] = useState(DEFAULT_PASSWORD)
  const [token, setTokenState] = useState(getToken())
  const [currentUser, setCurrentUser] = useState(null)
  const [view, setView] = useState('research')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [mobileNav, setMobileNav] = useState(false)

  const [message, setMessage] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [chatHistory, setChatHistory] = useState([])
  const [useHyde, setUseHyde] = useState(false)
  const [useLawCorpus, setUseLawCorpus] = useState(true)
  const [chatBusy, setChatBusy] = useState(false)
  const [analyzeBusy, setAnalyzeBusy] = useState(false)
  const [compareBusy, setCompareBusy] = useState(false)

  const [matters, setMatters] = useState([])
  const [matterId, setMatterId] = useState('')
  const [documents, setDocuments] = useState([])
  const [docId, setDocId] = useState('')
  const [docStatuses, setDocStatuses] = useState({})
  const [uploadConfidentiality, setUploadConfidentiality] = useState('internal')
  const [bulkProgress, setBulkProgress] = useState('')
  const [legalHolds, setLegalHolds] = useState([])
  const [holdReason, setHoldReason] = useState('')
  const [gapBusy, setGapBusy] = useState(false)
  const [gapStep, setGapStep] = useState('')
  const [gapReport, setGapReport] = useState(null)
  const [compareClauseBusy, setCompareClauseBusy] = useState(false)
  const [compareClauseResult, setCompareClauseResult] = useState(null)
  const [clauseItems, setClauseItems] = useState([])
  const [selectedClauseId, setSelectedClauseId] = useState('')
  const [deadlines, setDeadlines] = useState([])
  const [deadlineTitle, setDeadlineTitle] = useState('')
  const [deadlineDate, setDeadlineDate] = useState('')
  const [editorOpen, setEditorOpen] = useState(false)
  const [workspace, setWorkspace] = useState(null)
  const [workspaceSaving, setWorkspaceSaving] = useState(false)

  const [status, setStatus] = useState(null)
  const [corpusStats, setCorpusStats] = useState(null)
  const [lang, setLang] = useState('en')
  const [analyzeQ, setAnalyzeQ] = useState('Summarize confidentiality obligations')
  const [analyzeResult, setAnalyzeResult] = useState(null)
  const [compareResult, setCompareResult] = useState(null)
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [graphLoading, setGraphLoading] = useState(false)
  const [graphExtractLoading, setGraphExtractLoading] = useState(false)
  const [graphLoadError, setGraphLoadError] = useState('')
  const [threads, setThreads] = useState([])
  const [threadId, setThreadId] = useState('')
  const [evalStatus, setEvalStatus] = useState(null)
  const [exportModalOpen, setExportModalOpen] = useState(false)
  const [ssoStatus, setSsoStatus] = useState(null)
  const [branding, setBranding] = useState(null)
  const isAuthCallback = typeof window !== 'undefined' && window.location.pathname === '/auth/callback'

  const isAdmin = isAdminRole(currentUser?.role)

  const lowConfidence = useMemo(() => {
    if (!sources.length) return false
    const top = sources[0]?.rerank_score
    return top != null && top < -2
  }, [sources])

  const showToast = useCallback((msg, type = 'error') => setToast({ message: msg, type }), [])

  useEffect(() => {
    setApiHandlers({
      onError: (msg) => showToast(msg, 'error'),
      onUnauthorized: () => {
        clearToken()
        setTokenState('')
        setCurrentUser(null)
        showToast('Session expired — please sign in again.', 'error')
      },
    })
  }, [showToast])

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/config/branding`)
      .then((r) => r.json())
      .then((b) => {
        setBranding(b)
        if (b.brand_primary_color) {
          document.documentElement.style.setProperty('--accent', b.brand_primary_color)
        }
      })
      .catch(() => setBranding(null))
  }, [])

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/auth/sso/status`)
      .then((r) => r.json())
      .then(setSsoStatus)
      .catch(() => setSsoStatus(null))
  }, [])

  const refreshMatters = useCallback(
    () => api('/api/v1/matters').then((rows) => { setMatters(rows); return rows }).catch(() => { setMatters([]); return [] }),
    [],
  )

  const loadUser = useCallback(async () => {
    try {
      const me = await api('/api/v1/auth/me')
      setCurrentUser(me)
    } catch {
      setCurrentUser(null)
    }
  }, [])

  useEffect(() => {
    if (!token) return
    loadUser()
    api('/api/v1/status').then(setStatus).catch(() => setStatus(null))
    refreshMatters()
    api('/api/v1/threads').then(setThreads).catch(() => setThreads([]))
  }, [token, loadUser])

  useEffect(() => {
    if (!token || (view !== 'clauses' && view !== 'matters')) return
    api('/api/v1/clause-library').then(setClauseItems).catch(() => setClauseItems([]))
  }, [token, view])

  useEffect(() => {
    if (!token || view !== 'corpus' || !isAdmin) return
    setCorpusStats(null)
    api('/api/v1/corpus/stats').then(setCorpusStats).catch(() => setCorpusStats({}))
  }, [token, view, isAdmin])

  useEffect(() => {
    if (!token || view !== 'graph') return
    refreshMatters().then((rows) => {
      if (!matterId && rows?.length) setMatterId(rows[0].id)
    })
  }, [token, view, refreshMatters])

  useEffect(() => {
    if (view !== 'graph' || matterId || !matters.length) return
    setMatterId(matters[0].id)
  }, [view, matters, matterId])

  useEffect(() => {
    if (view !== 'graph' || !matterId || !documents.length) return
    const processed = documents.find((d) => (d.ingest_status || d.status) === 'processed' || (d.ingest_status || d.status) === 'ready')
    if (processed && (!docId || !documents.some((d) => d.id === docId && (d.ingest_status || d.status) === 'processed'))) {
      setDocId(processed.id)
    }
  }, [view, matterId, documents, docId])

  useEffect(() => {
    if (!token || !threadId) {
      setChatHistory([])
      return
    }
    api(`/api/v1/threads/${threadId}/messages`)
      .then((msgs) => {
        setChatHistory(msgs.map((m) => ({ role: m.role, content: m.content })))
        const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant')
        if (lastAssistant) {
          setAnswer(lastAssistant.content)
          const src = lastAssistant.sources?.items || lastAssistant.sources || []
          setSources(Array.isArray(src) ? src : [])
        }
      })
      .catch(() => setChatHistory([]))
  }, [threadId, token])

  useEffect(() => {
    if (!matterId || !token) {
      setDocuments([])
      setDeadlines([])
      setLegalHolds([])
      return undefined
    }
    const refreshDocs = () => {
      api(`/api/v1/matters/${matterId}/documents`).then(setDocuments).catch(() => setDocuments([]))
    }
    refreshDocs()
    const docPoll = setInterval(refreshDocs, 2500)
    api(`/api/v1/matters/${matterId}/deadlines`).then(setDeadlines).catch(() => setDeadlines([]))
    if (isAdmin || currentUser?.role === 'matter_lead') {
      api(`/api/v1/matters/${matterId}/legal-holds`).then(setLegalHolds).catch(() => setLegalHolds([]))
    } else {
      setLegalHolds([])
    }
    return () => clearInterval(docPoll)
  }, [matterId, token, isAdmin, currentUser?.role])

  const pollDocStatus = useCallback(async (documentId) => {
    if (!matterId || !documentId) return
    try {
      const st = await api(`/api/v1/matters/${matterId}/documents/${documentId}/status`)
      setDocStatuses((prev) => ({ ...prev, [documentId]: st }))
      if (st.status === 'processed' || st.status === 'failed') {
        const docs = await api(`/api/v1/matters/${matterId}/documents`)
        setDocuments(docs)
      }
    } catch {
      /* ignore */
    }
  }, [matterId])

  const login = async () => {
    setLoginLoading(true)
    setLoginError('')
    try {
      const data = await api('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setSession({ accessToken: data.access_token, refreshToken: data.refresh_token })
      setTokenState(data.access_token)
      if (data.user) setCurrentUser(data.user)
    } catch (e) {
      setLoginError(e.message || 'Login failed')
    } finally {
      setLoginLoading(false)
    }
  }

  const logout = () => {
    clearToken()
    setTokenState('')
    setCurrentUser(null)
  }

  const sendChat = async () => {
    const q = lang === 'de' ? `[DE] ${message}` : message
    setChatBusy(true)
    setAnswer('')
    setSources([])
    const payload = {
      message: q,
      use_law_corpus: useLawCorpus,
      use_hyde: useHyde,
      thread_id: threadId || undefined,
    }
    const useAsync = status?.llm_profile === 'airgap'
    try {
      if (useAsync) {
        const job = await api('/api/v1/chat/async', { method: 'POST', body: JSON.stringify(payload) })
        const result = await pollChatJob(job.job_id, {
          onProgress: (p) => {
            if (p.progress_step) setAnswer(`Working… (${p.progress_step})`)
          },
        })
        setAnswer(result.answer || '')
        setSources(result.sources || [])
        if (result.thread_id) {
          setThreadId(result.thread_id)
          api('/api/v1/threads').then(setThreads).catch(() => {})
        }
        return
      }
      let streamed = ''
      await apiStream('/api/v1/chat/stream', payload, (ev) => {
          if (ev.type === 'token') {
            streamed += ev.content || ''
            setAnswer(streamed)
          }
          if (ev.type === 'sources') setSources(ev.sources || [])
          if (ev.type === 'done' && ev.thread_id) {
            setThreadId(ev.thread_id)
            api('/api/v1/threads').then(setThreads).catch(() => {})
          }
        })
      if (!streamed) {
        const data = await api('/api/v1/chat', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setAnswer(data.answer)
        setSources(data.sources || [])
        if (data.thread_id) {
          setThreadId(data.thread_id)
          api('/api/v1/threads').then(setThreads).catch(() => {})
        }
      }
    } finally {
      setChatBusy(false)
    }
  }

  const createMatter = async () => {
    const m = await api('/api/v1/matters', {
      method: 'POST',
      body: JSON.stringify({ name: `Matter ${new Date().toLocaleDateString()}`, description: 'Workspace matter' }),
    })
    await refreshMatters()
    setMatterId(m.id)
  }

  const deleteMatter = async (id) => {
    if (!window.confirm('Delete this matter and all documents?')) return
    try {
      await api(`/api/v1/matters/${id}`, { method: 'DELETE' })
      await refreshMatters()
      setMatterId('')
      setDocuments([])
      setLegalHolds([])
    } catch {
      /* toast shown by api handler */
    }
  }

  const placeHold = async () => {
    if (!matterId || !holdReason.trim()) return
    await api(`/api/v1/matters/${matterId}/legal-hold`, {
      method: 'POST',
      body: JSON.stringify({ reason: holdReason.trim() }),
    })
    setHoldReason('')
    const holds = await api(`/api/v1/matters/${matterId}/legal-holds`)
    setLegalHolds(holds)
    showToast('Legal hold placed', 'success')
  }

  const releaseHold = async (holdId) => {
    if (!matterId || !window.confirm('Release this legal hold?')) return
    await api(`/api/v1/matters/${matterId}/legal-hold/${holdId}`, { method: 'DELETE' })
    const holds = await api(`/api/v1/matters/${matterId}/legal-holds`)
    setLegalHolds(holds)
    showToast('Legal hold released', 'success')
  }

  const uploadDoc = async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('confidentiality', uploadConfidentiality)
    const doc = await api(`/api/v1/matters/${matterId}/documents`, { method: 'POST', body: fd })
    setDocuments((prev) => {
      const exists = prev.some((d) => d.id === doc.id)
      return exists ? prev.map((d) => (d.id === doc.id ? doc : d)) : [...prev, doc]
    })
    pollDocStatus(doc.id)
  }

  const uploadZip = async (file) => {
    const fd = new FormData()
    fd.append('archive', file)
    setBulkProgress('Uploading zip…')
    const res = await api(`/api/v1/matters/${matterId}/documents/bulk`, { method: 'POST', body: fd })
    setBulkProgress(res?.errors?.length ? `Done with ${res.errors.length} errors` : 'Bulk upload complete')
    await api(`/api/v1/matters/${matterId}/documents`).then(setDocuments)
  }

  const uploadBulkFiles = async (fileList) => {
    const fd = new FormData()
    Array.from(fileList).forEach((f) => fd.append('files', f))
    fd.append('confidentiality', uploadConfidentiality)
    setBulkProgress(`Uploading ${fileList.length} files…`)
    const res = await api(`/api/v1/matters/${matterId}/documents/bulk-files`, { method: 'POST', body: fd })
    setBulkProgress(`Uploaded ${res?.count || 0} files`)
    await api(`/api/v1/matters/${matterId}/documents`).then(setDocuments)
  }

  const addDeadline = async () => {
    if (!matterId || !deadlineTitle.trim() || !deadlineDate) return
    await api(`/api/v1/matters/${matterId}/deadlines`, {
      method: 'POST',
      body: JSON.stringify({ title: deadlineTitle.trim(), due_date: deadlineDate }),
    })
    setDeadlineTitle('')
    setDeadlineDate('')
    const rows = await api(`/api/v1/matters/${matterId}/deadlines`)
    setDeadlines(rows)
  }

  const toggleDeadline = async (id, status) => {
    await api(`/api/v1/matters/${matterId}/deadlines/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    const rows = await api(`/api/v1/matters/${matterId}/deadlines`)
    setDeadlines(rows)
  }

  const runAnalyze = async () => {
    setAnalyzeBusy(true)
    try {
      setAnalyzeResult(await api(`/api/v1/matters/${matterId}/analyze`, {
        method: 'POST',
        body: JSON.stringify({ document_id: docId, question: analyzeQ }),
      }))
    } finally {
      setAnalyzeBusy(false)
    }
  }

  const runCompare = async () => {
    setCompareBusy(true)
    try {
      setCompareResult(await api(`/api/v1/matters/${matterId}/compare`, {
        method: 'POST',
        body: JSON.stringify({ document_id: docId, question: analyzeQ }),
      }))
    } finally {
      setCompareBusy(false)
    }
  }

  const runCompareClause = async (clauseId) => {
    const cid = clauseId || selectedClauseId
    if (!matterId || !docId || !cid) return
    setCompareClauseBusy(true)
    try {
      setCompareClauseResult(await api(`/api/v1/matters/${matterId}/compare-clause`, {
        method: 'POST',
        body: JSON.stringify({ document_id: docId, clause_library_id: cid }),
      }))
    } finally {
      setCompareClauseBusy(false)
    }
  }

  const openEditor = async () => {
    if (!matterId || !docId) return
    const ws = await api(`/api/v1/matters/${matterId}/documents/${docId}/workspace`)
    setWorkspace(ws)
    setEditorOpen(true)
  }

  const saveWorkspace = async (contentText, expectedVersion) => {
    setWorkspaceSaving(true)
    try {
      const ws = await api(`/api/v1/matters/${matterId}/documents/${docId}/workspace`, {
        method: 'PUT',
        body: JSON.stringify({ content_text: contentText, expected_version_number: expectedVersion }),
      })
      setWorkspace(ws)
      showToast(`Saved version ${ws.version_number}`, 'success')
    } finally {
      setWorkspaceSaving(false)
    }
  }

  const exportDocx = async () => {
    const blob = await api(`/api/v1/matters/${matterId}/documents/${docId}/export/docx`)
    const name = (documents.find((d) => d.id === docId)?.filename || 'contract').replace(/\.[^.]+$/, '') + '_export.docx'
    downloadBlob(blob, name)
  }

  const addAnnotation = async (clauseId, comment) => {
    await api(`/api/v1/matters/${matterId}/documents/${docId}/annotations`, {
      method: 'POST',
      body: JSON.stringify({ clause_id: clauseId, comment }),
    })
    showToast('Annotation added', 'success')
  }

  const runGapAnalysis = async () => {
    setGapBusy(true)
    setGapReport(null)
    setGapStep('queued')
    try {
      const { job_id: jobId } = await api(`/api/v1/matters/${matterId}/workflows/gap-analysis`, {
        method: 'POST',
        body: JSON.stringify({ document_id: docId, baseline: 'gdpr' }),
      })
      for (let i = 0; i < 90; i += 1) {
        await new Promise((r) => setTimeout(r, 2000))
        const st = await api(`/api/v1/workflows/gap-analysis/${jobId}`)
        setGapStep(st.progress_step || st.status)
        if (st.status === 'completed') {
          setGapReport(st.report)
          showToast('Gap analysis complete', 'success')
          return
        }
        if (st.status === 'failed') throw new Error(st.error || 'Gap analysis failed')
      }
      throw new Error('Gap analysis timed out')
    } catch (e) {
      showToast(e.message || 'Gap analysis failed')
    } finally {
      setGapBusy(false)
      setGapStep('')
    }
  }

  const loadGraph = async () => {
    if (!matterId || !docId) return
    setGraphLoading(true)
    setGraphLoadError('')
    try {
      const [ent, edges] = await Promise.all([
        api(`/api/v1/matters/${matterId}/documents/${docId}/graph-entities`),
        api(`/api/v1/matters/${matterId}/documents/${docId}/graph-edges`),
      ])
      setGraph({ nodes: ent.entities || [], edges: edges.edges || [] })
      if (!(ent.entities || []).length && !(edges.edges || []).length) {
        setGraphLoadError('Graph is empty — click Extract graph to run extraction on this document.')
      }
    } catch (e) {
      setGraphLoadError(e.message || 'Failed to load graph')
      setGraph({ nodes: [], edges: [] })
    } finally {
      setGraphLoading(false)
    }
  }

  const extractGraph = async () => {
    if (!matterId || !docId) return
    setGraphExtractLoading(true)
    setGraphLoadError('')
    try {
      const res = await api(`/api/v1/matters/${matterId}/documents/${docId}/graph-extract`, { method: 'POST' })
      showToast(`Graph extracted: ${res.nodes} entities, ${res.edges} relationships`, 'success')
      await loadGraph()
    } catch (e) {
      setGraphLoadError(e.message || 'Graph extraction failed')
    } finally {
      setGraphExtractLoading(false)
    }
  }

  const downloadBlob = (blob, name) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  }

  const exportPdf = () => {
    if (!answer?.trim()) {
      showToast('Run a research query before exporting.', 'error')
      return
    }
    setExportModalOpen(true)
  }

  const confirmExportPdf = async (meta) => {
    setExportModalOpen(false)
    try {
      const selectedMatter = matters.find((m) => m.id === matterId)
      const selectedDoc = documents.find((d) => d.id === docId)
      const blob = await api('/api/v1/export/audit', {
        method: 'POST',
        body: JSON.stringify({
          format: 'pdf',
          question: message,
          answer,
          sources,
          thread_id: threadId || undefined,
          matter_id: matterId || undefined,
          matter_name: meta.matterName,
          document_name: meta.documentName,
          prepared_for: meta.preparedFor,
          matter_reference: meta.matterReference,
          author_name: meta.authorName,
          firm_name: meta.firmName,
          filename: selectedDoc?.filename,
        }),
      })
      const ref = (meta.matterReference || 'export').replace(/[^\w.-]+/g, '_')
      downloadBlob(blob, `jurisguard-${ref}.pdf`)
      showToast('PDF exported', 'success')
    } catch {
      /* toast from api handler */
    }
  }

  const exportMd = async () => {
    try {
      const blob = await api('/api/v1/export/audit', {
        method: 'POST',
        body: JSON.stringify({ format: 'markdown', question: message, answer, sources, thread_id: threadId || undefined }),
      })
      downloadBlob(blob, 'jurisguard-audit.md')
      showToast('Markdown exported', 'success')
    } catch {
      /* toast from api handler */
    }
  }

  const exportAnalyze = async () => {
    const doc = documents.find((d) => d.id === docId)
    const blob = await api('/api/v1/export/analyze-report', {
      method: 'POST',
      body: JSON.stringify({
        format: 'markdown',
        matter_id: matterId,
        document_id: docId,
        question: analyzeQ,
        answer: analyzeResult?.answer,
        structured: analyzeResult?.structured,
        risk: analyzeResult?.risk,
        filename: doc?.filename,
      }),
    })
    downloadBlob(blob, 'analyze-report.md')
  }

  const exportCompare = async () => {
    const blob = await api('/api/v1/export/compare-report', {
      method: 'POST',
      body: JSON.stringify({ format: 'markdown', matter_id: matterId, document_id: docId, question: analyzeQ }),
    })
    downloadBlob(blob, 'compare-report.md')
  }

  const submitFeedback = (rating) =>
    api('/api/v1/feedback', {
      method: 'POST',
      body: JSON.stringify({ rating, question: message, answer, thread_id: threadId || undefined }),
    }).then(() => showToast('Feedback recorded', 'success'))

  const runEval = async () => {
    const res = await api('/api/v1/admin/run-eval', { method: 'POST' })
    showToast(res.message || 'Eval started', 'success')
    setEvalStatus({ running: true })
  }

  const viewTitle = {
    research: 'Research',
    matters: 'Matters',
    corpus: 'Corpus',
    clauses: 'Clause bank',
    graph: 'Graph',
    audit: 'Audit',
    admin: 'Admin',
    help: 'Help',
    system: 'System',
  }[view] || view

  if (isAuthCallback) {
    return (
      <AuthCallback
        onComplete={(t) => {
          if (t) {
            setToken(t)
            setTokenState(t)
          }
        }}
      />
    )
  }

  if (!token) {
    return (
      <>
        <LoginPage
          email={email}
          setEmail={setEmail}
          password={password}
          setPassword={setPassword}
          onLogin={login}
          error={loginError}
          loading={loginLoading}
          ssoStatus={ssoStatus}
          branding={branding}
        />
        {toast && <Toast {...toast} onClose={() => setToast(null)} />}
      </>
    )
  }

  return (
    <div className="app-shell">
      <Sidebar
        active={view}
        onNavigate={setView}
        profile={status?.llm_profile}
        model={status?.model_tiers?.generation?.model}
        isAdmin={isAdmin}
        mobileOpen={mobileNav}
        onToggleMobile={() => setMobileNav((v) => !v)}
        onCloseMobile={() => setMobileNav(false)}
        branding={branding}
      />
      <div className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <h1>{viewTitle}</h1>
            {currentUser && <small className="muted">{currentUser.email} · {currentUser.role}</small>}
          </div>
          <div className="topbar-right">
            <select className="select-compact" value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Query language">
              <option value="en">EN</option>
              <option value="de">DE</option>
            </select>
            <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>Sign out</button>
          </div>
        </header>
        <main className="content">
          {view === 'research' && (
            <ChatView
              message={message}
              setMessage={setMessage}
              answer={answer}
              sources={sources}
              busy={chatBusy}
              lang={lang}
              threads={threads}
              threadId={threadId}
              setThreadId={setThreadId}
              onSend={sendChat}
              onFeedback={submitFeedback}
              onExport={exportPdf}
              onExportMd={exportMd}
              lowConfidence={lowConfidence}
              useHyde={useHyde}
              setUseHyde={setUseHyde}
              useLawCorpus={useLawCorpus}
              setUseLawCorpus={setUseLawCorpus}
              chatHistory={threadId ? chatHistory.slice(0, -2) : []}
              brandName={branding?.brand_name}
            />
          )}
          {view === 'matters' && (
            <MattersView
              matters={matters}
              matterId={matterId}
              setMatterId={setMatterId}
              documents={documents}
              docId={docId}
              setDocId={setDocId}
              onCreateMatter={createMatter}
              onDeleteMatter={deleteMatter}
              onUpload={uploadDoc}
              onBulkUpload={uploadZip}
              onBulkFiles={uploadBulkFiles}
              analyzeQ={analyzeQ}
              setAnalyzeQ={setAnalyzeQ}
              analyzeResult={analyzeResult}
              compareResult={compareResult}
              analyzeBusy={analyzeBusy}
              compareBusy={compareBusy}
              onAnalyze={runAnalyze}
              onCompare={runCompare}
              onGapAnalysis={runGapAnalysis}
              gapBusy={gapBusy}
              gapStep={gapStep}
              gapReport={gapReport}
              onExportAnalyze={exportAnalyze}
              onExportCompare={exportCompare}
              userRole={currentUser?.role}
              legalHolds={legalHolds}
              onPlaceHold={placeHold}
              onReleaseHold={releaseHold}
              holdReason={holdReason}
              setHoldReason={setHoldReason}
              docStatuses={docStatuses}
              pollDocStatus={pollDocStatus}
              uploadConfidentiality={uploadConfidentiality}
              setUploadConfidentiality={setUploadConfidentiality}
              bulkProgress={bulkProgress}
              onOpenEditor={openEditor}
              clauseItems={clauseItems}
              selectedClauseId={selectedClauseId}
              setSelectedClauseId={setSelectedClauseId}
              onCompareClause={runCompareClause}
              compareClauseBusy={compareClauseBusy}
              compareClauseResult={compareClauseResult}
              deadlines={deadlines}
              deadlineTitle={deadlineTitle}
              setDeadlineTitle={setDeadlineTitle}
              deadlineDate={deadlineDate}
              setDeadlineDate={setDeadlineDate}
              onAddDeadline={addDeadline}
              onToggleDeadline={toggleDeadline}
            />
          )}
          <ContractEditor
            open={editorOpen}
            onClose={() => setEditorOpen(false)}
            filename={documents.find((d) => d.id === docId)?.filename}
            workspace={workspace}
            onSave={saveWorkspace}
            onExportDocx={exportDocx}
            onAddAnnotation={addAnnotation}
            saving={workspaceSaving}
            readOnly={workspace?.read_only}
          />
          {view === 'graph' && (
            <GraphView
              matters={matters}
              matterId={matterId}
              setMatterId={setMatterId}
              documents={documents}
              docId={docId}
              setDocId={setDocId}
              graph={graph}
              onLoad={loadGraph}
              onExtract={extractGraph}
              loading={graphLoading}
              extractLoading={graphExtractLoading}
              loadError={graphLoadError}
            />
          )}
          {view === 'corpus' && (isAdmin ? <CorpusView stats={corpusStats} loading={corpusStats === null} isAdmin={isAdmin} /> : (
            <div className="card alert alert-warn">Corpus admin view requires org_admin or owner role.</div>
          ))}
          {view === 'clauses' && (
            <ClauseLibraryView
              matterId={matterId}
              docId={docId}
              onCompareClause={runCompareClause}
              compareClauseBusy={compareClauseBusy}
              compareClauseResult={compareClauseResult}
            />
          )}
          {view === 'audit' && <AuditView isAdmin={isAdmin} />}
          {view === 'admin' && (isAdmin ? <AdminView currentUser={currentUser} /> : (
            <div className="card alert alert-warn">Admin view requires org_admin or owner role.</div>
          ))}
          {view === 'help' && <HelpView />}
          {view === 'system' && (
            <SystemView status={status} currentUser={currentUser} evalStatus={evalStatus} onRunEval={runEval} />
          )}
        </main>
      </div>
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
      <ExportModal
        open={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onConfirm={confirmExportPdf}
        defaults={{
          preparedFor: '',
          matterName: matters.find((m) => m.id === matterId)?.name || '',
          matterReference: matterId ? `MAT-${String(matterId).slice(0, 8).toUpperCase()}` : '',
          documentName: documents.find((d) => d.id === docId)?.filename || 'Law corpus research',
          authorName: currentUser?.email?.split('@')[0]?.replace(/[._]/g, ' ') || '',
          firmName: branding?.brand_name || 'JurisGuard',
        }}
      />
    </div>
  )
}

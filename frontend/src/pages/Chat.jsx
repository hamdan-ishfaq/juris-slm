import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader, Menu, FileText, Plus, Trash2, ChevronDown, ChevronUp, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import { queryAPI } from '../lib/api';
import Sidebar from '../components/Sidebar';

const ROLE = (localStorage.getItem('user_role') || 'user').toLowerCase();
const IS_PRIVILEGED = ROLE === 'admin' || ROLE === 'owner';

const CLEARANCE_META = {
  owner: { label: 'Level 1 · 2 · 3', color: 'text-gold',    bg: 'bg-gold/10    border-gold/20'    },
  admin: { label: 'Level 1 · 2',     color: 'text-info',    bg: 'bg-info/10    border-info/20'    },
  user:  { label: 'Level 1',         color: 'text-ink-muted', bg: 'bg-elevated  border-stroke'    },
};

const ACCESS_META = {
  level_1: { label: 'L1', color: 'text-success', bg: 'bg-success/10 border-success/20' },
  level_2: { label: 'L2', color: 'text-warning',  bg: 'bg-warning/10  border-warning/20'  },
  level_3: { label: 'L3', color: 'text-danger',   bg: 'bg-danger/10   border-danger/20'   },
};

function MessageSkeleton() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
      <div className="bg-surface border border-stroke rounded-sm px-4 py-3 w-56 h-14 space-y-2">
        <div className="h-2 bg-elevated rounded w-full animate-pulse" />
        <div className="h-2 bg-elevated rounded w-4/5 animate-pulse" />
      </div>
    </motion.div>
  );
}

function ClearanceBadge() {
  const meta = CLEARANCE_META[ROLE] || CLEARANCE_META.user;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-mono border ${meta.bg} ${meta.color}`}>
      <Shield className="w-3 h-3" />
      {meta.label}
    </span>
  );
}

function AuditTrace({ sources }) {
  const [open, setOpen] = useState(false);
  if (!IS_PRIVILEGED || !sources?.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs font-mono text-ink-faint hover:text-ink-muted transition-colors"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        Audit trace · {sources.length} chunk{sources.length > 1 ? 's' : ''} retrieved
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 border border-stroke rounded-sm overflow-hidden">
              <div className="grid grid-cols-[1fr_48px_60px_60px] px-3 py-2 bg-elevated border-b border-stroke text-xs font-mono text-ink-faint uppercase tracking-widest">
                <span>Source</span>
                <span>Level</span>
                <span>Score</span>
                <span>Rank</span>
              </div>
              {sources.slice(0, 8).map((src, i) => {
                const al   = (src.access_level || 'level_1').toLowerCase();
                const meta = ACCESS_META[al] || ACCESS_META.level_1;
                const score = src.relevance ?? src.score ?? src.rerank_score ?? null;
                const rank  = src.pre_rerank_rank ?? i;
                return (
                  <div key={i} className="grid grid-cols-[1fr_48px_60px_60px] px-3 py-2 border-b border-stroke last:border-0 items-center gap-2">
                    <div className="min-w-0">
                      <p className="text-xs text-ink truncate font-mono">
                        {src.source || src.doc_id || `chunk_${i}`}
                      </p>
                      {src.text && (
                        <p className="text-xs text-ink-faint truncate mt-0.5">
                          {src.text.substring(0, 80)}…
                        </p>
                      )}
                    </div>
                    <span className={`inline-flex items-center justify-center px-1.5 py-0.5 rounded-sm text-xs font-mono border ${meta.bg} ${meta.color}`}>
                      {meta.label}
                    </span>
                    <span className="text-xs font-mono text-ink-muted">
                      {score !== null ? `${(score * 100).toFixed(0)}%` : '—'}
                    </span>
                    <span className="text-xs font-mono text-ink-faint">
                      #{rank + 1}
                    </span>
                  </div>
                );
              })}
              {sources.length > 8 && (
                <div className="px-3 py-2 text-xs text-ink-faint font-mono">
                  +{sources.length - 8} more chunks
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Chat() {
  const [messages,      setMessages]      = useState([
    { id: 1, type: 'assistant', text: 'Welcome to BEWEIS. Ask about legal documents, regulations, or any contractual questions.' }
  ]);
  const [input,         setInput]         = useState('');
  const [loading,       setLoading]       = useState(false);
  const [loadingHistory,setLoadingHistory] = useState(true);
  const [sidebarOpen,   setSidebarOpen]   = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  useEffect(() => {
    const load = async () => {
      setLoadingHistory(true);
      try {
        const res  = await queryAPI.getChatHistory(50);
        const msgs = res.data.messages || [];
        if (msgs.length > 0) {
          setMessages(msgs.map((m, i) => ({
            id:        i + 1,
            type:      m.role === 'assistant' ? 'assistant' : 'user',
            text:      m.content,
            timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString() : undefined,
          })));
        }
      } catch {
        toast.error('Failed to load chat history', { duration: 3000 });
      } finally {
        setLoadingHistory(false);
      }
    };
    load();
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleClearChat = async () => {
    if (!window.confirm('Clear entire chat history? This cannot be undone.')) return;
    try {
      setLoading(true);
      await queryAPI.clearChatHistory();
      setMessages([{ id: 1, type: 'assistant', text: 'Welcome to BEWEIS. Ask about legal documents, regulations, or any contractual questions.' }]);
      toast.success('History cleared', { duration: 1500 });
    } catch {
      toast.error('Failed to clear history');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    const userMsg = { id: messages.length + 1, type: 'user', text: input };
    setMessages(p => [...p, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const res    = await queryAPI.query(input);
      const answer = res.data.answer  || 'No response received';
      const sources = res.data.sources || [];
      setMessages(p => [...p, {
        id: p.length + 1, type: 'assistant',
        text: answer, sources,
        timestamp: new Date().toLocaleTimeString(),
      }]);
    } catch (err) {
      let text = 'An error occurred';
      if (err.response?.status === 429)    text = 'Rate limited — please wait a moment.';
      else if (err.response?.status === 401) text = 'Session expired. Please log in again.';
      else if (err.response?.data?.detail)   text = err.response.data.detail;
      else if (err.message)                  text = err.message;
      setMessages(p => [...p, { id: p.length + 1, type: 'assistant', isError: true, text: `Error: ${text}` }]);
      toast.error(text, { duration: 4000 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[100dvh] bg-base">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col h-[100dvh] overflow-hidden">

        {/* Header */}
        <div className="border-b border-stroke bg-surface flex-shrink-0">
          <div className="max-w-4xl mx-auto px-4 md:px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                className="md:hidden p-1.5 text-ink-faint hover:text-ink hover:bg-elevated rounded-sm transition-colors"
              >
                <Menu className="w-4 h-4" />
              </button>
              <div>
                <h1 className="text-sm font-medium text-ink tracking-wide">Legal Analysis</h1>
                <p className="text-xs text-ink-faint hidden md:block">Ask questions about your legal documents</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ClearanceBadge />
              <button
                onClick={handleClearChat}
                disabled={loading}
                title="Clear history"
                className="p-1.5 text-ink-faint hover:text-danger hover:bg-danger-dim rounded-sm transition-all duration-150 disabled:opacity-40"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => {
                  setMessages([{ id: 1, type: 'assistant', text: 'Welcome to BEWEIS. Ask about legal documents, regulations, or any contractual questions.' }]);
                  toast.success('New conversation', { duration: 1500 });
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-ink-muted bg-elevated border border-stroke rounded-sm hover:border-stroke-strong hover:text-ink transition-all duration-150"
              >
                <Plus className="w-3 h-3" />
                <span className="hidden md:inline">New Chat</span>
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-4 md:px-6 py-5 space-y-4">

            {loadingHistory && <><MessageSkeleton /><MessageSkeleton /></>}

            {messages.map(msg => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
                className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className="max-w-[85%] md:max-w-[72%]">
                  <div className={`
                    rounded-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words
                    ${msg.type === 'user'
                      ? 'bg-elevated border border-stroke text-ink'
                      : msg.isError
                      ? 'bg-danger-dim border border-danger/30 text-danger'
                      : 'bg-surface border border-stroke text-ink'
                    }
                  `}>
                    {msg.text}
                  </div>

                  {/* Clearance indicator — assistant messages only */}
                  {msg.type === 'assistant' && !msg.isError && (
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <span className="text-xs text-ink-faint font-mono">
                        Filtered to your clearance
                      </span>
                      <ClearanceBadge />
                    </div>
                  )}

                  {/* Sources panel */}
                  {msg.type === 'assistant' && msg.sources?.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs text-ink-faint font-mono uppercase tracking-widest">Sources</p>
                      {msg.sources.slice(0, 5).map((src, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2.5 px-3 py-2.5 bg-elevated border border-stroke rounded-sm"
                          style={{ borderLeft: '2px solid #c9a452' }}
                        >
                          <FileText className="w-3.5 h-3.5 text-gold flex-shrink-0 mt-0.5" />
                          <div className="text-xs min-w-0 flex-1">
                            {typeof src === 'string' ? (
                              <p className="text-ink-muted">{src.substring(0, 200)}…</p>
                            ) : (
                              <>
                                {src.text   && <p className="text-ink-muted">{src.text.substring(0, 200)}…</p>}
                                {src.source && <p className="text-ink-faint mt-1 font-mono truncate">{src.source}</p>}
                                <div className="flex items-center gap-2 mt-1">
                                  {src.relevance != null && (
                                    <span className="text-ink-faint font-mono">{(src.relevance * 100).toFixed(0)}% match</span>
                                  )}
                                  {src.access_level && (() => {
                                    const al = (src.access_level || 'level_1').toLowerCase();
                                    const m  = ACCESS_META[al] || ACCESS_META.level_1;
                                    return (
                                      <span className={`px-1.5 py-0.5 rounded-sm text-xs font-mono border ${m.bg} ${m.color}`}>
                                        {m.label}
                                      </span>
                                    );
                                  })()}
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                      {msg.sources.length > 5 && (
                        <p className="text-xs text-ink-faint font-mono">+{msg.sources.length - 5} more</p>
                      )}
                    </div>
                  )}

                  {/* Audit trace — admin/owner only */}
                  {msg.type === 'assistant' && !msg.isError && (
                    <AuditTrace sources={msg.sources} />
                  )}
                </div>
              </motion.div>
            ))}

            {loading && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
                <div className="bg-surface border border-stroke rounded-sm px-4 py-3 flex items-center gap-2">
                  <Loader className="w-3.5 h-3.5 animate-spin text-gold" />
                  <span className="text-xs text-ink-muted font-mono">Analyzing…</span>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-stroke bg-surface flex-shrink-0">
          <div className="max-w-4xl mx-auto px-4 md:px-6 py-3">
            <form onSubmit={handleSend} className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Ask a legal question…"
                disabled={loading}
                className="flex-1 px-3 py-2 bg-base border border-stroke rounded-sm text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-stroke-focus focus:ring-1 focus:ring-gold/20 transition-all duration-150 font-sans disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-4 py-2 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Send</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
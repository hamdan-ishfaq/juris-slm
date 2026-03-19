import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Menu, ChevronDown, ChevronUp, Play, CheckCircle, XCircle, Activity, Terminal } from 'lucide-react';
import toast from 'react-hot-toast';
import { evalAPI } from '../lib/api';
import Sidebar from '../components/Sidebar';

// ─── API Explorer data ────────────────────────────────────────────────────────
const ENDPOINTS = [
  {
    group: 'Auth',
    items: [
      { method: 'POST', path: '/auth/register', auth: 'None',  role: 'None',  limit: null,      desc: 'Register a new user' },
      { method: 'POST', path: '/auth/login',    auth: 'None',  role: 'None',  limit: '5/min',   desc: 'Login and receive JWT token' },
      { method: 'GET',  path: '/auth/me',       auth: 'Bearer',role: 'Any',   limit: null,      desc: 'Get current user profile' },
    ]
  },
  {
    group: 'Chat',
    items: [
      { method: 'POST',   path: '/chat/query',   auth: 'Bearer', role: 'Any',   limit: '10/min',  desc: 'Execute RAG query with RBAC filtering' },
      { method: 'GET',    path: '/chat/history', auth: 'Bearer', role: 'Any',   limit: null,      desc: 'Get chat history for current user' },
      { method: 'DELETE', path: '/chat/history', auth: 'Bearer', role: 'Any',   limit: null,      desc: 'Clear all chat history' },
      { method: 'GET',    path: '/chat/trace',   auth: 'Bearer', role: 'Any',   limit: null,      desc: 'Last flight recorder trace' },
    ]
  },
  {
    group: 'Documents',
    items: [
      { method: 'POST', path: '/documents/upload',          auth: 'Bearer', role: 'Any*',  limit: '5/hr',  desc: 'Upload PDF (*level_2/3 requires admin+)' },
      { method: 'GET',  path: '/documents/metadata',        auth: 'Bearer', role: 'Any',   limit: null,     desc: 'List indexed chunks (RBAC filtered)' },
      { method: 'GET',  path: '/documents/semantic-search', auth: 'Bearer', role: 'Any',   limit: null,     desc: 'Semantic search over chunks (RBAC filtered)' },
    ]
  },
  {
    group: 'Admin',
    items: [
      { method: 'GET',    path: '/admin/users',                  auth: 'Bearer', role: 'Owner', limit: null, desc: 'List all users' },
      { method: 'PUT',    path: '/admin/users/{id}/role',        auth: 'Bearer', role: 'Owner', limit: null, desc: 'Update user role' },
      { method: 'DELETE', path: '/admin/users/{id}',             auth: 'Bearer', role: 'Owner', limit: null, desc: 'Delete a user' },
    ]
  },
  {
    group: 'Debug',
    items: [
      { method: 'GET',  path: '/health',            auth: 'None',   role: 'None',  limit: null, desc: 'System health check' },
      { method: 'GET',  path: '/debug/metadata',    auth: 'Bearer', role: 'Owner', limit: null, desc: 'Raw FAISS metadata dump' },
      { method: 'GET',  path: '/debug/semantic',    auth: 'Bearer', role: 'Owner', limit: null, desc: 'Debug semantic similarity' },
      { method: 'GET',  path: '/debug/trace',       auth: 'Bearer', role: 'Owner', limit: null, desc: 'Debug layered trace path' },
      { method: 'GET',  path: '/debug/last',        auth: 'Bearer', role: 'Owner', limit: null, desc: 'Last chat router trace' },
      { method: 'POST', path: '/evaluate',          auth: 'Bearer', role: 'Owner', limit: null, desc: 'Run full evaluation suite' },
      { method: 'GET',  path: '/debug/evaluation',  auth: 'Bearer', role: 'Owner', limit: null, desc: 'Last evaluation results' },
    ]
  },
];

const METHOD_STYLE = {
  GET:    'text-info    bg-info/10    border-info/20',
  POST:   'text-success bg-success/10 border-success/20',
  PUT:    'text-warning  bg-warning/10  border-warning/20',
  DELETE: 'text-danger  bg-danger/10  border-danger/20',
};

// ─── Sub-components ───────────────────────────────────────────────────────────
function EndpointCard({ item }) {
  const [open,     setOpen]     = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [response, setResponse] = useState(null);

  const fire = async () => {
    setLoading(true);
    setResponse(null);
    const token = localStorage.getItem('access_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
      const method = item.method === 'DELETE' ? 'DELETE' : item.method;
      const body   = item.method === 'POST' && item.path !== '/auth/login' && item.path !== '/auth/register'
        ? undefined : undefined;
      const res = await fetch(item.path, { method, headers, body });
      const data = await res.json().catch(() => ({ status: res.status }));
      setResponse({ status: res.status, ok: res.ok, data });
    } catch (e) {
      setResponse({ status: 0, ok: false, data: { error: e.message } });
    } finally {
      setLoading(false);
      setOpen(true);
    }
  };

  return (
    <div className="border border-stroke rounded-sm overflow-hidden bg-surface">
      <div className="flex items-center gap-3 px-4 py-3">
        <span className={`flex-shrink-0 px-2 py-0.5 rounded-sm text-xs font-mono font-medium border ${METHOD_STYLE[item.method] || METHOD_STYLE.GET}`}>
          {item.method}
        </span>
        <span className="text-xs font-mono text-ink flex-1 truncate">{item.path}</span>
        {item.limit && (
          <span className="text-xs font-mono text-warning bg-warning/10 border border-warning/20 px-1.5 py-0.5 rounded-sm flex-shrink-0">
            {item.limit}
          </span>
        )}
        <span className={`text-xs font-mono flex-shrink-0 ${item.role === 'Owner' ? 'text-gold' : 'text-ink-faint'}`}>
          {item.role}
        </span>
        <button
          onClick={fire}
          disabled={loading}
          className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1 bg-elevated border border-stroke rounded-sm text-xs font-mono text-ink-muted hover:text-ink hover:border-stroke-strong transition-all disabled:opacity-40"
        >
          {loading
            ? <span className="animate-pulse">…</span>
            : <><Play className="w-3 h-3" /> Test</>
          }
        </button>
        <button onClick={() => setOpen(o => !o)} className="text-ink-faint hover:text-ink transition-colors">
          {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>
      <div className="px-4 pb-2 text-xs text-ink-faint">{item.desc}</div>

      <AnimatePresence>
        {open && response && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-stroke"
          >
            <div className="px-4 py-3 bg-base">
              <div className="flex items-center gap-2 mb-2">
                {response.ok
                  ? <CheckCircle className="w-3.5 h-3.5 text-success" />
                  : <XCircle    className="w-3.5 h-3.5 text-danger"  />
                }
                <span className={`text-xs font-mono ${response.ok ? 'text-success' : 'text-danger'}`}>
                  {response.status} {response.ok ? 'OK' : 'Error'}
                </span>
              </div>
              <pre className="text-xs font-mono text-ink-muted overflow-x-auto max-h-48 whitespace-pre-wrap break-all">
                {JSON.stringify(response.data, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function EvalResultRow({ result }) {
  const [open, setOpen] = useState(false);
  const pass = result.status === 'PASS';

  return (
    <div className="border-b border-stroke last:border-0">
      <div
        className="grid grid-cols-[32px_80px_1fr_80px_80px_80px] gap-2 px-4 py-3 items-center cursor-pointer hover:bg-elevated transition-colors text-xs font-mono"
        onClick={() => setOpen(o => !o)}
      >
        <span className="text-ink-faint">{result.id}</span>
        <span className="text-ink-muted truncate">{result.category}</span>
        <span className="text-ink truncate" title={result.question}>{result.question?.substring(0, 45)}…</span>
        <span className={result.guest_ok ? 'text-success' : 'text-danger'}>
          {result.guest_ok ? 'Denied ✓' : 'Leaked ✗'}
        </span>
        <span className="text-info">{result.admin_response?.substring(0, 20)}…</span>
        <span className={`flex items-center gap-1 ${pass ? 'text-success' : 'text-danger'}`}>
          {pass ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {result.status}
        </span>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 grid grid-cols-2 gap-4 text-xs bg-elevated border-t border-stroke">
              <div className="pt-3">
                <p className="text-ink-faint font-mono uppercase tracking-widest mb-1">Guest Response</p>
                <p className="text-ink-muted leading-relaxed">{result.guest_response}</p>
              </div>
              <div className="pt-3">
                <p className="text-ink-faint font-mono uppercase tracking-widest mb-1">Admin Response</p>
                <p className="text-ink-muted leading-relaxed">{result.admin_response}</p>
              </div>
              {result.description && (
                <div className="col-span-2 pt-1">
                  <p className="text-ink-faint font-mono uppercase tracking-widest mb-1">Test Description</p>
                  <p className="text-ink-muted">{result.description}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function Diagnostics() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab,   setActiveTab]   = useState('health');

  // Health state
  const [health,        setHealth]        = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Eval state
  const [results,  setResults]  = useState([]);
  const [evalLoading, setEvalLoading] = useState(false);
  const [stats,    setStats]    = useState({ test_count: 0, passed: 0, failed: 0 });
  const [error,    setError]    = useState('');

  // Auto-load health on mount
  useEffect(() => {
    if (activeTab === 'health') fetchHealth();
  }, [activeTab]);

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const res  = await fetch('/health');
      const data = await res.json();
      setHealth(data);
    } catch {
      setHealth({ error: 'Health endpoint unreachable' });
    } finally {
      setHealthLoading(false);
    }
  };

  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const pollResults = useCallback(async () => {
    try {
      const res  = await evalAPI.getEvaluation();
      const data = res.data;
      if (data.status === 'completed') {
        stopPolling();
        setResults(data.results || []);
        setStats({ test_count: data.test_count, passed: data.passed, failed: data.failed });
        setEvalLoading(false);
        toast.success(`${data.passed}/${data.test_count} tests passed`);
      } else if (data.status === 'error') {
        stopPolling();
        setError(data.detail || 'Evaluation failed');
        setEvalLoading(false);
      }
    } catch { /* keep polling */ }
  }, []);

  const runEvaluation = async () => {
    setEvalLoading(true); setError(''); setResults([]);
    try {
      await evalAPI.startEvaluation();
      // Start polling every 5 seconds
      pollRef.current = setInterval(pollResults, 5000);
      // First poll immediately after 2s
      setTimeout(pollResults, 2000);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Evaluation failed';
      setError(msg);
      setEvalLoading(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => () => stopPolling(), []);

  const TABS = [
    { id: 'health',  label: 'System Status', icon: Activity  },
    { id: 'eval',    label: 'Evaluation',    icon: Zap       },
    { id: 'api',     label: 'API Explorer',  icon: Terminal  },
  ];

  return (
    <div className="flex h-[100dvh] bg-base">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="border-b border-stroke bg-surface flex-shrink-0">
          <div className="max-w-6xl mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
            <button onClick={() => setSidebarOpen(true)} className="md:hidden p-1.5 text-ink-faint hover:text-ink hover:bg-elevated rounded-sm transition-colors">
              <Menu className="w-4 h-4" />
            </button>
            <Zap className="w-4 h-4 text-gold" />
            <div>
              <h1 className="text-sm font-medium text-ink tracking-wide">System Diagnostics</h1>
              <p className="text-xs text-ink-faint hidden md:block">Owner dashboard — health, evaluation, API explorer</p>
            </div>
          </div>
          {/* Tabs */}
          <div className="max-w-6xl mx-auto px-4 md:px-6 flex gap-1 pb-0">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-mono border-b-2 transition-all ${
                  activeTab === id
                    ? 'border-gold text-gold'
                    : 'border-transparent text-ink-faint hover:text-ink'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto px-4 md:px-6 py-6">

            {/* ── System Status ── */}
            {activeTab === 'health' && (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <button
                    onClick={fetchHealth}
                    disabled={healthLoading}
                    className="px-4 py-2 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 disabled:opacity-40 transition-all"
                  >
                    {healthLoading ? 'Checking…' : 'Refresh'}
                  </button>
                </div>

                {health && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {[
                      { label: 'API Status',    value: health.status      || '—', ok: health.status === 'ok' },
                      { label: 'Models Loaded', value: health.models_loaded ? 'Yes' : 'No', ok: health.models_loaded },
                      { label: 'Cache',         value: health.cache        || '—', ok: health.cache === 'connected' },
                      { label: 'Rate Limiting', value: health.rate_limiting ? 'Enabled' : 'Disabled', ok: health.rate_limiting },
                    ].map(({ label, value, ok }) => (
                      <div key={label} className="bg-surface border border-stroke rounded-sm p-4 flex items-center justify-between">
                        <div>
                          <p className="text-xs text-ink-faint font-mono uppercase tracking-widest">{label}</p>
                          <p className={`text-sm font-mono font-medium mt-1 ${ok ? 'text-success' : 'text-danger'}`}>{String(value)}</p>
                        </div>
                        {ok
                          ? <CheckCircle className="w-5 h-5 text-success" />
                          : <XCircle    className="w-5 h-5 text-danger"  />
                        }
                      </div>
                    ))}

                    {health.timestamp && (
                      <div className="md:col-span-2 bg-surface border border-stroke rounded-sm p-4">
                        <p className="text-xs text-ink-faint font-mono uppercase tracking-widest mb-1">Last Checked</p>
                        <p className="text-xs font-mono text-ink-muted">{new Date(health.timestamp).toLocaleString()}</p>
                      </div>
                    )}

                    <div className="md:col-span-2 bg-surface border border-stroke rounded-sm overflow-hidden">
                      <div className="px-4 py-3 border-b border-stroke">
                        <p className="text-xs font-mono text-ink-faint uppercase tracking-widest">Raw Response</p>
                      </div>
                      <pre className="px-4 py-3 text-xs font-mono text-ink-muted overflow-x-auto">
                        {JSON.stringify(health, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Evaluation ── */}
            {activeTab === 'eval' && (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <button
                    onClick={runEvaluation}
                    disabled={evalLoading}
                    className="px-4 py-2 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 disabled:opacity-40 transition-all flex items-center gap-2"
                  >
                    {evalLoading ? <><span className="animate-pulse">Running…</span></> : <><Play className="w-3.5 h-3.5" /> Run Evaluation</>}
                  </button>
                  {evalLoading && (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-ink-faint font-mono animate-pulse">
                      Running 10 test cases × 2 roles — polling every 5s…
                    </span>
                    <div className="flex gap-1">
                      {[0,1,2].map(i => (
                        <span key={i} className="w-1.5 h-1.5 rounded-full bg-gold animate-bounce"
                          style={{ animationDelay: `${i * 150}ms` }} />
                      ))}
                    </div>
                  </div>
                )}
                </div>

                {error && (
                  <div className="px-4 py-3 bg-danger-dim border border-danger/30 rounded-sm text-xs text-danger font-mono">{error}</div>
                )}

                {results.length > 0 && (
                  <>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { label: 'Total',  value: stats.test_count, color: 'text-gold',    border: 'border-gold/20'    },
                        { label: 'Passed', value: stats.passed,     color: 'text-success', border: 'border-success/20' },
                        { label: 'Failed', value: stats.failed,     color: 'text-danger',  border: 'border-danger/20'  },
                      ].map(s => (
                        <div key={s.label} className={`bg-surface border ${s.border} rounded-sm p-4 text-center`}>
                          <div className={`text-2xl font-mono font-bold ${s.color}`}>{s.value}</div>
                          <div className="text-xs text-ink-faint font-mono mt-1 uppercase tracking-widest">{s.label}</div>
                        </div>
                      ))}
                    </div>

                    <div className="bg-surface border border-stroke rounded-sm overflow-hidden">
                      <div className="grid grid-cols-[32px_80px_1fr_80px_80px_80px] gap-2 px-4 py-3 border-b border-stroke text-xs font-mono text-ink-faint uppercase tracking-widest">
                        <span>#</span>
                        <span>Category</span>
                        <span>Question</span>
                        <span>Guest</span>
                        <span>Admin</span>
                        <span>Status</span>
                      </div>
                      {results.map((r, i) => <EvalResultRow key={i} result={r} />)}
                    </div>
                  </>
                )}

                {!evalLoading && results.length === 0 && !error && (
                  <div className="text-center py-20 text-ink-faint font-mono text-xs uppercase tracking-widest">
                    Click "Run Evaluation" to test all 10 cases
                  </div>
                )}
              </div>
            )}

            {/* ── API Explorer ── */}
            {activeTab === 'api' && (
              <div className="space-y-6">
                {ENDPOINTS.map(group => (
                  <div key={group.group}>
                    <p className="text-xs font-mono text-ink-faint uppercase tracking-widest mb-3">
                      {group.group}
                    </p>
                    <div className="space-y-2">
                      {group.items.map(item => (
                        <EndpointCard key={item.method + item.path} item={item} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
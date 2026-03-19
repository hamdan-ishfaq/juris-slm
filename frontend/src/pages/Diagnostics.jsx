import React, { useState } from 'react';
import { Zap, Menu } from 'lucide-react';
import { evalAPI } from '../lib/api';
import Sidebar from '../components/Sidebar';

export default function Diagnostics() {
  const [results,  setResults]  = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [stats,    setStats]    = useState({ test_count: 0, passed: 0, failed: 0 });
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const runEvaluation = async () => {
    setLoading(true); setError(''); setResults([]);
    try {
      const response = await evalAPI.runEvaluation();
      if (response.data.status === 'completed') {
        setResults(response.data.results);
        setStats({
          test_count: response.data.test_count,
          passed:     response.data.passed,
          failed:     response.data.failed,
        });
      }
    } catch (err) {
      setError(`Evaluation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const guestColor = (result) => {
    const denied = result.guest_response.toLowerCase().includes('access denied');
    const correct = result.should_deny_guest ? denied : !denied;
    return correct ? 'text-success' : 'text-danger';
  };

  return (
    <div className="flex h-[100dvh] bg-base">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="border-b border-stroke bg-surface flex-shrink-0">
          <div className="max-w-6xl mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 text-ink-faint hover:text-ink hover:bg-elevated rounded-sm transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <Zap className="w-4 h-4 text-gold" />
            <div>
              <h1 className="text-sm font-medium text-ink tracking-wide">System Diagnostics</h1>
              <p className="text-xs text-ink-faint hidden md:block">Automated evaluation of retrieval, logic, and security</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto px-4 md:px-6 py-6 space-y-6">

            {/* Run button */}
            <div className="flex items-center gap-4">
              <button
                onClick={runEvaluation}
                disabled={loading}
                className="px-4 py-2 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? 'Running Tests…' : 'Run Full Evaluation'}
              </button>
              {loading && (
                <span className="text-xs text-ink-faint font-mono animate-pulse">Querying system…</span>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="px-4 py-3 bg-danger-dim border border-danger/30 rounded-sm text-xs text-danger font-mono">
                {error}
              </div>
            )}

            {/* Stats */}
            {results.length > 0 && (
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Total Tests', value: stats.test_count, color: 'text-gold',    border: 'border-gold/30'    },
                  { label: 'Passed',      value: stats.passed,     color: 'text-success', border: 'border-success/30' },
                  { label: 'Failed',      value: stats.failed,     color: 'text-danger',  border: 'border-danger/30'  },
                ].map(s => (
                  <div key={s.label} className={`bg-surface border ${s.border} rounded-sm p-4 text-center`}>
                    <div className={`text-2xl font-mono font-bold ${s.color}`}>{s.value}</div>
                    <div className="text-xs text-ink-faint font-mono mt-1 uppercase tracking-widest">{s.label}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Results table */}
            {results.length > 0 && (
              <div className="overflow-x-auto rounded-sm border border-stroke">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="bg-elevated border-b border-stroke">
                      {['ID', 'Category', 'Question', 'Guest', 'Admin', 'Status'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-ink-faint uppercase tracking-widest font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, i) => (
                      <tr key={i} className="border-b border-stroke last:border-0 hover:bg-elevated transition-colors">
                        <td className="px-4 py-3 text-ink-muted">{r.id}</td>
                        <td className="px-4 py-3 text-ink-muted">{r.category}</td>
                        <td className="px-4 py-3 text-ink max-w-xs">
                          <span title={r.question} className="truncate block">{r.question.substring(0, 40)}…</span>
                        </td>
                        <td className={`px-4 py-3 font-medium ${guestColor(r)}`}>
                          {r.guest_response.substring(0, 28)}…
                        </td>
                        <td className="px-4 py-3 text-info">
                          {r.admin_response.substring(0, 28)}…
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-medium ${
                            r.status === 'PASS'
                              ? 'bg-success/10 text-success border border-success/20'
                              : 'bg-danger/10  text-danger  border border-danger/20'
                          }`}>
                            {r.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Empty state */}
            {!loading && results.length === 0 && !error && (
              <div className="text-center py-20 text-ink-faint font-mono text-xs uppercase tracking-widest">
                Run an evaluation to see results
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
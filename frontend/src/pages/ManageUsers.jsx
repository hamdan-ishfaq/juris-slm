import { useEffect, useState } from 'react';
import { adminAPI } from '../lib/api';
import { Loader2, Shield, Trash2, ArrowUpRight, ArrowDownRight, Menu } from 'lucide-react';
import Sidebar from '../components/Sidebar';

const roleMeta = {
  owner: { color: 'text-gold',    bg: 'bg-gold/10    border-gold/20'    },
  admin: { color: 'text-info',    bg: 'bg-info/10    border-info/20'    },
  user:  { color: 'text-ink-muted', bg: 'bg-elevated  border-stroke'    },
  guest: { color: 'text-ink-faint', bg: 'bg-elevated  border-stroke'    },
};

export default function ManageUsers() {
  const [users,       setUsers]       = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const loadUsers = async () => {
    setLoading(true); setError('');
    try {
      const res = await adminAPI.listUsers();
      setUsers(res.data || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally { setLoading(false); }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleRole = async (id, role) => {
    setLoading(true);
    try   { await adminAPI.updateRole(id, role); await loadUsers(); }
    catch (e) { setError(e.response?.data?.detail || e.message); setLoading(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Permanently delete this user?')) return;
    setLoading(true);
    try   { await adminAPI.deleteUser(id); await loadUsers(); }
    catch (e) { setError(e.response?.data?.detail || e.message); setLoading(false); }
  };

  return (
    <div className="flex h-[100dvh] bg-base">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="border-b border-stroke bg-surface flex-shrink-0">
          <div className="max-w-5xl mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 text-ink-faint hover:text-ink hover:bg-elevated rounded-sm transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <Shield className="w-4 h-4 text-gold" />
            <div>
              <h1 className="text-sm font-medium text-ink tracking-wide">Manage Users</h1>
              <p className="text-xs text-ink-faint hidden md:block">Promote, demote, or remove accounts</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-4 md:px-6 py-6">

            {error && (
              <div className="mb-4 px-4 py-3 bg-danger-dim border border-danger/30 rounded-sm text-xs text-danger font-mono">
                {error}
              </div>
            )}

            <div className="bg-surface border border-stroke rounded-sm overflow-hidden">

              {/* Table header */}
              <div className="hidden md:grid grid-cols-[1fr_100px_160px_160px_80px] px-4 py-3 border-b border-stroke text-xs font-mono text-ink-faint uppercase tracking-widest">
                <span>Email</span>
                <span>Role</span>
                <span>Created</span>
                <span className="text-center">Actions</span>
                <span className="text-center">Remove</span>
              </div>

              {loading && (
                <div className="flex items-center justify-center py-12 text-ink-muted gap-2 text-xs font-mono">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading users…
                </div>
              )}

              {!loading && users.map((u, i) => {
                const meta = roleMeta[u.role] || roleMeta.user;
                return (
                  <div
                    key={u.id}
                    className={`grid grid-cols-1 md:grid-cols-[1fr_100px_160px_160px_80px] gap-2 md:gap-0 px-4 py-3 items-center text-sm border-stroke ${i < users.length - 1 ? 'border-b' : ''}`}
                  >
                    <span className="text-ink font-mono text-xs break-all">{u.email}</span>

                    <span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-xs font-mono font-medium border ${meta.bg} ${meta.color}`}>
                        <span className="w-1 h-1 rounded-full bg-current" />
                        {u.role}
                      </span>
                    </span>

                    <span className="text-xs text-ink-faint font-mono">
                      {new Date(u.created_at).toLocaleDateString()}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleRole(u.id, 'admin')}
                        disabled={u.role === 'admin' || u.role === 'owner'}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-mono bg-elevated border border-stroke hover:border-stroke-strong hover:text-ink text-ink-muted disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      >
                        <ArrowUpRight className="w-3 h-3" /> Admin
                      </button>
                      <button
                        onClick={() => handleRole(u.id, 'user')}
                        disabled={u.role === 'user'}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-mono bg-elevated border border-stroke hover:border-stroke-strong hover:text-ink text-ink-muted disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      >
                        <ArrowDownRight className="w-3 h-3" /> User
                      </button>
                    </div>

                    <div className="flex justify-start md:justify-center">
                      <button
                        onClick={() => handleDelete(u.id)}
                        disabled={u.role === 'owner'}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-mono text-ink-faint hover:text-danger hover:bg-danger-dim border border-transparent hover:border-danger/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      >
                        <Trash2 className="w-3 h-3" /> Remove
                      </button>
                    </div>
                  </div>
                );
              })}

              {!loading && users.length === 0 && (
                <div className="text-center py-12 text-ink-faint font-mono text-xs uppercase tracking-widest">
                  No users found
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
import { useEffect, useState } from 'react';
import { adminAPI } from '../lib/api';
import { Loader2, Shield, Trash2, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export default function ManageUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadUsers = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminAPI.listUsers();
      setUsers(res.data || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleRole = async (id, role) => {
    setLoading(true);
    try {
      await adminAPI.updateRole(id, role);
      await loadUsers();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this user?')) return;
    setLoading(true);
    try {
      await adminAPI.deleteUser(id);
      await loadUsers();
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white pt-24 pb-12 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="w-6 h-6 text-amber-300" />
          <h1 className="text-3xl font-bold">Manage Users</h1>
        </div>
        <p className="text-gray-400 mb-6">Owner-only controls: promote/demote accounts and remove users.</p>

        {error && (
          <div className="mb-4 p-3 rounded bg-red-900/40 border border-red-700 text-sm text-red-200">{error}</div>
        )}

        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="grid grid-cols-5 px-4 py-3 text-sm text-gray-400 border-b border-gray-800">
            <span>Email</span>
            <span>Role</span>
            <span>Created</span>
            <span className="text-center">Promote/Demote</span>
            <span className="text-center">Delete</span>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-10 text-gray-300">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading...
            </div>
          )}

          {!loading && users.map((u) => (
            <div key={u.id} className="grid grid-cols-5 px-4 py-3 text-sm border-b border-gray-800 last:border-b-0 items-center">
              <span className="text-gray-200 break-all">{u.email}</span>
              <span className="font-semibold capitalize">{u.role}</span>
              <span className="text-gray-400 text-xs">{new Date(u.created_at).toLocaleString()}</span>
              <div className="flex items-center justify-center gap-2">
                <button
                  onClick={() => handleRole(u.id, 'admin')}
                  disabled={u.role === 'admin'}
                  className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50 flex items-center gap-1"
                >
                  <ArrowUpRight className="w-4 h-4" /> Admin
                </button>
                <button
                  onClick={() => handleRole(u.id, 'user')}
                  disabled={u.role === 'user'}
                  className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50 flex items-center gap-1"
                >
                  <ArrowDownRight className="w-4 h-4" /> User
                </button>
              </div>
              <div className="flex justify-center">
                <button
                  onClick={() => handleDelete(u.id)}
                  className="px-3 py-1 rounded bg-red-900 hover:bg-red-800 flex items-center gap-1 text-red-100"
                >
                  <Trash2 className="w-4 h-4" /> Remove
                </button>
              </div>
            </div>
          ))}

          {!loading && users.length === 0 && (
            <div className="text-center py-8 text-gray-500">No users found.</div>
          )}
        </div>
      </div>
    </div>
  );
}

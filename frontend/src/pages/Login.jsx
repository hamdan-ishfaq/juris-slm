import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

const Login = () => {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();
    setLoading(true);

    // Mock Authentication Logic
    setTimeout(() => {
      const user = username.toLowerCase().trim();
      
      if (user === 'admin') {
        localStorage.setItem('juris_role', 'Admin');
        toast.success('Welcome back, Administrator');
        navigate('/dashboard');
      } else if (user === 'guest') {
        localStorage.setItem('juris_role', 'Guest');
        toast.success('Access Granted: Guest Mode');
        navigate('/dashboard');
      } else {
        toast.error('Invalid User. Try "admin" or "guest"');
      }
      setLoading(false);
    }, 800);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-md border border-slate-100">
        <div className="text-center mb-8">
          <div className="bg-juris-100 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield className="w-8 h-8 text-juris-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900">System Login</h2>
          <p className="text-slate-500">Enter your credentials to continue</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-slate-200 focus:ring-2 focus:ring-juris-500 focus:border-transparent outline-none transition-all"
              placeholder="Type 'admin' or 'guest'"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-juris-900 text-white py-3 rounded-lg font-bold hover:bg-slate-800 transition-colors flex items-center justify-center"
          >
            {loading ? <Loader2 className="animate-spin" /> : 'Authenticate'}
          </button>
        </form>
        
        <div className="mt-6 text-center text-xs text-slate-400">
          SECURE CONNECTION • 256-BIT ENCRYPTION
        </div>
      </div>
    </div>
  );
};

export default Login;
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../lib/api';

export default function Login() {
  const [email,    setEmail]    = useState('owner@beweis.com');
  const [password, setPassword] = useState('OwnerSecret123!');
  const [isLogin,  setIsLogin]  = useState(true);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [success,  setSuccess]  = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');

    if (!email.trim() || !password.trim()) {
      setError('Email and password are required');
      return;
    }

    setLoading(true);
    try {
      if (isLogin) {
        await authAPI.login(email, password);
        setSuccess('Authenticated. Redirecting...');
        setTimeout(() => navigate('/'), 500);
      } else {
        try {
          await authAPI.register(email, password);
          setSuccess('Account created.');
          setLoading(false);
          setTimeout(async () => {
            setLoading(true);
            try {
              await authAPI.login(email, password);
              setTimeout(() => navigate('/'), 500);
            } catch {
              setError('Login failed. Please sign in manually.');
              setLoading(false);
            }
          }, 1500);
        } catch (err) {
          setError(err.message);
          setLoading(false);
        }
        return;
      }
    } catch (err) {
      let msg = 'An error occurred';
      if (err.response?.status === 429)      msg = 'Too many attempts. Please wait.';
      else if (err.response?.status === 401) msg = 'Invalid credentials.';
      else if (err.response?.data?.detail)   msg = err.response.data.detail;
      setError(msg);
      setLoading(false);
      toast.error(msg, { duration: 4000 });
    }
  };

  const inputCls = [
    'w-full px-3 py-2 bg-base border border-stroke rounded-sm',
    'text-sm text-ink placeholder:text-ink-faint font-sans',
    'focus:outline-none focus:border-stroke-focus focus:ring-1 focus:ring-gold/20',
    'transition-all duration-150 disabled:opacity-50',
  ].join(' ');

  return (
    <div className="min-h-screen bg-base flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-surface border border-stroke rounded-sm p-8">

          {/* Logo */}
          <div className="flex items-center gap-2.5 mb-1">
            <div className="flex flex-col gap-[3px]">
              <span className="block h-[2px] w-5 bg-gold"      />
              <span className="block h-[2px] w-[14px] bg-gold" />
              <span className="block h-[2px] w-[10px] bg-gold" />
            </div>
            <span className="font-mono text-base font-medium tracking-[0.14em] text-ink">BEWEIS</span>
          </div>
          <p className="text-xs text-ink-faint font-mono ml-8 mb-8">
            {isLogin ? 'sign in to your account' : 'create a new account'}
          </p>

          {/* Alerts */}
          {error && (
            <div className="mb-5 px-3 py-2.5 bg-danger-dim border border-danger/30 rounded-sm flex items-start gap-2.5">
              <AlertCircle className="w-3.5 h-3.5 text-danger flex-shrink-0 mt-0.5" />
              <span className="text-xs text-danger">{error}</span>
            </div>
          )}
          {success && (
            <div className="mb-5 px-3 py-2.5 bg-success-dim border border-success/30 rounded-sm flex items-start gap-2.5">
              <CheckCircle className="w-3.5 h-3.5 text-success flex-shrink-0 mt-0.5" />
              <span className="text-xs text-success">{success}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-mono text-ink-muted uppercase tracking-widest mb-1.5">Email</label>
              <input
                type="email" value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required disabled={loading}
                className={inputCls}
              />
            </div>
            <div>
              <label className="block text-xs font-mono text-ink-muted uppercase tracking-widest mb-1.5">Password</label>
              <input
                type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required disabled={loading}
                className={inputCls}
              />
            </div>

            <button
              type="submit" disabled={loading}
              className="w-full py-2.5 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Authenticating...
                </>
              ) : (isLogin ? 'Sign In' : 'Sign Up')}
            </button>
          </form>

          {/* Toggle */}
          <p className="mt-5 text-center text-xs text-ink-faint font-mono">
            {isLogin ? 'No account? ' : 'Have an account? '}
            <button
              type="button"
              onClick={() => { setIsLogin(!isLogin); setError(''); setSuccess(''); }}
              disabled={loading}
              className="text-gold hover:text-gold/80 font-medium transition-colors"
            >
              {isLogin ? 'Sign up' : 'Sign in'}
            </button>
          </p>

          {/* Demo creds */}
          <div className="mt-6 p-3 bg-elevated border border-stroke rounded-sm">
            <p className="text-xs font-mono text-ink-faint uppercase tracking-widest mb-2">Demo</p>
            <p className="text-xs font-mono text-ink-muted">email: <span className="text-gold">owner@beweis.com</span></p>
            <p className="text-xs font-mono text-ink-muted">pass: <span className="text-gold">OwnerSecret123!</span></p>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../lib/api';
import { Button, Input, Card, CardBody } from '../components/ui';

export default function Login() {
  const [email, setEmail] = useState('owner@beweis.com');
  const [password, setPassword] = useState('OwnerSecret123!');
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!email.trim() || !password.trim()) {
      setError('Email and password are required');
      toast.error('Email and password are required', { duration: 3000 });
      return;
    }

    setLoading(true);

    try {
      if (isLogin) {
        await authAPI.login(email, password);
        setSuccess('Logged in! Redirecting...');
        toast.success('Welcome!', { duration: 2000 });
        setTimeout(() => navigate('/'), 500);
      } else {
        const signupPassword = password;
        try {
          await authAPI.register(email, signupPassword);
          setSuccess('Account created!');
          toast.success('Account created!', { duration: 2000 });
          setLoading(false);
          setTimeout(async () => {
            setLoading(true);
            try {
              await authAPI.login(email, signupPassword);
              setTimeout(() => navigate('/'), 500);
            } catch (loginErr) {
              setError('Login failed.');
              setSuccess('');
              setLoading(false);
              toast.error('Please log in manually');
            }
          }, 1500);
        } catch (registerErr) {
          setError(registerErr.message);
          setLoading(false);
          toast.error(registerErr.message);
        }
        return;
      }
    } catch (err) {
      let errorMsg = 'An error occurred';
      if (err.response?.status === 429) {
        errorMsg = 'Too many login attempts.';
      } else if (err.response?.status === 401) {
        errorMsg = 'Invalid email or password';
      } else if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail;
      }
      setError(errorMsg);
      setLoading(false);
      toast.error(errorMsg, { duration: 4000 });
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card variant="elevated" className="overflow-hidden">
          <CardBody className="p-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-neutral-900 mb-2">BEWEIS</h1>
              <p className="text-base text-neutral-600">
                {isLogin ? 'Sign in to your account' : 'Create a new account'}
              </p>
            </div>

            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-300 rounded-md flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-red-800">{error}</span>
              </div>
            )}

            {success && (
              <div className="mb-6 p-4 bg-green-50 border border-green-300 rounded-md flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                <span className="text-sm text-green-800">{success}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" required disabled={loading} />
              <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required disabled={loading} />
              <Button type="submit" variant="primary" size="lg" loading={loading} disabled={loading} className="w-full">
                {isLogin ? 'Sign In' : 'Sign Up'}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-neutral-600">
                {isLogin ? "Don't have an account? " : 'Already have an account? '}
                <button type="button" onClick={() => { setIsLogin(!isLogin); setError(''); setSuccess(''); }} disabled={loading} className="text-primary-600 hover:text-primary-700 font-medium transition-colors">
                  {isLogin ? 'Sign up' : 'Sign in'}
                </button>
              </p>
            </div>

            <div className="mt-6 p-4 bg-neutral-100 border border-neutral-300 rounded-md">
              <p className="text-xs font-semibold text-neutral-700 mb-2">Demo Credentials:</p>
              <p className="text-xs text-neutral-600">Email: <span className="text-neutral-900 font-mono">owner@beweis.com</span></p>
              <p className="text-xs text-neutral-600">Password: <span className="text-neutral-900 font-mono">OwnerSecret123!</span></p>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

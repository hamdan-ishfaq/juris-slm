import React, { useState, useEffect, useRef } from 'react';
import { Scale, Shield, Lock, Sparkles, ArrowRight, MessageSquare, Send, Loader2, AlertCircle, CheckCircle, LogOut, User } from 'lucide-react';

// ============================================
// 1. API SETUP (lib/api.js equivalent)
// ============================================
const API_BASE_URL = 'http://127.0.0.1:8000';

const api = {
  query: async (question, role) => {
    const response = await fetch(`${API_BASE_URL}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question, role }) 
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
  }
};

// ============================================
// 2. LANDING PAGE
// ============================================
const LandingPage = ({ onNavigate }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900">
      {/* Navigation */}
      <nav className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="w-8 h-8 text-blue-400" />
            <span className="text-2xl font-bold text-white">Juris AI</span>
          </div>
          <button
            onClick={() => onNavigate('login')}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Sign In
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-300 text-sm mb-8">
            <Sparkles className="w-4 h-4" />
            <span>AI-Powered Legal Intelligence</span>
          </div>
          
          <h1 className="text-6xl font-bold text-white mb-6 leading-tight">
            Your Legal Research
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              Powered by AI
            </span>
          </h1>
          
          <p className="text-xl text-slate-300 mb-12 leading-relaxed">
            Get instant answers to complex legal questions with AI-driven insights.
            Backed by authoritative sources and built for legal professionals.
          </p>
          
          <button
            onClick={() => onNavigate('login')}
            className="inline-flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white text-lg font-semibold rounded-xl shadow-xl shadow-blue-500/20 transition-all hover:scale-105"
          >
            Get Started
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-3 gap-8 mt-24">
          <div className="p-8 bg-slate-800/50 border border-slate-700/50 rounded-2xl backdrop-blur-sm">
            <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-4">
              <MessageSquare className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-3">Instant Answers</h3>
            <p className="text-slate-400">Get immediate responses to your legal queries with AI-powered analysis.</p>
          </div>
          
          <div className="p-8 bg-slate-800/50 border border-slate-700/50 rounded-2xl backdrop-blur-sm">
            <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-4">
              <Shield className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-3">Verified Sources</h3>
            <p className="text-slate-400">Every answer is backed by authoritative legal sources and references.</p>
          </div>
          
          <div className="p-8 bg-slate-800/50 border border-slate-700/50 rounded-2xl backdrop-blur-sm">
            <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-4">
              <Lock className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-3">Secure & Private</h3>
            <p className="text-slate-400">Role-based access control ensures your data stays confidential.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// 3. LOGIN PAGE
// ============================================
const LoginPage = ({ onNavigate, onLogin }) => {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = () => {
    setError('');

    if (!username.trim()) {
      setError('Please enter a username');
      return;
    }

    const role = username.toLowerCase() === 'admin' ? 'Admin' : 'Guest';
    localStorage.setItem('userRole', role);
    localStorage.setItem('username', username);
    onLogin(role, username);
    onNavigate('dashboard');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4">
            <Scale className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome to Juris AI</h1>
          <p className="text-slate-400">Sign in to access your legal AI assistant</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8 backdrop-blur-sm">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter username"
                className="w-full px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
            >
              Sign In
            </button>
          </div>

          <div className="mt-6 pt-6 border-t border-slate-700">
            <p className="text-sm text-slate-400 text-center">
              Demo credentials: <span className="text-blue-400 font-medium">admin</span> or <span className="text-blue-400 font-medium">guest</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// 4. DASHBOARD (CHAT INTERFACE)
// ============================================
const Dashboard = ({ role, username, onNavigate }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleLogout = () => {
    localStorage.removeItem('userRole');
    localStorage.removeItem('username');
    onNavigate('login');
  };

  const handleSubmit = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);

    setMessages(prev => [...prev, { type: 'user', content: userMessage }]);

    setLoading(true);

    try {
      const response = await api.query(userMessage, role);
      
      setMessages(prev => [...prev, {
        type: 'assistant',
        content: response.answer,
        sources: response.sources || []
      }]);
    } catch (err) {
      setError(err.message || 'Failed to get response from AI');
      setMessages(prev => [...prev, {
        type: 'error',
        content: 'Sorry, I encountered an error processing your request. Please try again.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="h-screen bg-slate-900 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-800/50 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Scale className="w-7 h-7 text-blue-400" />
            <span className="text-xl font-bold text-white">Juris AI</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Role Badge */}
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
              role === 'Admin' 
                ? 'bg-blue-500/10 border border-blue-500/20 text-blue-400' 
                : 'bg-slate-700/50 border border-slate-600 text-slate-300'
            }`}>
              {role === 'Admin' ? (
                <Shield className="w-4 h-4" />
              ) : (
                <User className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">{role} Access</span>
            </div>

            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span className="text-sm font-medium">Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* Chat Container */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {messages.length === 0 ? (
            <div className="text-center py-20">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-500/10 rounded-2xl mb-4">
                <MessageSquare className="w-8 h-8 text-blue-400" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Welcome, {username}!</h2>
              <p className="text-slate-400">Ask me any legal question to get started.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-3xl ${
                    msg.type === 'user' 
                      ? 'bg-blue-600 text-white rounded-2xl rounded-tr-sm' 
                      : msg.type === 'error'
                      ? 'bg-red-500/10 border border-red-500/20 text-red-400 rounded-2xl rounded-tl-sm'
                      : 'bg-slate-800 text-slate-100 rounded-2xl rounded-tl-sm'
                  } px-6 py-4`}>
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-slate-700">
                        <p className="text-xs text-slate-400 mb-2 font-medium">Sources:</p>
                        <div className="flex flex-wrap gap-2">
                          {msg.sources.map((source, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-3 py-1 bg-slate-700/50 border border-slate-600 rounded-full text-xs text-slate-300">
                              <CheckCircle className="w-3 h-3 text-blue-400" />
                              {source}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-slate-800 rounded-2xl rounded-tl-sm px-6 py-4">
                    <div className="flex items-center gap-3 text-slate-400">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Analyzing your question...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Error Toast */}
      {error && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 max-w-md w-full mx-6">
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-400 text-sm font-medium">Connection Error</p>
              <p className="text-red-300 text-sm mt-1">{error}</p>
            </div>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
              ×
            </button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-slate-700 bg-slate-800/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a legal question..."
              disabled={loading}
              className="flex-1 px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
            />
            <button
              onClick={handleSubmit}
              disabled={loading || !input.trim()}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-colors flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================
// 5. MAIN APP (ROUTER & LAYOUT)
// ============================================
export default function App() {
  const [currentPage, setCurrentPage] = useState('landing');
  const [userRole, setUserRole] = useState(null);
  const [username, setUsername] = useState('');

  useEffect(() => {
    const savedRole = localStorage.getItem('userRole');
    const savedUsername = localStorage.getItem('username');
    if (savedRole && savedUsername) {
      setUserRole(savedRole);
      setUsername(savedUsername);
      setCurrentPage('dashboard');
    }
  }, []);

  const handleLogin = (role, name) => {
    setUserRole(role);
    setUsername(name);
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'landing':
        return <LandingPage onNavigate={setCurrentPage} />;
      case 'login':
        return <LoginPage onNavigate={setCurrentPage} onLogin={handleLogin} />;
      case 'dashboard':
        return userRole ? (
          <Dashboard role={userRole} username={username} onNavigate={setCurrentPage} />
        ) : (
          <LoginPage onNavigate={setCurrentPage} onLogin={handleLogin} />
        );
      default:
        return <LandingPage onNavigate={setCurrentPage} />;
    }
  };

  return renderPage();
}
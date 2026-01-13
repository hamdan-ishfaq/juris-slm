import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, LogOut, ShieldAlert, ShieldCheck, User, Bot, FileText } from 'lucide-react';
import api from '../lib/api';
import toast from 'react-hot-toast';

const Dashboard = () => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState('');
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const storedRole = localStorage.getItem('juris_role');
    if (!storedRole) {
      navigate('/login');
    } else {
      setRole(storedRole);
      setMessages([{ type: 'bot', text: `System ready. Logged in as ${storedRole}. How can I assist you with legal inquiries today?` }]);
    }
  }, [navigate]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleLogout = () => {
    localStorage.removeItem('juris_role');
    navigate('/');
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMsg = { type: 'user', text: query };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setLoading(true);

    try {
      const response = await api.post('/query', {
        query: userMsg.text,
        role: role
      });

      const botMsg = {
        type: 'bot',
        text: response.data.answer,
        sources: response.data.sources
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      console.error(error);
      toast.error('Connection failed. Is the backend running?');
      setMessages(prev => [...prev, { type: 'bot', text: "⚠️ Error: Unable to reach the Neural Engine." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-white">
      {/* Header */}
      <header className="flex justify-between items-center p-4 border-b border-slate-100 bg-white">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${role === 'Admin' ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
            {role === 'Admin' ? <ShieldAlert className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
          </div>
          <div>
            <h1 className="font-bold text-slate-800">Juris Console</h1>
            <p className="text-xs text-slate-500">Role: <span className="font-semibold">{role}</span></p>
          </div>
        </div>
        <button onClick={handleLogout} className="p-2 text-slate-400 hover:text-red-500 transition-colors">
          <LogOut className="w-5 h-5" />
        </button>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 bg-slate-50 space-y-6">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex max-w-[80%] ${msg.type === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-3`}>
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.type === 'user' ? 'bg-juris-900 text-white' : 'bg-juris-600 text-white'}`}>
                {msg.type === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Bubble */}
              <div className={`p-4 rounded-2xl shadow-sm ${msg.type === 'user' ? 'bg-juris-900 text-white rounded-tr-none' : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'}`}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                
                {/* Citations (Only for Bot) */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center"><FileText className="w-3 h-3 mr-1" /> Cited Sources:</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.sources.map((src, i) => (
                        <span key={i} className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-md border border-slate-200">
                          {src}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
             <div className="flex items-center gap-2 p-4 bg-white rounded-2xl border border-slate-100">
               <div className="w-2 h-2 bg-juris-400 rounded-full animate-bounce"></div>
               <div className="w-2 h-2 bg-juris-400 rounded-full animate-bounce delay-75"></div>
               <div className="w-2 h-2 bg-juris-400 rounded-full animate-bounce delay-150"></div>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-slate-100">
        <div className="max-w-4xl mx-auto relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a legal question..."
            className="w-full pl-6 pr-14 py-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-juris-500 focus:bg-white transition-all outline-none text-slate-800"
          />
          <button 
            type="submit" 
            disabled={loading || !query.trim()}
            className="absolute right-3 top-3 p-2 bg-juris-600 text-white rounded-lg hover:bg-juris-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
};

export default Dashboard;
import { useState } from 'react';
import { Send, Bot, User, Shield, FileText } from 'lucide-react';

export default function Chat() {
  const [input, setInput] = useState('');
  const [role, setRole] = useState('guest'); 
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Hello. I am Juris AI. Select your Access Level above to begin.' }
  ]);
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    const userMsg = input;
    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, role: role })
      });
      const data = await res.json();
      
      // --- HERE IS THE FIX: We now save the 'sources' too ---
      setMessages(prev => [...prev, { 
        role: 'ai', 
        content: data.answer, 
        sources: data.sources // <--- Capture the evidence
      }]);
      // ----------------------------------------------------

    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: 'Error connecting to the brain.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 pt-20 pb-4 px-4 flex flex-col">
      
      {/* Role Switcher */}
      <div className="max-w-4xl mx-auto w-full mb-4 flex justify-end">
        <div className="bg-gray-800 p-2 rounded-lg border border-gray-700 flex items-center gap-3">
          <span className="text-gray-400 text-sm">Simulate Role:</span>
          <select 
            value={role} 
            onChange={(e) => setRole(e.target.value)}
            className={`bg-gray-900 text-white px-3 py-1 rounded border ${
              role === 'admin' ? 'border-blue-500 text-blue-400' : 'border-gray-600 text-gray-400'
            }`}
          >
            <option value="guest">Guest (Restricted)</option>
            <option value="admin">Admin (Full Access)</option>
          </select>
          {role === 'admin' ? <Shield className="w-4 h-4 text-blue-400"/> : <User className="w-4 h-4 text-gray-400"/>}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 max-w-4xl mx-auto w-full overflow-y-auto mb-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`p-4 rounded-2xl max-w-[80%] ${
              m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-200'
            }`}>
              <div className="flex items-center gap-2 mb-1 text-xs opacity-50 font-bold uppercase">
                {m.role === 'user' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                {m.role === 'user' ? 'You' : 'Juris AI'}
              </div>
              
              {/* The Message Text */}
              <div className="whitespace-pre-wrap">{m.content}</div>

              {/* --- NEW: SOURCE CITATIONS --- */}
              {m.role === 'ai' && m.sources && m.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-700">
                  <p className="text-xs text-gray-400 mb-2 font-semibold">Sources Used:</p>
                  <div className="flex flex-wrap gap-2">
                    {/* Deduplicate sources to avoid showing same file twice */}
                    {[...new Set(m.sources)].map((source, idx) => (
                      <span key={idx} className="flex items-center gap-1 px-2 py-1 bg-blue-900/30 border border-blue-500/30 rounded text-xs text-blue-300">
                        <FileText className="w-3 h-3" />
                        {source}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {/* ----------------------------- */}

            </div>
          </div>
        ))}
        {loading && <div className="text-gray-500 text-sm animate-pulse ml-2">Thinking...</div>}
      </div>

      {/* Input Area */}
      <div className="max-w-4xl mx-auto w-full bg-gray-900 p-2 rounded-xl flex gap-2 border border-gray-800">
        <input 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder={`Ask as ${role}...`} 
          className="flex-1 bg-transparent text-white px-4 outline-none"
        />
        <button onClick={sendMessage} className="p-3 bg-blue-600 rounded-lg hover:bg-blue-700 transition">
          <Send className="w-5 h-5 text-white" />
        </button>
      </div>
    </div>
  );
}
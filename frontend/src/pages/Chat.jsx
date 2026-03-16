import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Send, Loader, Menu, FileText, Plus, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { queryAPI } from '../lib/api';
import Sidebar from '../components/Sidebar';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Card, { CardBody } from '../components/ui/Card';

// Loading skeleton component for chat history
function MessageSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-start"
    >
      <div className="bg-white border border-neutral-200 rounded-lg px-4 py-3 w-64 h-16">
        <div className="h-4 bg-neutral-200 rounded w-full mb-2 animate-pulse"></div>
        <div className="h-4 bg-neutral-200 rounded w-4/5 animate-pulse"></div>
      </div>
    </motion.div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'assistant',
      text: 'Welcome to BEWEIS! Ask me about legal documents, regulations, or any legal questions.'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 📚 Load chat history on component mount
  useEffect(() => {
    const loadChatHistory = async () => {
      setLoadingHistory(true);
      try {
        const response = await queryAPI.getChatHistory(50);
        const historyMessages = response.data.messages || [];
        
        if (historyMessages.length > 0) {
          // Convert backend format to UI format
          const formattedMessages = historyMessages.map((msg, idx) => ({
            id: idx + 1,
            type: msg.role === 'assistant' ? 'assistant' : 'user',
            text: msg.content,
            timestamp: msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : undefined
          }));
          
          setMessages(formattedMessages);
          console.log(`✅ Loaded ${historyMessages.length} messages from chat history`);
        } else {
          // Keep welcome message if no history
          console.log('📝 No previous chat history found');
        }
      } catch (error) {
        console.error('❌ Failed to load chat history:', error);
        toast.error('Failed to load chat history', { duration: 3000 });
      } finally {
        setLoadingHistory(false);
      }
    };

    loadChatHistory();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 🗑️ Clear chat history
  const handleClearChat = async () => {
    if (!window.confirm('Are you sure you want to clear your entire chat history? This cannot be undone.')) {
      return;
    }

    try {
      setLoading(true);
      await queryAPI.clearChatHistory();
      
      // Reset to welcome message
      setMessages([
        {
          id: 1,
          type: 'assistant',
          text: 'Welcome to BEWEIS! Ask me about legal documents, regulations, or any legal questions.'
        }
      ]);
      
      toast.success('Chat history cleared', { duration: 2000 });
      console.log('✅ Chat history cleared successfully');
    } catch (error) {
      console.error('❌ Failed to clear chat history:', error);
      let errorText = 'Failed to clear chat history';
      
      if (error.response?.status === 401) {
        errorText = 'Session expired. Please log in again.';
      } else if (error.response?.data?.detail) {
        errorText = error.response.data.detail;
      }
      
      toast.error(errorText, { duration: 3000 });
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = {
      id: messages.length + 1,
      type: 'user',
      text: input
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      console.log('📤 Sending query:', input);
      const response = await queryAPI.query(input);
      
      console.log('📥 Got response:', response.data);
      
      // ✅ New response format: { answer, sources, status }
      const answer = response.data.answer || 'No response received';
      const sources = response.data.sources || [];
      
      const assistantMessage = {
        id: messages.length + 2,
        type: 'assistant',
        text: answer,
        sources: sources,
        timestamp: new Date().toLocaleTimeString()
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      toast.success('Response received!', { duration: 2000 });
      
    } catch (error) {
      console.error('❌ Query error:', error);
      
      let errorText = 'An error occurred';
      
      if (error.response?.status === 429) {
        errorText = 'Rate limited - too many requests. Please wait a moment.';
      } else if (error.response?.status === 401) {
        errorText = 'Session expired. Please log in again.';
      } else if (error.response?.data?.detail) {
        errorText = error.response.data.detail;
      } else if (error.message) {
        errorText = error.message;
      }
      
      const errorMessage = {
        id: messages.length + 2,
        type: 'assistant',
        isError: true,
        text: `Error: ${errorText}`
      };
      
      setMessages(prev => [...prev, errorMessage]);
      toast.error(errorText, { duration: 4000 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[100dvh] bg-neutral-50">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-[100dvh] overflow-hidden">
        {/* Header */}
        <div className="border-b border-neutral-200 bg-white">
          <div className="max-w-5xl mx-auto px-4 md:px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="md:hidden p-2 text-neutral-600 hover:text-primary-700 hover:bg-neutral-100 rounded-lg transition-colors"
                >
                  <Menu className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-xl md:text-2xl font-semibold text-neutral-900">Legal Analysis</h1>
                  <p className="text-sm text-neutral-600 hidden md:block">Ask questions about your legal documents</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearChat}
                  disabled={loading}
                  className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 p-2"
                  title="Clear chat history"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setMessages([
                      {
                        id: 1,
                        type: 'assistant',
                        text: 'Welcome to BEWEIS! Ask me about legal documents, regulations, or any legal questions.'
                      }
                    ]);
                    toast.success('Started new conversation');
                  }}
                  className="flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  <span className="hidden md:inline">New Chat</span>
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto bg-neutral-50">
          <div className="max-w-5xl mx-auto px-4 md:px-6 py-6 space-y-4">
            {/* Loading skeleton while fetching history */}
            {loadingHistory && (
              <>
                <MessageSkeleton />
                <MessageSkeleton />
                <MessageSkeleton />
              </>
            )}
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[85%] md:max-w-[70%]`}>
                  {/* Message bubble */}
                  <div
                    className={`
                      rounded-lg px-4 py-3
                      ${message.type === 'user'
                        ? 'bg-neutral-100 text-neutral-900 border border-neutral-200'
                        : message.isError
                        ? 'bg-danger-50 border border-danger-200 text-danger-900'
                        : 'bg-white border border-neutral-200 text-neutral-900'
                      }
                    `}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                      {message.text}
                    </p>
                  </div>

                  {/* Citations/Sources below message */}
                  {message.type === 'assistant' && message.sources && message.sources.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs text-neutral-600 font-medium">Sources:</p>
                      {message.sources.slice(0, 5).map((source, idx) => (
                        <Card key={idx} className="bg-white">
                          <CardBody className="p-3">
                            <div className="flex items-start gap-2">
                              <FileText className="w-4 h-4 text-primary-600 flex-shrink-0 mt-0.5" />
                              <div className="flex-1 text-xs">
                                {typeof source === 'string' ? (
                                  <p className="text-neutral-700">{source.substring(0, 200)}...</p>
                                ) : (
                                  <>
                                    {source.text && <p className="text-neutral-700">{source.text.substring(0, 200)}...</p>}
                                    {source.source && <p className="text-neutral-500 mt-1">{source.source}</p>}
                                    {source.relevance && <p className="text-neutral-500 mt-1">{(source.relevance * 100).toFixed(0)}% match</p>}
                                  </>
                                )}
                              </div>
                            </div>
                          </CardBody>
                        </Card>
                      ))}
                      {message.sources.length > 5 && (
                        <p className="text-xs text-neutral-500">+{message.sources.length - 5} more sources</p>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
            
            {loading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-start"
              >
                <div className="bg-white border border-neutral-200 text-neutral-900 rounded-lg px-4 py-3 flex items-center gap-2">
                  <Loader className="w-4 h-4 animate-spin text-primary-600" />
                  <span className="text-sm">Analyzing...</span>
                </div>
              </motion.div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-neutral-200 bg-white">
          <div className="max-w-5xl mx-auto px-4 md:px-6 py-4">
            <form onSubmit={handleSendMessage} className="flex gap-3">
              <Input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a legal question..."
                disabled={loading}
                className="flex-1"
              />
              <Button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-4"
              >
                <Send className="w-4 h-4" />
                <span className="hidden md:inline ml-2">Send</span>
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

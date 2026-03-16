// src/lib/api.js
import axios from 'axios';
import toast from 'react-hot-toast';

// API Base URL Configuration
// Use relative paths for automatic Ngrok and localhost support
// This allows the app to work on https://ngrok-url and http://localhost:8001
const API_BASE = import.meta.env.VITE_API_BASE || '';

console.log('🔗 API Base URL:', API_BASE || 'Using relative paths (window.location)');

// Simple JWT decoder (no external dependency)
const decodeJWT = (token) => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const decoded = JSON.parse(atob(parts[1]));
    return decoded;
  } catch (err) {
    console.warn('Could not decode JWT:', err);
    return null;
  }
};

// Rate limit cooldown tracker (prevent duplicate toast messages)
let lastRateLimitToast = 0;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000, // 5 minutes - first query loads LLM model (can take 2-4 min)
});

// ✅ REQUEST INTERCEPTOR: Attach Bearer token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    console.log('🔐 Token attached to request:', config.method.toUpperCase(), config.url);
  } else {
    console.warn('⚠️ No auth token available');
  }
  return config;
}, (error) => {
  console.error('❌ Request interceptor error:', error);
  return Promise.reject(error);
});

// ✅ RESPONSE INTERCEPTOR: Handle errors globally
api.interceptors.response.use(
  (response) => {
    console.log('✅ Response OK:', response.status, response.config.url);
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.message;
    
    console.error('❌ API Error:', {
      status,
      url: error.config?.url,
      detail,
      timestamp: new Date().toISOString()
    });

    // 🔴 401 UNAUTHORIZED: Token expired or invalid
    if (status === 401) {
      console.error('🔐 Auth failed - clearing token and redirecting to login');
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_email');
      localStorage.removeItem('user_role');
      localStorage.removeItem('user_id');
      
      // Redirect to login
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      toast.error('Session expired. Please log in again.', { id: 'auth-error' });
    }
    
    // 🟡 429 TOO MANY REQUESTS: Rate limited
    if (status === 429) {
      const now = Date.now();
      // Only show toast once per 5 seconds to avoid spam
      if (now - lastRateLimitToast > 5000) {
        toast.error('You are doing that too fast. Please wait.', { 
          id: 'rate-limit',
          duration: 3000 
        });
        lastRateLimitToast = now;
      }
      console.warn('⏱️ Rate limit hit - please wait before retrying');
    }
    
    // 🟠 Other errors
    if (status >= 500) {
      toast.error('Server error. Please try again later.', { id: 'server-error' });
    } else if (status >= 400 && status !== 401 && status !== 429) {
      console.error('💬 API returned:', detail);
    }

    return Promise.reject(error);
  }
);


export const authAPI = {
  register: async (email, password) => {
    try {
      const response = await api.post('/auth/register', { email, password });
      console.log('✅ Registration successful');
      return response;
    } catch (error) {
      console.error('❌ Registration failed:', error.response?.data?.detail);
      throw error;
    }
  },

  login: async (email, password) => {
    try {
      const response = await api.post('/auth/login', { email, password });
      
      // ✅ Store access token
      if (response.data.access_token) {
        localStorage.setItem('access_token', response.data.access_token);
        localStorage.setItem('user_email', email);
        
        // Decode token to extract role and user ID
        const decoded = decodeJWT(response.data.access_token);
        if (decoded) {
          localStorage.setItem('user_role', decoded.role || 'user');
          localStorage.setItem('user_id', decoded.sub);
          console.log('✅ Login successful - Token stored', { role: decoded.role, userId: decoded.sub });
        } else {
          localStorage.setItem('user_role', 'user');
          console.log('✅ Login successful - No role in token, defaulting to user');
        }
      }
      
      return response;
    } catch (error) {
      console.error('❌ Login failed:', error.response?.data?.detail || error.message);
      throw error;
    }
  },

  getMe: async () => {
    try {
      const response = await api.get('/auth/me');
      return response;
    } catch (error) {
      console.error('❌ Failed to get user info:', error.response?.data?.detail);
      throw error;
    }
  },

  logout: () => {
    console.log('🚪 Logging out...');
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
  }
};

export const queryAPI = {
  query: async (question) => {
    try {
      const role = localStorage.getItem('user_role') || 'user';
      console.log('🔍 Sending query:', { question, role });
      
      // Updated to use /chat/query endpoint from chat router
      // First query may take 2-4 minutes to load LLM model from disk
      const response = await api.post('/chat/query', { 
        query: question,
        role: role
      }, {
        timeout: 300000 // 5 minutes for model loading
      });
      
      console.log('✅ Query response received:', {
        hasAnswer: !!response.data.answer,
        hasCitations: !!response.data.sources,
        status: response.data.status
      });
      
      return response;
    } catch (error) {
      console.error('❌ Query failed:', error.response?.data?.detail || error.message);
      throw error;
    }
  },

  // Get chat history for current user
  getChatHistory: async (limit = 50) => {
    try {
      console.log('📚 Fetching chat history...');
      const response = await api.get(`/chat/history?limit=${limit}`);
      console.log('✅ Chat history retrieved:', response.data.message_count, 'messages');
      return response;
    } catch (error) {
      console.error('❌ Failed to fetch chat history:', error.response?.data?.detail || error.message);
      throw error;
    }
  },

  // Clear chat history for current user
  clearChatHistory: async () => {
    try {
      console.log('🗑️ Clearing chat history...');
      const response = await api.delete('/chat/history');
      console.log('✅ Chat history cleared');
      return response;
    } catch (error) {
      console.error('❌ Failed to clear chat history:', error.response?.data?.detail || error.message);
      throw error;
    }
  }
};

export const uploadAPI = {
  upload: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      console.log('📤 Uploading file:', { name: file.name, size: file.size, type: file.type });
      
      // Updated to use /documents/upload endpoint from documents router
      const response = await api.post('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      console.log('✅ File uploaded successfully:', response.data);
      return response;
    } catch (error) {
      console.error('❌ Upload failed:', error.response?.data?.detail || error.message);
      throw error;
    }
  },

  // Get document metadata
  getDocuments: async () => {
    try {
      console.log('📄 Fetching documents metadata...');
      const response = await api.get('/documents/metadata');
      console.log('✅ Documents retrieved:', response.data.num_chunks, 'chunks');
      return response;
    } catch (error) {
      console.error('❌ Failed to fetch documents:', error.response?.data?.detail || error.message);
      throw error;
    }
  },

  // Perform semantic search
  searchDocuments: async (query, threshold = 0.5, topK = 20) => {
    try {
      console.log('🔎 Searching documents:', query);
      const response = await api.get('/documents/semantic-search', {
        params: { query, threshold, top_k: topK }
      });
      console.log('✅ Search complete:', response.data.found, 'results');
      return response;
    } catch (error) {
      console.error('❌ Search failed:', error.response?.data?.detail || error.message);
      throw error;
    }
  }
};

export const evalAPI = {
  runEvaluation: async () => {
    try {
      console.log('🧪 Starting evaluation...');
      const response = await api.post('/evaluate');
      console.log('✅ Evaluation complete');
      return response;
    } catch (error) {
      console.error('❌ Evaluation failed:', error.response?.data?.detail || error.message);
      throw error;
    }
  }
};

export const adminAPI = {
  listUsers: async () => {
    try {
      const response = await api.get('/admin/users');
      return response;
    } catch (error) {
      console.error('❌ Failed to list users:', error.response?.data?.detail);
      throw error;
    }
  },

  updateRole: async (userId, role) => {
    try {
      const response = await api.put(`/admin/users/${userId}/role`, null, { 
        params: { role } 
      });
      return response;
    } catch (error) {
      console.error('❌ Failed to update role:', error.response?.data?.detail);
      throw error;
    }
  },

  deleteUser: async (userId) => {
    try {
      const response = await api.delete(`/admin/users/${userId}`);
      return response;
    } catch (error) {
      console.error('❌ Failed to delete user:', error.response?.data?.detail);
      throw error;
    }
  }
};

export default api;

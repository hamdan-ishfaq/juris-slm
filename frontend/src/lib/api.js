import axios from 'axios';

// Create a configured axios instance
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000', // Your Python API URL
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
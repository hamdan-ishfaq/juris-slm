import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Required for Windows browser → WSL2 (bind 0.0.0.0, not 127.0.0.1 only)
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Helps HMR when opening the app from Windows via WSL IP
    hmr: {
      host: 'localhost',
      clientPort: 5173,
    },
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
    },
  },
})

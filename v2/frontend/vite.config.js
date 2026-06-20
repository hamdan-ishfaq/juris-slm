import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const port = Number(process.env.VITE_PORT || 5173)

export default defineConfig({
  plugins: [react()],
  server: {
    // Required for Windows browser → WSL2 (bind 0.0.0.0, not 127.0.0.1 only)
    host: '0.0.0.0',
    port,
    strictPort: process.env.VITE_STRICT_PORT !== '0',
    // Helps HMR when opening the app from Windows via WSL IP
    hmr: {
      host: 'localhost',
      clientPort: port,
    },
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
    },
  },
  preview: {
    host: '0.0.0.0',
    port,
    strictPort: process.env.VITE_STRICT_PORT !== '0',
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
    },
  },
})

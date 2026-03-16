import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND = 'http://127.0.0.1:8001'

// Proxy all backend route prefixes to avoid CORS in local dev.
// When using ngrok you hit the ngrok URL directly so this only matters
// for `npm run dev` on localhost.
const proxyTarget = { target: BACKEND, changeOrigin: true }

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: true,
    clearMocks: true,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/auth':      proxyTarget,
      '/chat':      proxyTarget,
      '/documents': proxyTarget,
      '/admin':     proxyTarget,
      '/evaluate':  proxyTarget,
      '/debug':     proxyTarget,
      '/health':    proxyTarget,
    }
  }
})
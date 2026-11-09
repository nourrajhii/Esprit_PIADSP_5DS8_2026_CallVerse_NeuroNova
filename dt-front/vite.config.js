import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Le proxy redirige /api vers le backend (FastAPI / Express...) pendant le dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '^/api/': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})

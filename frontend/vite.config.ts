import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forwards to the FastAPI backend during `npm run dev` so the app can
      // call same-origin `/api/...` paths without worrying about CORS or a
      // hardcoded backend URL. Override the target with VITE_API_PROXY_TARGET
      // if the backend isn't on the default localhost:8000.
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

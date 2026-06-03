import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite dev proxy forwards /api/* to the Frappe dev server so the React app can
// call relative API URLs (no CORS configuration needed in dev). For production,
// set VITE_FRAPPE_BASE_URL to an absolute origin and the proxy is unused.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const frappeTarget = env.VITE_FRAPPE_PROXY_TARGET || 'http://iranrobot.localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': {
          target: frappeTarget,
          changeOrigin: true,
        },
      },
    },
  }
})

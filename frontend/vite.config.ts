import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // In dev, /api calls go to the Django backend. Override with VITE_API_URL when deployed.
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: { environment: 'jsdom' },
})

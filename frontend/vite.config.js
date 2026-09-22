import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  html: { cspNonce: 'VITE_CSP_NONCE' },
})

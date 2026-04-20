import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/model': 'http://127.0.0.1:8000',
      '/presets': 'http://127.0.0.1:8000',
      '/simulate': 'http://127.0.0.1:8000',
      '/compare': 'http://127.0.0.1:8000',
    },
  },
})

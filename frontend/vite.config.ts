/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/testes/preparo.ts'],
    coverage: { provider: 'v8', include: ['src/**/*.{ts,tsx}'] },
  },
})

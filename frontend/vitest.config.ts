import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Unit and component tests. Every backend call is mocked: no test reaches
// the API or spends a SerpApi credit.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})

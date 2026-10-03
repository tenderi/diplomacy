import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      // App code only: not the tests themselves, and not the shadcn/ui primitives
      // (vendored Radix wrappers, tested upstream).
      exclude: ['src/test/**', '**/*.d.ts', '**/*.config.*', '**/*.test.{ts,tsx}', 'src/components/ui/**', 'src/main.tsx'],
      // A few points under today's numbers: room to delete dead code, not to lose tests.
      // Measured with vitest 4's AST-aware v8 remapping, which counts only executable
      // code (not JSX markup, imports or type-only lines): lines 89.97, statements 86.49,
      // functions 85.61, branches 79.61.
      thresholds: { lines: 87, statements: 84, functions: 83, branches: 77 },
    },
  },
  server: {
    port: 5173,
    // Proxy only /api so that SPA routes (/games, /games/123, etc.) are served by Vite and refresh/back work
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})

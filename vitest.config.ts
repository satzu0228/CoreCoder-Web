import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/frontend/**/*.test.ts'],
    setupFiles: ['tests/frontend/setup.ts'],
  },
  resolve: {
    alias: { '@': new URL('src', import.meta.url).pathname },
  },
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  root: 'src',
  build: {
    outDir: resolve(__dirname, 'corecoder/web/static/dist'),
    emptyOutDir: true,
  },
})

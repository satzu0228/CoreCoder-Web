import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { create } from 'naive-ui'
import 'vfonts/Lato.css'
import App from './App.vue'

const app = createApp(App)
const naive = create({})

app.use(createPinia())
app.use(naive)
app.mount('#app')

// ── 全局错误处理 ──────────────────────────────────────────────

app.config.errorHandler = (err: unknown, _instance, info: string) => {
  const message = err instanceof Error ? err.message : String(err)
  console.error(`[vue-error] ${info}: ${message}`, err)
}

app.config.warnHandler = (msg: string, _instance, _trace: string) => {
  if (msg.includes('Hydration') || msg.includes('non-matching selector')) return
  console.warn(`[vue-warn] ${msg}`)
}

window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
  const message = event.reason instanceof Error ? event.reason.message : String(event.reason)
  console.error('[unhandled-rejection]', event.reason)
  // Attempt to surface via store notice banner
  try {
    // Pinia stores are available globally after app.mount via getActivePinia
    import('./stores/chatStore').then(({ useChatStore }) => {
      useChatStore().notice = `未处理的异步错误: ${message}`
    }).catch(() => { /* store not available */ })
  } catch { /* ignore */ }
})

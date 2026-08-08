<template>
  <div id="app" class="app-shell">
    <SessionSidebar />
    <ChatPanel />
    <div v-if="booting" class="boot-screen"><span class="boot-mark">C</span><p>正在打开工作空间…</p></div>
    <ConfirmModal />
    <DiffViewerModal />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import DiffViewerModal from './components/DiffViewerModal.vue'
import SessionSidebar from './components/SessionSidebar.vue'
import { useAgentStream } from './composables/useAgentStream'
import { useChatStore } from './stores/chatStore'
import './style.css'

const store = useChatStore()
const { initializeSessions } = useAgentStream()
const booting = ref(true)

onMounted(async () => {
  const params = new URLSearchParams(location.search)
  const urlToken = params.get('token')
  store.token = urlToken || sessionStorage.getItem('corecoder-token') || ''
  if (urlToken) sessionStorage.setItem('corecoder-token', urlToken)
  if (params.has('token')) {
    params.delete('token')
    const query = params.toString()
    history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}${location.hash}`)
  }
  try {
    await initializeSessions()
  } catch (error) {
    store.notice = error instanceof Error ? error.message : '无法打开工作空间'
  } finally {
    booting.value = false
  }
})
</script>

<style scoped>
.app-shell { width: 100%; height: 100dvh; display: flex; overflow: hidden; background: #f5f7fa; }
.boot-screen { position: fixed; inset: 0; z-index: 100; display: grid; place-content: center; justify-items: center; background: #f5f7fa; color: #7d8998; font-size: 12px; }
.boot-mark { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; background: #17202a; color: #fff; font: 700 15px Consolas, monospace; }
</style>

<template>
  <div id="app" class="w-full h-dvh flex overflow-hidden bg-brand-50">
    <SessionSidebar />
    <ChatPanel />
    <div v-if="booting" class="fixed inset-0 z-[100] grid place-content-center justify-items-center bg-brand-50 text-brand-500 text-xs">
      <span class="w-[42px] h-[42px] grid place-items-center rounded-xl bg-brand-950 text-white font-bold text-[15px] font-mono">C</span>
      <p>正在打开工作空间…</p>
    </div>
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

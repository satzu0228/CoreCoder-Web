<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <div class="max-w-4xl mx-auto py-8 px-4">
      <h1 class="text-3xl font-bold mb-6 text-center text-gray-900">CoreCoder Web</h1>
      <ChatPanel />
    </div>
    <ConfirmModal />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from './stores/chatStore'
import { useAgentStream } from './composables/useAgentStream'
import ChatPanel from './components/ChatPanel.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import './style.css'

const store = useChatStore()
const { checkPendingConfirm } = useAgentStream()

onMounted(async () => {
  // Extract token from URL query params
  const params = new URLSearchParams(location.search)
  const token = params.get('token') || ''
  store.token = token

  // Check for any pending confirmation to restore after page reload
  await checkPendingConfirm()
})
</script>

<template>
  <div id="app" class="app-container">
    <div class="workspace-layout">
      <div class="sidebar">
        <FileTree :token="store.token" @file-selected="onFileSelected" />
      </div>
      <div class="main-content">
        <ChatPanel />
      </div>
    </div>
    <ConfirmModal />
    <DiffViewerModal />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from './stores/chatStore'
import { useAgentStream } from './composables/useAgentStream'
import ChatPanel from './components/ChatPanel.vue'
import FileTree from './components/FileTree.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import DiffViewerModal from './components/DiffViewerModal.vue'
import './style.css'

const store = useChatStore()
const { checkPendingConfirm } = useAgentStream()

const onFileSelected = (file: { path: string; content: string }) => {
  // 点击文件树的文件时，可以在这里处理预览逻辑
  // 目前只是选中状态，实际预览可以在后续版本中加
  console.log('Selected file:', file.path)
}

onMounted(async () => {
  // Extract token from URL query params
  const params = new URLSearchParams(location.search)
  const token = params.get('token') || ''
  store.token = token

  // Check for any pending confirmation to restore after page reload
  await checkPendingConfirm()
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  background: #fafafa;
}

.workspace-layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 250px;
  background: white;
  border-right: 1px solid #e0e0e0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>

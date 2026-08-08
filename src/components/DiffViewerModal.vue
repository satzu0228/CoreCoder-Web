<template>
  <Teleport to="body">
    <div v-if="store.diffViewerOpen" class="diff-modal-overlay" @click="close">
      <div class="diff-modal" @click.stop>
        <div class="modal-header">
          <div><span>文件变更</span><h3>{{ store.diffViewerData.fileName }}</h3></div>
          <button @click="close" class="close-btn" aria-label="关闭 diff">×</button>
        </div>
        <div class="modal-body">
          <DiffViewer
            :old-content="store.diffViewerData.oldContent"
            :new-content="store.diffViewerData.newContent"
            :file-name="store.diffViewerData.fileName"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useChatStore } from '../stores/chatStore'
import DiffViewer from './DiffViewer.vue'

const store = useChatStore()

const close = () => {
  store.closeDiffViewer()
}
</script>

<style scoped>
.diff-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(20, 29, 40, 0.52);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.diff-modal {
  background: white;
  border: 1px solid rgba(255,255,255,.35);
  border-radius: 15px;
  box-shadow: 0 28px 80px rgba(18,28,40,.27);
  width: 90%;
  max-width: 1200px;
  height: 80vh;
  max-height: 800px;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 18px;
  border-bottom: 1px solid #e2e7ed;
}

.modal-header span { display: block; margin-bottom: 3px; color: #8793a2; font: 700 9px Consolas, monospace; letter-spacing: .09em; text-transform: uppercase; }
.modal-header h3 {
  margin: 0;
  color: #293748;
  font: 600 12px Consolas, monospace;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  color: #748093;
  padding: 4px;
}

.close-btn:hover {
  color: #000;
}

.modal-body {
  flex: 1;
  overflow: hidden;
}
</style>

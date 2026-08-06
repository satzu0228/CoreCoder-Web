<template>
  <Teleport to="body">
    <div v-if="store.diffViewerOpen" class="diff-modal-overlay" @click="close">
      <div class="diff-modal" @click.stop>
        <div class="modal-header">
          <h3>View Changes - {{ store.diffViewerData.fileName }}</h3>
          <button @click="close" class="close-btn">✕</button>
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
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.diff-modal {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
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
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  color: #666;
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

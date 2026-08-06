<template>
  <div v-if="store.pendingConfirm" class="confirm-modal-overlay">
    <div class="confirm-modal">
      <div class="modal-header">
        <h3>{{ title }}</h3>
        <button @click="handleReject" class="close-btn">✕</button>
      </div>

      <div class="modal-content">
        <div v-if="store.pendingConfirm.action === 'edit_file'">
          <p class="label">File:</p>
          <code class="path">{{ store.pendingConfirm.file_path }}</code>
          <p class="label" style="margin-top: 12px">Changes:</p>
          <pre class="diff-preview">{{ store.pendingConfirm.diff }}</pre>
          <button @click="openDiffViewer" class="view-diff-btn">
            View Full Diff (Monaco)
          </button>
        </div>

        <div v-if="store.pendingConfirm.action === 'bash'">
          <p class="label">Command:</p>
          <code class="command">{{ store.pendingConfirm.command }}</code>
          <p v-if="store.pendingConfirm.reason" class="label" style="margin-top: 12px">
            Reason:
          </p>
          <p v-if="store.pendingConfirm.reason" class="reason">
            {{ store.pendingConfirm.reason }}
          </p>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="handleApprove" :disabled="isSubmitting" class="btn-approve">
          {{ isSubmitting ? 'Submitting...' : 'Approve' }}
        </button>
        <button @click="handleReject" :disabled="isSubmitting" class="btn-reject">
          {{ isSubmitting ? 'Submitting...' : 'Reject' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useChatStore } from '../stores/chatStore'
import { useAgentStream } from '../composables/useAgentStream'

const store = useChatStore()
const { submitConfirm } = useAgentStream()
const isSubmitting = ref(false)

const title = computed(() => {
  if (store.pendingConfirm?.action === 'edit_file') return 'Confirm Edit'
  if (store.pendingConfirm?.action === 'bash') return 'Confirm Command'
  return 'Confirm Action'
})

// Use full old/new content from the backend when available.
// Fall back to reconstructing from unified diff for backward compat.
const oldFileContent = computed(() => {
  if (store.pendingConfirm?.old_content) return store.pendingConfirm.old_content
  if (!store.pendingConfirm?.diff) return ''
  const lines = store.pendingConfirm.diff.split('\n')
  return lines
    .filter(line => line.startsWith('-') && !line.startsWith('---'))
    .map(line => line.slice(1))
    .join('\n')
})

const newFileContent = computed(() => {
  if (store.pendingConfirm?.new_content) return store.pendingConfirm.new_content
  if (!store.pendingConfirm?.diff) return ''
  const lines = store.pendingConfirm.diff.split('\n')
  return lines
    .filter(line => line.startsWith('+') && !line.startsWith('+++'))
    .map(line => line.slice(1))
    .join('\n')
})

const openDiffViewer = async () => {
  // Use store method to open diff viewer
  store.openDiffViewer(
    store.pendingConfirm?.file_path || 'file.txt',
    oldFileContent.value,
    newFileContent.value
  )
}

async function handleApprove() {
  console.log('handleApprove clicked')
  isSubmitting.value = true
  try {
    await submitConfirm(true)
  } catch (err) {
    console.error('Approve failed:', err)
  } finally {
    isSubmitting.value = false
  }
}

async function handleReject() {
  console.log('handleReject clicked')
  isSubmitting.value = true
  try {
    await submitConfirm(false)
  } catch (err) {
    console.error('Reject failed:', err)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.confirm-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-modal {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  max-width: 700px;
  width: 90%;
  max-height: 90vh;
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

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.label {
  font-weight: 600;
  font-size: 14px;
  margin: 0 0 8px 0;
}

.path {
  display: block;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
  overflow-x: auto;
  word-break: break-all;
}

.command {
  display: block;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
  overflow-x: auto;
  word-break: break-all;
}

.reason {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.diff-preview {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
  margin: 8px 0;
  border: 1px solid #e0e0e0;
}

.view-diff-btn {
  background: #0066cc;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  margin-top: 12px;
}

.view-diff-btn:hover {
  background: #0052a3;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid #e0e0e0;
  background: #f9f9f9;
}

.btn-approve {
  background: #4CAF50;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.btn-approve:hover:not(:disabled) {
  background: #45a049;
}

.btn-approve:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-reject {
  background: #f44336;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.btn-reject:hover:not(:disabled) {
  background: #da190b;
}

.btn-reject:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>

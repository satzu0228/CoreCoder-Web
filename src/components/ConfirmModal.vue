<template>
  <div v-if="store.pendingConfirm" class="confirm-modal-overlay">
    <div class="confirm-modal">
      <div class="modal-header">
        <h3>{{ title }}</h3>
        <button @click="handleReject" class="close-btn" aria-label="拒绝并关闭">×</button>
      </div>

      <div class="modal-content">
        <div v-if="store.pendingConfirm.action === 'edit_file' || store.pendingConfirm.action === 'write_file'">
          <p class="label">文件</p>
          <code class="path">{{ store.pendingConfirm.file_path }}</code>
          <p class="label" style="margin-top: 16px">变更摘要</p>
          <pre class="diff-preview">{{ store.pendingConfirm.diff }}</pre>
          <button @click="openDiffViewer" class="view-diff-btn">
            查看完整 diff
          </button>
        </div>

        <div v-if="store.pendingConfirm.action === 'bash'">
          <p class="label">命令</p>
          <code class="command">{{ store.pendingConfirm.command }}</code>
          <p v-if="store.pendingConfirm.reason" class="label" style="margin-top: 12px">
            风险原因
          </p>
          <p v-if="store.pendingConfirm.reason" class="reason">
            {{ store.pendingConfirm.reason }}
          </p>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="handleApprove" :disabled="isSubmitting" class="btn-approve">
          {{ isSubmitting ? '处理中…' : '允许执行' }}
        </button>
        <button @click="handleReject" :disabled="isSubmitting" class="btn-reject">
          {{ isSubmitting ? '处理中…' : '拒绝' }}
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
  if (store.pendingConfirm?.action === 'edit_file') return '确认文件修改'
  if (store.pendingConfirm?.action === 'write_file') return '确认写入文件'
  if (store.pendingConfirm?.action === 'bash') return '确认运行命令'
  return '确认操作'
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
  inset: 0;
  background: rgba(20, 29, 40, 0.48);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-modal {
  background: #fff;
  border: 1px solid rgba(255,255,255,.5);
  border-radius: 16px;
  box-shadow: 0 24px 70px rgba(19, 29, 42, 0.24);
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
  padding: 20px 22px;
  border-bottom: 1px solid #e5eaf0;
}

.modal-header h3 {
  margin: 0;
  color: #202b38;
  font-size: 15px;
  font-weight: 700;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 20px;
  color: #7d8999;
  padding: 4px;
}

.close-btn:hover {
  color: #000;
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
}

.label {
  color: #6f7d8f;
  font: 700 10px Consolas, monospace;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin: 0 0 8px 0;
}

.path,
.command {
  display: block;
  background: #f5f7fa;
  padding: 11px 12px;
  border: 1px solid #e1e7ee;
  border-radius: 8px;
  color: #354356;
  font: 12px/1.5 Consolas, monospace;
  overflow-x: auto;
  word-break: break-all;
}

.reason {
  font-size: 14px;
  color: #69778a;
  margin: 0;
}

.diff-preview {
  background: #17202a;
  color: #d9e2ec;
  padding: 12px;
  border-radius: 9px;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
  margin: 8px 0;
  border: 1px solid #283545;
}

.view-diff-btn {
  background: transparent;
  color: #3767d6;
  border: 1px solid #b9c9e9;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  margin-top: 12px;
}

.view-diff-btn:hover {
  background: #eef3ff;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 22px 20px;
  border-top: 1px solid #e5eaf0;
  background: #fafbfd;
}

.btn-approve {
  background: #263343;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.btn-approve:hover:not(:disabled) {
  background: #3767d6;
}

.btn-approve:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-reject {
  background: #fff;
  color: #59687b;
  border: 1px solid #d4dce5;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.btn-reject:hover:not(:disabled) {
  border-color: #e0baba;
  background: #fff3f3;
  color: #a53f3f;
}

.btn-reject:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>

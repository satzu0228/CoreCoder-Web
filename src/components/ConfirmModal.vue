<template>
  <div v-if="store.pendingConfirm" class="fixed inset-0 z-[1000] flex items-center justify-center bg-brand-950/50 backdrop-blur-sm">
    <div class="bg-white border border-white/50 rounded-2xl shadow-2xl max-w-[700px] w-[90%] max-h-[90vh] flex flex-col">
      <div class="flex justify-between items-center py-5 px-[22px] border-b border-brand-200">
        <h3 class="m-0 text-brand-900 text-[15px] font-bold">{{ title }}</h3>
        <button @click="handleReject" class="bg-transparent border-0 cursor-pointer text-xl text-brand-500 p-1 hover:text-black" aria-label="拒绝并关闭">×</button>
      </div>

      <div class="flex-1 overflow-y-auto p-[22px]">
        <div v-if="store.pendingConfirm.action === 'edit_file' || store.pendingConfirm.action === 'write_file'">
          <p class="text-brand-600 font-bold text-[10px] font-mono tracking-wider uppercase mb-2">文件</p>
          <code class="block bg-brand-50 py-[11px] px-3 border border-brand-200 rounded-lg text-brand-800 text-xs font-mono overflow-x-auto break-all">{{ store.pendingConfirm.file_path }}</code>
          <p class="text-brand-600 font-bold text-[10px] font-mono tracking-wider uppercase mt-4 mb-2">变更摘要</p>
          <pre class="bg-brand-950 text-brand-200 p-3 rounded-lg text-xs max-h-[300px] overflow-y-auto my-2 border border-brand-800">{{ store.pendingConfirm.diff }}</pre>
          <button @click="openDiffViewer" class="bg-transparent text-primary-500 border border-primary-200 py-2 px-3 rounded-lg cursor-pointer text-[13px] font-semibold mt-3 hover:bg-primary-50">
            查看完整 diff
          </button>
        </div>

        <div v-if="store.pendingConfirm.action === 'bash'">
          <p class="text-brand-600 font-bold text-[10px] font-mono tracking-wider uppercase mb-2">命令</p>
          <code class="block bg-brand-50 py-[11px] px-3 border border-brand-200 rounded-lg text-brand-800 text-xs font-mono overflow-x-auto break-all">{{ store.pendingConfirm.command }}</code>
          <p v-if="store.pendingConfirm.reason" class="text-brand-600 font-bold text-[10px] font-mono tracking-wider uppercase mt-3 mb-2">风险原因</p>
          <p v-if="store.pendingConfirm.reason" class="text-sm text-brand-600 m-0">{{ store.pendingConfirm.reason }}</p>
        </div>
      </div>

      <div class="flex justify-end gap-2 py-4 px-[22px] pb-5 border-t border-brand-200 bg-brand-50/80">
        <button @click="handleApprove" :disabled="isSubmitting" class="bg-brand-950 text-white border-0 py-2 px-4 rounded-lg cursor-pointer text-sm font-semibold hover:bg-primary-500 disabled:bg-gray-300 disabled:cursor-not-allowed">
          {{ isSubmitting ? '处理中…' : '允许执行' }}
        </button>
        <button @click="handleReject" :disabled="isSubmitting" class="bg-white text-brand-700 border border-brand-300 py-2 px-4 rounded-lg cursor-pointer text-sm font-semibold hover:border-danger-border hover:bg-danger-light hover:text-danger-dark disabled:bg-gray-300 disabled:cursor-not-allowed">
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

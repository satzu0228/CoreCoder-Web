<template>
  <n-modal
    v-if="store.pendingConfirm"
    :show="!!store.pendingConfirm"
    :mask-closable="false"
    preset="dialog"
    :title="title"
    positive-text="Approve"
    negative-text="Reject"
    @positive-click="approve"
    @negative-click="reject"
  >
    <template #default>
      <div class="space-y-3">
        <div v-if="store.pendingConfirm.action === 'edit_file'">
          <p class="font-semibold text-sm">File:</p>
          <code class="text-xs">{{ store.pendingConfirm.file_path }}</code>
        </div>
        <div v-if="store.pendingConfirm.action === 'bash'">
          <p class="font-semibold text-sm">Command:</p>
          <code class="text-xs">{{ store.pendingConfirm.command }}</code>
        </div>
        <div v-if="store.pendingConfirm.reason">
          <p class="font-semibold text-sm">Reason:</p>
          <p class="text-sm text-gray-700">{{ store.pendingConfirm.reason }}</p>
        </div>
        <div v-if="store.pendingConfirm.diff">
          <p class="font-semibold text-sm">Changes:</p>
          <pre class="text-xs bg-gray-100 p-2 rounded max-h-80 overflow-y-auto">{{ store.pendingConfirm.diff }}</pre>
        </div>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NModal } from 'naive-ui'
import { useChatStore } from '../stores/chatStore'
import { useAgentStream } from '../composables/useAgentStream'

const store = useChatStore()
const { submitConfirm } = useAgentStream()

const title = computed(() => {
  if (store.pendingConfirm?.action === 'edit_file') return 'Confirm Edit'
  if (store.pendingConfirm?.action === 'bash') return 'Confirm Command'
  return 'Confirm Action'
})

async function approve() {
  await submitConfirm(true)
}

async function reject() {
  await submitConfirm(false)
}
</script>

<template>
  <li class="tool-card" :class="toolCall.status === 'running' ? 'border-amber-400 bg-amber-50' : 'border-green-400 bg-green-50'">
    <div class="flex items-center gap-2 font-semibold">
      <span :class="toolCall.status === 'running' ? 'bg-amber-400' : 'bg-green-400'" class="text-white text-xs px-1.5 py-0.5 rounded-full">
        {{ toolCall.status }}
      </span>
      <span>{{ toolCall.name }}</span>
    </div>
    <div v-if="toolCall.args" class="text-gray-600 text-xs mt-1 overflow-hidden text-ellipsis whitespace-nowrap">
      {{ formatArgs(toolCall.args) }}
    </div>
    <div v-if="toolCall.status === 'done' && toolCall.result" class="mt-2">
      <button
        @click="toggleResult"
        class="text-xs text-blue-600 hover:text-blue-800 bg-none border-none p-0 cursor-pointer"
      >
        {{ showResult ? '▼ hide result' : '▶ show result' }}
      </button>
      <pre v-if="showResult" class="mt-2 text-xs bg-gray-100 p-2 rounded max-h-32 overflow-y-auto">{{ toolCall.result }}</pre>
    </div>
  </li>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ToolCall } from '../stores/chatStore'

defineProps<{
  toolCall: ToolCall
}>()

const showResult = ref(false)

function toggleResult() {
  showResult.value = !showResult.value
}

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => `${k}: ${JSON.stringify(v).slice(0, 80)}`)
    .join('  ')
}
</script>

<style scoped>
.tool-card {
  @apply flex flex-col border rounded-md p-3 mb-1 text-sm bg-gray-50 border-gray-300;
}
</style>

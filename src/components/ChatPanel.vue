<template>
  <div class="flex flex-col h-screen max-w-4xl mx-auto px-4">
    <div class="flex-1 overflow-y-auto border border-gray-300 rounded-lg p-3 mb-4 bg-white">
      <div v-for="msg in store.messages" :key="msg.id" class="mb-4">
        <div v-if="msg.role === 'user'" class="text-gray-700">
          <span class="font-semibold">You:</span> {{ msg.content }}
        </div>
        <div v-else class="text-gray-900">
          <span class="font-semibold">Agent:</span> {{ msg.content }}
          <ul v-if="msg.toolCalls?.length" class="ml-4 mt-2 space-y-1">
            <ToolCallCard
              v-for="toolId in msg.toolCalls.map(tc => tc.id)"
              :key="toolId"
              :tool-call="store.toolCalls.get(toolId)!"
            />
          </ul>
        </div>
      </div>
    </div>
    <form @submit.prevent="handleSubmit" class="flex gap-2">
      <input
        v-model="inputText"
        type="text"
        placeholder="Ask CoreCoder to do something..."
        :disabled="isLoading"
        autocomplete="off"
        class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
      />
      <button
        type="submit"
        :disabled="isLoading"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
      >
        Send
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../stores/chatStore'
import { useAgentStream } from '../composables/useAgentStream'
import ToolCallCard from './ToolCallCard.vue'

const store = useChatStore()
const { sendMessage } = useAgentStream()
const inputText = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  inputText.value = ''
  isLoading.value = true
  try {
    await sendMessage(text)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="chat-panel">
    <div class="messages-area">
      <div v-for="msg in store.messages" :key="msg.id" class="message">
        <div v-if="msg.role === 'user'" class="user-message">
          <span class="role">You:</span> {{ msg.content }}
        </div>
        <div v-else class="agent-message">
          <span class="role">Agent:</span> {{ msg.content }}
          <ul v-if="msg.toolCalls?.length" class="tool-calls">
            <ToolCallCard
              v-for="toolId in msg.toolCalls.map(tc => tc.id)"
              :key="toolId"
              :tool-call="store.toolCalls.get(toolId)!"
            />
          </ul>
        </div>
      </div>
    </div>
    <form @submit.prevent="handleSubmit" class="input-form">
      <input
        v-model="inputText"
        type="text"
        placeholder="Ask CoreCoder to do something..."
        :disabled="isLoading"
        autocomplete="off"
      />
      <button
        type="submit"
        :disabled="isLoading"
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

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
}

.messages-area {
  flex: 1;
  min-height: 200px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: white;
}

.message {
  margin-bottom: 16px;
}

.user-message {
  color: #333;
  font-size: 14px;
}

.agent-message {
  color: #333;
  font-size: 14px;
}

.role {
  font-weight: 600;
}

.tool-calls {
  list-style: none;
  margin: 8px 0 0 0;
  padding: 0 0 0 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-form {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.input-form input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d0d0d0;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.input-form input:focus {
  border-color: #0066cc;
  box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
}

.input-form input:disabled {
  background: #f5f5f5;
  color: #999;
  cursor: not-allowed;
}

.input-form button {
  padding: 8px 16px;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  font-size: 14px;
  flex-shrink: 0;
}

.input-form button:hover:not(:disabled) {
  background: #0052a3;
}

.input-form button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>

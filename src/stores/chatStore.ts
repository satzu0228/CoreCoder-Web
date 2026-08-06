import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
}

export interface ToolCall {
  id: string
  name: string
  args?: Record<string, unknown>
  status: 'running' | 'done'
  result?: string
}

export interface ConfirmEvent {
  id: string
  action: 'edit_file' | 'bash'
  file_path?: string
  command?: string
  reason?: string
  diff?: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const token = ref<string>('')
  const pendingConfirm = ref<ConfirmEvent | null>(null)
  const toolCalls = ref<Map<string, ToolCall>>(new Map())

  const addMessage = (role: 'user' | 'assistant', content: string) => {
    messages.value.push({
      id: Date.now().toString(),
      role,
      content,
    })
  }

  const updateToolCall = (id: string, update: Partial<ToolCall>) => {
    const existing = toolCalls.value.get(id)
    if (existing) {
      toolCalls.value.set(id, { ...existing, ...update })
    }
  }

  const createToolCall = (id: string, name: string, args: Record<string, unknown>) => {
    toolCalls.value.set(id, { id, name, args, status: 'running' })
  }

  const resetMessages = () => {
    messages.value = []
    toolCalls.value.clear()
    pendingConfirm.value = null
  }

  const messageCount = computed(() => messages.value.length)

  return {
    messages,
    token,
    pendingConfirm,
    toolCalls,
    addMessage,
    updateToolCall,
    createToolCall,
    resetMessages,
    messageCount,
  }
})

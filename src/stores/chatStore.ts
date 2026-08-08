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
  action: 'edit_file' | 'write_file' | 'bash'
  file_path?: string
  command?: string
  reason?: string
  diff?: string
  old_content?: string
  new_content?: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const token = ref<string>('')
  const pendingConfirm = ref<ConfirmEvent | null>(null)
  const pendingConfirmRestored = ref(false)
  const toolCalls = ref<Map<string, ToolCall>>(new Map())
  const diffViewerOpen = ref(false)
  const diffViewerData = ref({
    fileName: '',
    oldContent: '',
    newContent: '',
  })

  const addMessage = (role: 'user' | 'assistant', content: string) => {
    messages.value.push({
      id: crypto.randomUUID(),
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
    pendingConfirmRestored.value = false
  }

  const restoreMessages = (restored: Message[]) => {
    messages.value = restored
    toolCalls.value.clear()
    for (const message of restored) {
      for (const toolCall of message.toolCalls || []) {
        toolCalls.value.set(toolCall.id, toolCall)
      }
    }
  }

  const openDiffViewer = (fileName: string, oldContent: string, newContent: string) => {
    diffViewerData.value = { fileName, oldContent, newContent }
    diffViewerOpen.value = true
  }

  const closeDiffViewer = () => {
    diffViewerOpen.value = false
  }

  const messageCount = computed(() => messages.value.length)

  return {
    messages,
    token,
    pendingConfirm,
    pendingConfirmRestored,
    toolCalls,
    diffViewerOpen,
    diffViewerData,
    addMessage,
    updateToolCall,
    createToolCall,
    resetMessages,
    restoreMessages,
    openDiffViewer,
    closeDiffViewer,
    messageCount,
  }
})

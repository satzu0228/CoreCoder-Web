import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

export type SessionStatus = 'idle' | 'running' | 'waiting_confirmation' | 'cancelling' | 'cancelled' | 'interrupted' | 'error'

export interface SessionSummary {
  id: string
  title: string
  preview: string
  model: string
  status: SessionStatus
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
  isStreaming?: boolean
  statusText?: string
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
  session_id?: string
  file_path?: string
  command?: string
  reason?: string
  diff?: string
  old_content?: string
  new_content?: string
}

export const useChatStore = defineStore('chat', () => {
  const token = ref('')
  const workspaceName = ref('Workspace')
  const sessions = ref<SessionSummary[]>([])
  const activeSessionId = ref<string | null>(null)
  const runningSessionId = ref<string | null>(null)
  const messagesBySession = ref<Record<string, Message[]>>({})
  const pendingConfirm = ref<ConfirmEvent | null>(null)
  const pendingConfirmRestored = ref(false)
  const sidebarOpen = ref(false)
  const notice = ref('')
  const diffViewerOpen = ref(false)
  const diffViewerData = ref({ fileName: '', oldContent: '', newContent: '' })

  const activeSession = computed(() => sessions.value.find(item => item.id === activeSessionId.value) || null)
  const messages = computed(() => activeSessionId.value ? messagesBySession.value[activeSessionId.value] || [] : [])
  const isRunning = computed(() => runningSessionId.value !== null)

  function setMessages(sessionId: string, restored: Message[]) {
    messagesBySession.value[sessionId] = restored
  }

  function addMessage(sessionId: string, role: Message['role'], content: string): Message {
    const message = reactive<Message>({ id: crypto.randomUUID(), role, content })
    const current = messagesBySession.value[sessionId] || []
    messagesBySession.value[sessionId] = [...current, message]
    return message
  }

  function updateSession(sessionId: string, update: Partial<SessionSummary>) {
    const session = sessions.value.find(item => item.id === sessionId)
    if (session) Object.assign(session, update)
  }

  function openDiffViewer(fileName: string, oldContent: string, newContent: string) {
    diffViewerData.value = { fileName, oldContent, newContent }
    diffViewerOpen.value = true
  }

  return {
    token,
    workspaceName,
    sessions,
    activeSessionId,
    activeSession,
    runningSessionId,
    messagesBySession,
    messages,
    pendingConfirm,
    pendingConfirmRestored,
    sidebarOpen,
    notice,
    isRunning,
    diffViewerOpen,
    diffViewerData,
    setMessages,
    addMessage,
    updateSession,
    openDiffViewer,
    closeDiffViewer: () => { diffViewerOpen.value = false },
  }
})

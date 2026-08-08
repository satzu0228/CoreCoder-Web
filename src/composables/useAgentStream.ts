import { useChatStore } from '../stores/chatStore'
import type { ConfirmEvent, Message, SessionSummary, SessionStatus, ToolCall } from '../stores/chatStore'

function errorText(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') return fallback
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message)
  return fallback
}

export function useAgentStream() {
  const store = useChatStore()
  let lastSequence = 0

  const headers = (json = false) => ({
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    'X-CoreCoder-Token': store.token,
  })

  async function refreshSessions() {
    const response = await fetch('/api/sessions', { headers: headers() })
    if (!response.ok) throw new Error(`无法读取对话列表（${response.status}）`)
    const data = await response.json()
    store.workspaceName = data.workspace?.name || 'Workspace'
    store.sessions = (data.sessions || []) as SessionSummary[]
    store.runningSessionId = data.running_session_id || null
  }

  async function loadSession(sessionId: string) {
    const response = await fetch(`/api/sessions/${sessionId}`, { headers: headers() })
    if (!response.ok) throw new Error(`无法打开对话（${response.status}）`)
    const data = await response.json()
    store.setMessages(sessionId, (data.messages || []) as Message[])
    store.updateSession(sessionId, data.session || {})
  }

  async function selectSession(sessionId: string) {
    store.activeSessionId = sessionId
    if (store.pendingConfirm?.session_id !== sessionId) {
      store.pendingConfirm = null
      store.pendingConfirmRestored = false
    }
    store.sidebarOpen = false
    localStorage.setItem('corecoder-active-session', sessionId)
    store.notice = ''
    await loadSession(sessionId)
    await checkPendingConfirm(sessionId)
  }

  async function createSession() {
    const response = await fetch('/api/sessions', { method: 'POST', headers: headers() })
    if (!response.ok) throw new Error(`无法新建对话（${response.status}）`)
    const data = await response.json()
    store.sessions.unshift(data.session as SessionSummary)
    store.setMessages(data.session.id, [])
    await selectSession(data.session.id)
    return data.session as SessionSummary
  }

  async function initializeSessions() {
    await refreshSessions()
    if (!store.sessions.length) {
      await createSession()
      return
    }
    const saved = localStorage.getItem('corecoder-active-session')
    const initial = store.sessions.find(item => item.id === saved)?.id || store.sessions[0].id
    await selectSession(initial)
  }

  async function renameSession(sessionId: string, title: string) {
    const response = await fetch(`/api/sessions/${sessionId}`, {
      method: 'PATCH', headers: headers(true), body: JSON.stringify({ title }),
    })
    if (!response.ok) throw new Error(`无法重命名对话（${response.status}）`)
    const data = await response.json()
    store.updateSession(sessionId, data.session)
  }

  async function deleteSession(sessionId: string) {
    const response = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE', headers: headers() })
    if (!response.ok) {
      const data = await response.json().catch(() => null)
      throw new Error(errorText(data, `无法删除对话（${response.status}）`))
    }
    delete store.messagesBySession[sessionId]
    store.sessions = store.sessions.filter(item => item.id !== sessionId)
    if (store.activeSessionId === sessionId) {
      if (store.sessions.length) await selectSession(store.sessions[0].id)
      else await createSession()
    }
  }

  async function checkPendingConfirm(sessionId = store.activeSessionId) {
    if (!sessionId) return
    try {
      const response = await fetch(`/api/sessions/${sessionId}/pending`, { headers: headers() })
      if (!response.ok) return
      const data = await response.json()
      if (data.pending) {
        store.pendingConfirm = { ...data.pending, session_id: sessionId } as ConfirmEvent
        store.pendingConfirmRestored = true
      } else if (store.pendingConfirm?.session_id === sessionId) {
        store.pendingConfirm = null
      }
    } catch (error) {
      console.error('Failed to restore confirmation:', error)
    }
  }

  async function followRestoredRun(sessionId: string) {
    for (let attempt = 0; attempt < 75; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 400))
      await refreshSessions()
      const status = store.sessions.find(item => item.id === sessionId)?.status
      if (status !== 'running' && status !== 'waiting_confirmation') {
        await loadSession(sessionId)
        return
      }
    }
  }

  async function sendMessage(message: string) {
    const sessionId = store.activeSessionId
    if (!sessionId) return
    store.notice = ''
    store.addMessage(sessionId, 'user', message)
    const assistant = store.addMessage(sessionId, 'assistant', '')
    assistant.isStreaming = true
    assistant.statusText = '正在连接模型'
    store.runningSessionId = sessionId
    store.updateSession(sessionId, { status: 'running' })
    const requestStartedAt = Date.now()
    let hasStreamActivity = false
    const waitingTimer = window.setInterval(() => {
      if (hasStreamActivity || assistant.toolCalls?.length || assistant.content) return
      const elapsed = Math.max(1, Math.floor((Date.now() - requestStartedAt) / 1000))
      if (elapsed < 2) assistant.statusText = '正在连接模型'
      else if (elapsed < 8) assistant.statusText = `等待模型响应 · ${elapsed}s`
      else if (elapsed < 20) assistant.statusText = `模型正在处理上下文 · ${elapsed}s`
      else assistant.statusText = `任务较复杂，模型仍在处理 · ${elapsed}s`
    }, 1000)

    function stopWaitingTimer() {
      window.clearInterval(waitingTimer)
    }

    let response: Response
    try {
      response = await fetch(`/api/sessions/${sessionId}/chat`, {
        method: 'POST', headers: headers(true), body: JSON.stringify({ message }),
      })
    } catch (error) {
      stopWaitingTimer()
      assistant.content = '无法连接到 CoreCoder 服务。请确认服务仍在运行后重试。'
      assistant.isStreaming = false
      store.runningSessionId = null
      store.updateSession(sessionId, { status: 'error' })
      return
    }
    if (!response.ok) {
      stopWaitingTimer()
      const data = await response.json().catch(() => null)
      assistant.content = errorText(data, `请求失败（${response.status}）`)
      assistant.isStreaming = false
      store.runningSessionId = null
      store.updateSession(sessionId, { status: 'error' })
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      stopWaitingTimer()
      assistant.content = '浏览器无法读取流式响应，请刷新后重试。'
      assistant.isStreaming = false
      store.runningSessionId = null
      store.updateSession(sessionId, { status: 'error' })
      return
    }
    const decoder = new TextDecoder()
    let buffer = ''
    let completeText = ''
    let streamCompleted = false
    const characterQueue: string[] = []
    let queueIndex = 0
    let typing = false
    let streamEnded = false
    let resolveTyping: () => void = () => undefined
    let typingResolved = false
    const typingFinished = new Promise<void>(resolve => { resolveTyping = resolve })

    function markTypingFinished() {
      if (typingResolved) return
      typingResolved = true
      resolveTyping()
    }

    function finishTypingIfReady() {
      if (streamEnded && queueIndex >= characterQueue.length) {
        assistant.isStreaming = false
        markTypingFinished()
      }
    }

    function typeNextCharacter() {
      if (queueIndex >= characterQueue.length) {
        typing = false
        finishTypingIfReady()
        return
      }
      assistant.content += characterQueue[queueIndex]
      queueIndex += 1
      window.setTimeout(typeNextCharacter, 11)
    }

    function enqueueText(text: string) {
      completeText += text
      characterQueue.push(...Array.from(text))
      if (!typing) {
        typing = true
        typeNextCharacter()
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() || ''
        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue
          const event = JSON.parse(frame.slice(6))
          if (event.session_id && event.session_id !== sessionId) continue
          // Track sequence for recovery
          if (typeof event.sequence === 'number' && event.sequence > lastSequence) {
            lastSequence = event.sequence
          }
          if (event.type === 'token') {
            hasStreamActivity = true
            assistant.statusText = '正在生成回复'
            enqueueText(event.text)
          } else if (event.type === 'tool_start') {
            hasStreamActivity = true
            assistant.statusText = ''
            const tool: ToolCall = { id: event.id, name: event.name, args: event.args || {}, status: 'running' }
            assistant.toolCalls = [...(assistant.toolCalls || []), tool]
          } else if (event.type === 'tool_end') {
            const tool = assistant.toolCalls?.find(item => item.id === event.id)
            if (tool) Object.assign(tool, { status: 'done', result: event.result || '' })
          } else if (event.type === 'confirm_required') {
            hasStreamActivity = true
            assistant.statusText = '等待确认'
            store.pendingConfirm = { ...event, session_id: sessionId } as ConfirmEvent
            store.pendingConfirmRestored = false
            store.updateSession(sessionId, { status: 'waiting_confirmation' })
            store.activeSessionId = sessionId
            localStorage.setItem('corecoder-active-session', sessionId)
          } else if (event.type === 'error') {
            hasStreamActivity = true
            enqueueText(`${completeText ? '\n\n' : ''}运行失败：${event.message}`)
            store.updateSession(sessionId, { status: 'error' })
          } else if (event.type === 'status' && !hasStreamActivity) {
            assistant.statusText = event.message || '等待模型响应'
          } else if (event.type === 'done') {
            streamCompleted = true
          }
        }
      }
    } catch (error) {
      store.notice = '连接已中断，正在尝试重连…'
      if (store.runningSessionId === sessionId) {
        await reconnectStream(sessionId)
      }
    } finally {
      stopWaitingTimer()
      reader.releaseLock()
      streamEnded = true
      finishTypingIfReady()
      await typingFinished
      await refreshSessions().catch(() => undefined)
      if (streamCompleted) await loadSession(sessionId).catch(() => undefined)
    }
  }

  async function reconnectStream(sessionId: string) {
    // Find the current streaming assistant message
    const msgs = store.messagesBySession[sessionId]
    if (!msgs) return
    const assistant = [...msgs].reverse().find(m => m.role === 'assistant')
    if (!assistant) return

    assistant.isStreaming = true
    assistant.statusText = '正在重连…'

    let response: Response
    try {
      response = await fetch(
        `/api/sessions/${sessionId}/events?after=${lastSequence}`,
        { headers: headers() },
      )
    } catch {
      store.notice = '重连失败，对话可能仍在后台运行，刷新可恢复。'
      assistant.isStreaming = false
      return
    }
    if (!response.ok) {
      store.notice = `重连失败（${response.status}），刷新可恢复。`
      assistant.isStreaming = false
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      assistant.isStreaming = false
      store.notice = '重连失败，请刷新页面。'
      return
    }
    const decoder = new TextDecoder()
    let buffer = ''
    const knownToolIds = new Set((assistant.toolCalls || []).map(t => t.id))

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() || ''
        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue
          const event = JSON.parse(frame.slice(6))
          if (event.session_id && event.session_id !== sessionId) continue
          if (typeof event.sequence === 'number' && event.sequence > lastSequence) {
            lastSequence = event.sequence
          }

          if (event.type === 'token') {
            assistant.statusText = '正在生成回复'
            assistant.content += event.text
          } else if (event.type === 'tool_start') {
            if (knownToolIds.has(event.id)) continue  // dedup
            knownToolIds.add(event.id)
            assistant.statusText = ''
            const tool: ToolCall = { id: event.id, name: event.name, args: event.args || {}, status: 'running' }
            assistant.toolCalls = [...(assistant.toolCalls || []), tool]
          } else if (event.type === 'tool_end') {
            const tool = assistant.toolCalls?.find(item => item.id === event.id)
            if (tool) Object.assign(tool, { status: 'done', result: event.result || '' })
          } else if (event.type === 'confirm_required') {
            assistant.statusText = '等待确认'
            store.pendingConfirm = { ...event, session_id: sessionId } as ConfirmEvent
            store.pendingConfirmRestored = false
            store.updateSession(sessionId, { status: 'waiting_confirmation' })
          } else if (event.type === 'resync_required') {
            // Buffer doesn't cover our range — full reload
            store.setMessages(sessionId, event.messages || [])
            store.updateSession(sessionId, { status: event.status || 'running' })
            store.notice = ''
            return
          } else if (event.type === 'error') {
            assistant.content += `${assistant.content ? '\n\n' : ''}运行失败：${event.message}`
            store.updateSession(sessionId, { status: 'error' })
          } else if (event.type === 'done') {
            // Run complete — load final state from server
            await loadSession(sessionId).catch(() => undefined)
            await refreshSessions().catch(() => undefined)
            store.notice = ''
            return
          }
        }
      }
    } catch {
      store.notice = '重连已中断，刷新可恢复。'
    } finally {
      reader.releaseLock()
      assistant.isStreaming = false
      await refreshSessions().catch(() => undefined)
    }
  }

  async function cancelRun() {
    const sessionId = store.runningSessionId || store.activeSessionId
    if (!sessionId) return
    store.updateSession(sessionId, { status: 'cancelling' as SessionStatus })
    try {
      const response = await fetch(`/api/sessions/${sessionId}/cancel`, {
        method: 'POST', headers: headers(),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => null)
        store.notice = errorText(data, `取消失败（${response.status}）`)
      }
    } catch {
      store.notice = '无法连接服务，取消请求可能未生效'
    }
  }

  async function submitConfirm(approve: boolean) {
    const pending = store.pendingConfirm
    const sessionId = pending?.session_id || store.activeSessionId
    if (!pending?.id || !sessionId) return
    const shouldFollow = store.pendingConfirmRestored
    const response = await fetch(`/api/sessions/${sessionId}/confirm`, {
      method: 'POST', headers: headers(true), body: JSON.stringify({ id: pending.id, approve }),
    })
    if (!response.ok) throw new Error(`确认操作已失效（${response.status}）`)
    store.pendingConfirm = null
    store.pendingConfirmRestored = false
    store.updateSession(sessionId, { status: 'running' as SessionStatus })
    if (shouldFollow) void followRestoredRun(sessionId)
  }

  return {
    initializeSessions,
    refreshSessions,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    sendMessage,
    cancelRun,
    submitConfirm,
    checkPendingConfirm,
  }
}

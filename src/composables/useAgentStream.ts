import { useChatStore } from '../stores/chatStore'
import type { ConfirmEvent } from '../stores/chatStore'

export function useAgentStream() {
  const store = useChatStore()

  async function checkPendingConfirm() {
    // Query server for any pending confirmation to restore after page reload.
    try {
      const resp = await fetch(`/api/session/pending?token=${store.token}`)
      if (!resp.ok) return

      const data = await resp.json()
      if (data.pending) {
        store.pendingConfirm = data.pending as ConfirmEvent
      }
    } catch (err) {
      console.error('Failed to check pending confirm:', err)
    }
  }

  async function sendMessage(message: string) {
    store.addMessage('user', message)
    // Pre-create assistant message for streaming updates
    store.addMessage('assistant', '')

    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CoreCoder-Token': store.token,
      },
      body: JSON.stringify({ message }),
    })

    if (!resp.ok) {
      store.addMessage('assistant', `Request failed: ${resp.status}`)
      return
    }

    let assistantContent = ''
    const reader = resp.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buf = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const frames = buf.split('\n\n')
        buf = frames.pop() || ''

        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue
          const evt = JSON.parse(frame.slice(6))

          if (evt.type === 'token') {
            assistantContent += evt.text
            // Update last message incrementally (it's the assistant message we just created)
            if (store.messages.length > 0) {
              const lastMsg = store.messages[store.messages.length - 1]
              if (lastMsg.role === 'assistant') {
                lastMsg.content = assistantContent
              }
            }
          } else if (evt.type === 'tool_start') {
            store.createToolCall(evt.id, evt.name, evt.args || {})
            // Link tool call to the current assistant message
            if (store.messages.length > 0) {
              const lastMsg = store.messages[store.messages.length - 1]
              if (lastMsg.role === 'assistant') {
                if (!lastMsg.toolCalls) lastMsg.toolCalls = []
                lastMsg.toolCalls.push({
                  id: evt.id,
                  name: evt.name,
                  args: evt.args || {},
                  status: 'running',
                })
              }
            }
          } else if (evt.type === 'tool_end') {
            store.updateToolCall(evt.id, {
              status: 'done',
              result: evt.result || '',
            })
            // Update tool call status in message
            if (store.messages.length > 0) {
              const lastMsg = store.messages[store.messages.length - 1]
              if (lastMsg.role === 'assistant' && lastMsg.toolCalls) {
                const toolCall = lastMsg.toolCalls.find(tc => tc.id === evt.id)
                if (toolCall) {
                  toolCall.status = 'done'
                  toolCall.result = evt.result || ''
                }
              }
            }
          } else if (evt.type === 'confirm_required') {
            store.pendingConfirm = evt as ConfirmEvent
          } else if (evt.type === 'error') {
            assistantContent += `\n[error] ${evt.message}`
          } else if (evt.type === 'done') {
            break
          }
        }
      }
    } finally {
      reader.releaseLock()
    }

    // Final update to ensure all content is persisted
    if (store.messages.length > 0) {
      const lastMsg = store.messages[store.messages.length - 1]
      if (lastMsg.role === 'assistant') {
        lastMsg.content = assistantContent
      }
    }
  }

  async function submitConfirm(approve: boolean) {
    if (!store.pendingConfirm?.id) return

    const resp = await fetch('/api/confirm', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CoreCoder-Token': store.token,
      },
      body: JSON.stringify({ id: store.pendingConfirm.id, approve }),
    })

    if (resp.ok) {
      store.pendingConfirm = null
    } else {
      console.error('Confirm request failed:', resp.status)
    }
  }

  return {
    sendMessage,
    submitConfirm,
    checkPendingConfirm,
  }
}

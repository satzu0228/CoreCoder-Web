import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../../src/stores/chatStore'

describe('chatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty sessions and messages', () => {
    const store = useChatStore()
    expect(store.sessions).toEqual([])
    expect(store.messages).toEqual([])
    expect(store.activeSessionId).toBeNull()
    expect(store.isRunning).toBe(false)
  })

  it('addMessage creates a message with correct shape', () => {
    const store = useChatStore()
    store.activeSessionId = 's1'
    store.addMessage('s1', 'user', 'hello')
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[0].content).toBe('hello')
    expect(store.messages[0].id).toBeTruthy()
  })

  it('addMessage appends in order', () => {
    const store = useChatStore()
    store.activeSessionId = 's1'
    store.addMessage('s1', 'user', 'first')
    store.addMessage('s1', 'assistant', 'second')
    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].content).toBe('first')
    expect(store.messages[1].content).toBe('second')
  })

  it('setMessages replaces messages array', () => {
    const store = useChatStore()
    store.activeSessionId = 's1'
    store.addMessage('s1', 'user', 'old')
    store.setMessages('s1', [{ id: 'x', role: 'user', content: 'new' }])
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('new')
  })

  it('updateSession patches session fields', () => {
    const store = useChatStore()
    store.sessions = [
      { id: 's1', title: 'Old', preview: '', model: 'm', status: 'idle' as const, created_at: '', updated_at: '' },
    ]
    store.updateSession('s1', { title: 'New' })
    expect(store.sessions[0].title).toBe('New')
  })

  it('isRunning reflects runningSessionId', () => {
    const store = useChatStore()
    expect(store.isRunning).toBe(false)
    store.runningSessionId = 's1'
    expect(store.isRunning).toBe(true)
    store.runningSessionId = null
    expect(store.isRunning).toBe(false)
  })

  it('pendingConfirm defaults to null', () => {
    const store = useChatStore()
    expect(store.pendingConfirm).toBeNull()
  })
})

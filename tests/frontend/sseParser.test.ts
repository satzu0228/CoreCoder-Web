import { describe, it, expect } from 'vitest'
import { parseSSEFrame } from '../../src/composables/useAgentStream'

describe('parseSSEFrame', () => {
  it('parses a valid SSE data frame', () => {
    const result = parseSSEFrame('data: {"type":"token","content":"hello"}')
    expect(result).toEqual({ type: 'token', content: 'hello' })
  })

  it('returns null for non-data lines', () => {
    expect(parseSSEFrame(': heartbeat')).toBeNull()
    expect(parseSSEFrame('')).toBeNull()
    expect(parseSSEFrame('event: ping')).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(parseSSEFrame('')).toBeNull()
  })

  it('returns null for malformed JSON', () => {
    expect(parseSSEFrame('data: {not valid json}')).toBeNull()
  })

  it('handles tool_start events', () => {
    const result = parseSSEFrame('data: {"type":"tool_start","id":"t1","name":"bash","args":{"command":"ls"}}')
    expect(result).toEqual({ type: 'tool_start', id: 't1', name: 'bash', args: { command: 'ls' } })
  })

  it('handles tool_end events', () => {
    const result = parseSSEFrame('data: {"type":"tool_end","id":"t1","name":"bash","result":"file1.txt\\nfile2.txt"}')
    expect(result).toHaveProperty('type', 'tool_end')
    expect(result).toHaveProperty('result')
  })

  it('handles confirm_required events', () => {
    const result = parseSSEFrame('data: {"type":"confirm_required","action":"bash","command":"rm -rf /"}')
    expect(result).toEqual({ type: 'confirm_required', action: 'bash', command: 'rm -rf /' })
  })

  it('handles done events', () => {
    const result = parseSSEFrame('data: {"type":"done"}')
    expect(result).toEqual({ type: 'done' })
  })

  it('handles error events', () => {
    const result = parseSSEFrame('data: {"type":"error","message":"something went wrong"}')
    expect(result).toEqual({ type: 'error', message: 'something went wrong' })
  })

  it('trims whitespace from frame', () => {
    const result = parseSSEFrame('  data: {"type":"done"}  ')
    expect(result).toEqual({ type: 'done' })
  })
})

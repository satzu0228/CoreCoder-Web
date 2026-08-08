// Vitest setup — stub browser APIs not available in jsdom
import { config } from '@vue/test-utils'

// Stub DOMPurify for test environment
vi.mock('dompurify', () => ({
  default: {
    sanitize: (html: string) => html,
    addHook: () => {},
  },
}))

// Stub ResizeObserver
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver

// Stub IntersectionObserver
global.IntersectionObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof IntersectionObserver

// Suppress Naive UI style warnings in tests
config.global.stubs = {
  transition: false,
}

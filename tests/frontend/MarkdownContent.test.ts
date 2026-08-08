import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import MarkdownContent from '../../src/components/MarkdownContent.vue'

describe('MarkdownContent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders plain text', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: 'Hello world', isStreaming: false },
    })
    expect(wrapper.html()).toContain('Hello world')
  })

  it('renders bold markdown', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: '**bold text**', isStreaming: false },
    })
    expect(wrapper.html()).toContain('<strong>')
    expect(wrapper.html()).toContain('bold text')
  })

  it('renders inline code', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: 'use `console.log()` to debug', isStreaming: false },
    })
    expect(wrapper.html()).toContain('<code>')
    expect(wrapper.html()).toContain('console.log()')
  })

  it('renders code blocks with pre and code tags', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: '```js\nconst x = 1;\n```', isStreaming: false },
    })
    const html = wrapper.html()
    expect(html).toContain('<pre>')
    expect(html).toContain('const x = 1;')
  })

  it('renders headings', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: '# Title', isStreaming: false },
    })
    expect(wrapper.html()).toContain('<h1')
    expect(wrapper.text()).toContain('Title')
  })

  it('returns empty string for empty content', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: '', isStreaming: false },
    })
    expect(wrapper.find('.markdown-body').text()).toBe('')
  })

  it('handles streaming prop without error', () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: 'streaming...', isStreaming: true },
    })
    expect(wrapper.html()).toContain('streaming...')
  })
})

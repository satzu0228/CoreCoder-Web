<template>
  <div class="markdown-body" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 DOMPurify：只允许安全的 URL scheme
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node instanceof HTMLAnchorElement) {
    const href = node.getAttribute('href') || ''
    const normalized = href.trim().toLowerCase()
    if (
      normalized &&
      !normalized.startsWith('http://') &&
      !normalized.startsWith('https://') &&
      !normalized.startsWith('mailto:') &&
      !normalized.startsWith('#')
    ) {
      node.removeAttribute('href')
    }
  }
})

// 配置 marked：让链接在新标签页打开
marked.use({
  renderer: {
    link({ href, title, tokens }) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const text = marked.parseInline(tokens as any)
      const titleAttr = title ? ` title="${title}"` : ''
      return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`
    },
  },
})

const props = defineProps<{
  content: string
  isStreaming?: boolean
  throttleMs?: number
}>()

const debouncedContent = ref(props.content)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
const THROTTLE_MS = props.throttleMs ?? 80
const SHORT_CONTENT_THRESHOLD = 500

watch(
  () => props.content,
  (newContent) => {
    if (!props.isStreaming || newContent.length < SHORT_CONTENT_THRESHOLD) {
      if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null }
      debouncedContent.value = newContent
      return
    }
    if (!debounceTimer) debouncedContent.value = newContent
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(() => {
      debouncedContent.value = newContent
      debounceTimer = null
    }, THROTTLE_MS)
  },
)

watch(
  () => props.isStreaming,
  (streaming) => {
    if (!streaming) {
      if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null }
      debouncedContent.value = props.content
    }
  },
)

const renderedHtml = computed(() => {
  if (!debouncedContent.value) return ''
  const rawHtml = marked.parse(debouncedContent.value, { breaks: true }) as string
  return DOMPurify.sanitize(rawHtml)
})
</script>

<style>
/* v-html 内容无法被 scoped 样式或 Tailwind 类名命中，保留非 scoped 样式块 */
.markdown-body {
  font-size: 14px;
  line-height: 1.78;
  color: #263343;
  word-break: break-word;
}
.markdown-body > *:first-child { margin-top: 0; }
.markdown-body > *:last-child { margin-bottom: 0; }
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
  margin: 1.2em 0 .5em;
  font-weight: 700;
  line-height: 1.35;
  color: #1a2535;
}
.markdown-body h1 { font-size: 1.35em; border-bottom: 1px solid #dfe5ec; padding-bottom: .35em; }
.markdown-body h2 { font-size: 1.18em; }
.markdown-body h3 { font-size: 1.05em; }
.markdown-body h4 { font-size: .95em; color: #3b4858; }
.markdown-body p { margin: .6em 0; }
.markdown-body code {
  padding: 1px 5px;
  border-radius: 4px;
  background: #edf2f7;
  color: #c7254e;
  font: .9em/1.5 Consolas, "Microsoft YaHei Mono", monospace;
}
.markdown-body pre {
  margin: .7em 0;
  padding: 13px 15px;
  border: 1px solid #dfe5ec;
  border-radius: 8px;
  background: #f7f9fb;
  overflow-x: auto;
}
.markdown-body pre code {
  padding: 0;
  background: transparent;
  color: #354052;
  font-size: .85em;
  line-height: 1.6;
}
.markdown-body ul, .markdown-body ol { margin: .5em 0; padding-left: 1.6em; }
.markdown-body li { margin: .2em 0; }
.markdown-body li > ul, .markdown-body li > ol { margin: .1em 0; }
.markdown-body blockquote {
  margin: .7em 0;
  padding: 6px 0 6px 14px;
  border-left: 3px solid #3767d6;
  background: rgba(55,103,214,.04);
  color: #526176;
}
.markdown-body blockquote p { margin: .3em 0; }
.markdown-body a { color: #3767d6; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body table { width: 100%; margin: .7em 0; border-collapse: collapse; font-size: .92em; }
.markdown-body th, .markdown-body td { padding: 7px 11px; border: 1px solid #dfe5ec; text-align: left; }
.markdown-body th { background: #f5f7fa; font-weight: 700; color: #3b4858; }
.markdown-body hr { margin: 1em 0; border: 0; border-top: 1px solid #dfe5ec; }
.markdown-body strong { font-weight: 700; color: #1a2535; }
.markdown-body em { font-style: italic; }
.markdown-body img { max-width: 100%; border-radius: 6px; }
</style>

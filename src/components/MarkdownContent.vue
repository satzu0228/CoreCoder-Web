<template>
  <div class="markdown-body" v-html="renderedHtml"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

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
}>()

const renderedHtml = computed(() => {
  if (!props.content) return ''
  // marked.parse 返回 string | Promise<string>，同步调用始终返回 string
  return marked.parse(props.content, { breaks: true }) as string
})
</script>

<style>
/* 不 scoped，因为 v-html 渲染出来的元素无法被 scoped 样式命中 */
.markdown-body {
  font-size: 14px;
  line-height: 1.78;
  color: #263343;
  word-break: break-word;
}

.markdown-body > *:first-child { margin-top: 0; }
.markdown-body > *:last-child { margin-bottom: 0; }

/* 标题 */
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
  margin: 1.2em 0 .5em;
  font-weight: 700;
  line-height: 1.35;
  color: #1a2535;
}
.markdown-body h1 { font-size: 1.35em; border-bottom: 1px solid #e2e7ed; padding-bottom: .35em; }
.markdown-body h2 { font-size: 1.18em; }
.markdown-body h3 { font-size: 1.05em; }
.markdown-body h4 { font-size: .95em; color: #3b4858; }

/* 段落 */
.markdown-body p { margin: .6em 0; }

/* 行内代码 */
.markdown-body code {
  padding: 1px 5px;
  border-radius: 4px;
  background: #edf2f7;
  color: #c7254e;
  font: .9em/1.5 Consolas, "Microsoft YaHei Mono", monospace;
}

/* 代码块 */
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

/* 列表 */
.markdown-body ul, .markdown-body ol {
  margin: .5em 0;
  padding-left: 1.6em;
}
.markdown-body li { margin: .2em 0; }
.markdown-body li > ul, .markdown-body li > ol { margin: .1em 0; }

/* 引用 */
.markdown-body blockquote {
  margin: .7em 0;
  padding: 6px 0 6px 14px;
  border-left: 3px solid #3767d6;
  background: rgba(55,103,214,.04);
  color: #526176;
}
.markdown-body blockquote p { margin: .3em 0; }

/* 链接 */
.markdown-body a {
  color: #3767d6;
  text-decoration: none;
}
.markdown-body a:hover { text-decoration: underline; }

/* 表格 */
.markdown-body table {
  width: 100%;
  margin: .7em 0;
  border-collapse: collapse;
  font-size: .92em;
}
.markdown-body th, .markdown-body td {
  padding: 7px 11px;
  border: 1px solid #dfe5ec;
  text-align: left;
}
.markdown-body th {
  background: #f5f7fa;
  font-weight: 700;
  color: #3b4858;
}

/* 分割线 */
.markdown-body hr {
  margin: 1em 0;
  border: 0;
  border-top: 1px solid #dfe5ec;
}

/* 强调 */
.markdown-body strong { font-weight: 700; color: #1a2535; }
.markdown-body em { font-style: italic; }

/* 图片 */
.markdown-body img { max-width: 100%; border-radius: 6px; }
</style>

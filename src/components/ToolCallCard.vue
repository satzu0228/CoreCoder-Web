<template>
  <div class="trace-step">
    <span class="trace-node" aria-hidden="true">
      <svg v-if="toolCall.status === 'done'" viewBox="0 0 16 16"><path d="m4 8 2.5 2.5L12 5" /></svg>
      <span v-else class="trace-spinner"></span>
    </span>
    <div class="trace-content">
      <button class="trace-summary" type="button" :aria-expanded="expanded" @click="expanded = !expanded">
        <span class="tool-name">{{ readableName }}</span>
        <span class="tool-brief">{{ brief }}</span>
        <svg viewBox="0 0 16 16" :class="{ rotated: expanded }" aria-hidden="true"><path d="m5 6 3 3 3-3" /></svg>
      </button>
      <div v-if="expanded" class="trace-detail">
        <div v-if="toolCall.args && Object.keys(toolCall.args).length" class="detail-block">
          <span>输入</span><pre>{{ formatArgs(toolCall.args) }}</pre>
        </div>
        <div v-if="toolCall.status === 'done' && toolCall.result" class="detail-block result-block">
          <span>结果</span><pre>{{ toolCall.result }}</pre>
        </div>
        <div v-if="toolCall.status === 'running'" class="running-copy">正在执行这一步…</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '../stores/chatStore'

const props = defineProps<{ toolCall: ToolCall }>()
const expanded = ref(false)
const names: Record<string, string> = {
  bash: '运行命令', read_file: '读取文件', write_file: '写入文件', edit_file: '修改文件',
  glob: '查找文件', grep: '搜索代码', agent: '委派任务',
}
const readableName = computed(() => names[props.toolCall.name] || props.toolCall.name)
const brief = computed(() => {
  const args = props.toolCall.args || {}
  const preferred = args.file_path || args.path || args.command || args.pattern || args.task
  if (preferred) return String(preferred).replace(/\s+/g, ' ').slice(0, 72)
  return props.toolCall.status === 'running' ? '执行中' : '已完成'
})
function formatArgs(args: Record<string, unknown>) { return JSON.stringify(args, null, 2) }
</script>

<style scoped>
/* Tailwind 无法表达的：动画 + 连接线伪元素 */
.trace-step {
  position: relative;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 9px;
  padding: 0 0 15px;
  opacity: 0;
  animation: trace-enter .24s ease-out forwards;
  animation-delay: calc(var(--trace-index, 0) * 110ms);
}
.trace-step:last-child { padding-bottom: 0; }
.trace-step:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 10px;
  top: 21px;
  bottom: -1px;
  width: 1px;
  background: #d8e0e9;
}
.trace-node {
  z-index: 1;
  width: 21px;
  height: 21px;
  display: grid;
  place-items: center;
  border: 1px solid #b9c8e6;
  border-radius: 50%;
  background: #f7f9fc;
  color: #3767d6;
}
.trace-step.complete .trace-node {
  border-color: #add2c9;
  color: #1f8a78;
}
.trace-node svg {
  width: 13px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}
.trace-spinner {
  width: 7px;
  height: 7px;
  border: 1.5px solid #aebddd;
  border-top-color: #3767d6;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
.trace-content { min-width: 0; padding-top: 1px; }
.trace-summary {
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 16px;
  align-items: center;
  gap: 8px;
  padding: 1px 0;
  border: 0;
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.tool-name { color: #3b4858; font-size: 12px; font-weight: 700; }
.tool-brief { overflow: hidden; color: #8792a2; font: 500 10px Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
.trace-summary > svg { width: 14px; fill: none; stroke: #8792a2; stroke-width: 1.4; transition: transform .16s; }
.trace-summary > svg.rotated { transform: rotate(180deg); }
.trace-detail { margin-top: 8px; padding: 10px 11px; border: 1px solid #e1e7ee; border-radius: 8px; background: #f8fafc; }
.detail-block + .detail-block { margin-top: 10px; }
.detail-block > span { display: block; margin-bottom: 5px; color: #8792a2; font: 700 9px Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.detail-block pre { max-height: 190px; margin: 0; padding: 0; overflow: auto; background: transparent; color: #435064; font: 10px/1.55 Consolas, monospace; white-space: pre-wrap; }
.result-block pre { color: #2e6158; }
.running-copy { color: #71809a; font-size: 11px; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes trace-enter { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  .trace-step { opacity: 1; animation: none; }
  .trace-spinner { animation: none; }
  .trace-summary > svg { transition: none; }
}
</style>

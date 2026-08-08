<template>
  <section class="min-w-0 h-full flex flex-1 flex-col bg-brand-50 text-brand-800">
    <header class="h-[67px] shrink-0 flex items-center gap-3 px-[25px] border-b border-brand-200 bg-white/86 backdrop-blur-md max-md:h-[60px] max-md:basis-[60px] max-md:px-[14px]">
      <button class="hidden max-md:grid w-9 h-9 place-items-center border border-brand-200 rounded-[9px] bg-white" type="button" aria-label="打开对话列表" @click="store.sidebarOpen = true">
        <svg class="w-[19px] fill-none stroke-brand-600" style="stroke-linecap:round;stroke-width:1.7" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
      </button>
      <div class="min-w-0 flex flex-col gap-1">
        <h1 class="overflow-hidden m-0 text-brand-900 text-sm font-bold truncate">{{ store.activeSession?.title || '新对话' }}</h1>
        <span class="flex items-center gap-1.5 text-brand-500 text-[10px]">
          <i class="w-[5px] h-[5px] rounded-full bg-brand-400" :class="`status-${store.activeSession?.status || 'idle'}`"></i>
          {{ headerStatus }}
        </span>
      </div>
      <div class="ml-auto px-2 py-[5px] border border-brand-200 rounded-md bg-brand-50 text-brand-600 font-medium text-[10px] font-mono max-md:hidden">{{ store.activeSession?.model || 'CoreCoder' }}</div>
    </header>

    <div ref="scrollArea" class="min-h-0 flex-1 overflow-y-auto smooth-scroll">
      <!-- 空状态 -->
      <div v-if="!store.messages.length" class="w-[min(660px,calc(100%-40px))] min-h-full flex flex-col justify-center items-center mx-auto py-12 pb-[120px] text-center max-md:w-[calc(100%-32px)] max-md:pb-20">
        <div class="w-[58px] h-[58px] grid place-items-center mb-[22px] border border-brand-200 rounded-[17px] bg-white text-primary-500 shadow-[0_10px_30px_rgba(30,43,59,.07)] -rotate-3">
          <span class="font-bold text-base font-mono rotate-3">&gt;_</span>
        </div>
        <p class="m-0 mb-2 text-brand-600 font-bold text-[10px] font-mono tracking-[0.1em] uppercase">{{ store.workspaceName }}</p>
        <h2 class="m-0 text-brand-900 text-[25px] tracking-[-0.025em]">从一个具体任务开始</h2>
        <p class="empty-state-desc">描述你想检查、修改或理解的代码。CoreCoder 会把每一步工具操作留在对话轨迹里。</p>
        <div class="flex flex-wrap justify-center gap-2">
          <button class="px-3 py-[9px] border border-brand-200 rounded-[9px] bg-white/70 text-brand-700 font-semibold text-[11px] cursor-pointer hover:border-brand-300 hover:bg-white hover:text-primary-600" type="button" @click="useExample('阅读项目并说明它的核心架构')">说明项目架构</button>
          <button class="px-3 py-[9px] border border-brand-200 rounded-[9px] bg-white/70 text-brand-700 font-semibold text-[11px] cursor-pointer hover:border-brand-300 hover:bg-white hover:text-primary-600" type="button" @click="useExample('检查当前改动，找出可能的问题')">检查当前改动</button>
          <button class="px-3 py-[9px] border border-brand-200 rounded-[9px] bg-white/70 text-brand-700 font-semibold text-[11px] cursor-pointer hover:border-brand-300 hover:bg-white hover:text-primary-600" type="button" @click="useExample('运行测试并修复失败项')">运行并修复测试</button>
        </div>
      </div>

      <!-- 对话列表 -->
      <div v-else class="w-[min(820px,calc(100%-40px))] mx-auto pt-[42px] pb-[34px] max-md:w-[calc(100%-24px)] max-md:pt-[25px]">
        <article v-for="msg in store.messages" :key="msg.id" class="message-row flex items-start gap-[11px] mb-[29px]" :class="`message-${msg.role}`">
          <div class="message-avatar w-7 h-7 shrink-0 grid place-items-center mt-[18px] rounded-lg bg-brand-950 text-white font-bold text-[10px] font-mono" aria-hidden="true">{{ msg.role === 'user' ? '你' : 'C' }}</div>
          <div class="message-column max-w-[min(88%,700px)] min-w-0 max-md:max-w-[calc(100%-39px)]">
            <div class="mx-[5px] mb-1.5 text-brand-500 text-[10px] font-bold">{{ msg.role === 'user' ? '你' : 'CoreCoder' }}</div>

            <!-- 执行轨迹 -->
            <div v-if="msg.role === 'assistant' && msg.toolCalls?.length" class="agent-trace min-w-[min(520px,65vw)] mb-[11px] max-md:min-w-[min(68vw,440px)]">
              <button class="flex items-center gap-[7px] w-full p-0 border-0 bg-transparent text-brand-500 font-bold text-[9px] font-mono tracking-[0.08em] uppercase cursor-pointer hover:text-brand-700" type="button" @click="toggleTrace(msg.id)">
                <svg viewBox="0 0 16 16" class="trace-chevron w-[13px] shrink-0 fill-none stroke-current" style="stroke-width:1.5" :class="{ collapsed: traceCollapsed[msg.id] }" aria-hidden="true">
                  <path d="m5 6 3 3 3-3" />
                </svg>
                <span>执行轨迹</span>
                <span class="ml-auto">{{ completedCount(msg.toolCalls) }}/{{ msg.toolCalls.length }}</span>
              </button>
              <div v-show="!traceCollapsed[msg.id]" class="mt-[9px]">
                <ToolCallCard v-for="(tool, index) in msg.toolCalls" :key="tool.id" :tool-call="tool" :style="{ '--trace-index': index }" />
              </div>
            </div>

            <!-- 等待模型响应 -->
            <div v-if="msg.role === 'assistant' && !msg.content && !msg.toolCalls?.length && msg.isStreaming" class="min-h-6 flex items-center gap-[9px] py-0.5 px-1 text-brand-500 font-medium text-[11px] font-mono">
              <span class="flex gap-[3px]">
                <i class="waiting-dot w-1 h-1 rounded-full bg-primary-400"></i>
                <i class="waiting-dot w-1 h-1 rounded-full bg-primary-400" style="animation-delay:.12s"></i>
                <i class="waiting-dot w-1 h-1 rounded-full bg-primary-400" style="animation-delay:.24s"></i>
              </span>
              <span>{{ msg.statusText || '等待模型响应' }}</span>
            </div>

            <!-- 消息气泡 -->
            <div v-if="msg.role === 'user' || msg.content" class="message-bubble min-w-[56px] px-[17px] py-[15px] border border-brand-200 bg-white shadow-[0_2px_10px_rgba(30,43,59,.045)] max-md:px-[14px] max-md:py-[13px]" :class="{ streaming: msg.isStreaming }">
              <div v-if="msg.content && msg.role === 'user'" class="text-sm leading-[1.72] whitespace-pre-wrap break-words">
                {{ msg.content }}
              </div>
              <div v-if="msg.content && msg.role === 'assistant'" class="text-sm leading-[1.72]">
                <MarkdownContent :content="msg.content" :is-streaming="msg.isStreaming" />
                <span v-if="msg.isStreaming" class="typing-caret inline-block w-[1.5px] h-[1em] ml-0.5 -mt-[0.12em] align-middle bg-primary-500"></span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="w-[min(840px,calc(100%-40px))] shrink-0 mx-auto pb-4 max-md:w-[calc(100%-20px)] max-md:pb-[9px]">
      <div v-if="store.notice" class="flex justify-between gap-[10px] mb-2 px-[11px] py-2 border border-[#ead8b8] rounded-lg bg-[#fff9ed] text-[#845f24] text-[11px]" role="status">
        <span>{{ store.notice }}</span><button class="border-0 bg-transparent cursor-pointer" type="button" @click="store.notice = ''">×</button>
      </div>
      <form class="composer-box px-4 py-[10px] pt-3 pr-[13px] pb-2.5 pl-4 border border-brand-300 rounded-[16px] bg-white shadow-[0_9px_28px_rgba(30,43,59,.09)]" @submit.prevent="handleSubmit">
        <textarea
          ref="textarea"
          v-model="inputText"
          rows="1"
          class="w-full max-h-[180px] resize-none border-0 outline-0 bg-transparent text-brand-800 text-sm leading-[1.55] disabled:cursor-not-allowed placeholder:text-brand-400"
          :placeholder="composerPlaceholder"
          :disabled="inputDisabled"
          @input="resizeTextarea"
          @keydown.enter.exact.prevent="handleSubmit"
        ></textarea>
        <div class="flex items-center justify-between mt-[7px] max-md:justify-end">
          <span class="text-brand-400 font-medium text-[9px] font-mono max-md:hidden">{{ composerHint }}</span>
          <button
            v-if="store.isRunning"
            type="button"
            class="stop-btn w-[31px] h-[31px] grid place-items-center border-0 rounded-[9px] text-white cursor-pointer disabled:cursor-not-allowed"
            :disabled="store.activeSession?.status === 'cancelling'"
            aria-label="停止任务"
            @click="cancelRun()"
          >
            <svg class="w-[17px] fill-none stroke-current" style="stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8" viewBox="0 0 20 20"><rect x="4" y="4" width="12" height="12" rx="1" /></svg>
          </button>
          <button v-else type="submit" class="w-[31px] h-[31px] grid place-items-center border-0 rounded-[9px] bg-brand-950 text-white cursor-pointer disabled:bg-brand-200 disabled:text-brand-400 disabled:cursor-default enabled:hover:bg-primary-500" :disabled="!inputText.trim() || inputDisabled" aria-label="发送消息">
            <svg class="w-[17px] fill-none stroke-current" style="stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8" viewBox="0 0 20 20"><path d="M10 15V5m0 0L6 9m4-4 4 4" /></svg>
          </button>
        </div>
      </form>
      <p class="mt-[7px] text-brand-400 text-[9px] text-center">CoreCoder 会在执行写入或高风险命令前请求确认。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useChatStore, type ToolCall } from '../stores/chatStore'
import { useAgentStream } from '../composables/useAgentStream'
import ToolCallCard from './ToolCallCard.vue'
import MarkdownContent from './MarkdownContent.vue'

const store = useChatStore()
const { sendMessage, cancelRun } = useAgentStream()
const inputText = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)
const scrollArea = ref<HTMLElement | null>(null)

const traceCollapsed = reactive<Record<string, boolean>>({})
function toggleTrace(msgId: string) { traceCollapsed[msgId] = !traceCollapsed[msgId] }

const inputDisabled = computed(() => store.isRunning)
const composerPlaceholder = computed(() => {
  if (store.runningSessionId && store.runningSessionId !== store.activeSessionId) return '另一个对话正在执行，请等待它完成…'
  if (store.activeSession?.status === 'waiting_confirmation') return '请先处理待确认操作…'
  if (store.isRunning) return 'CoreCoder 正在执行当前任务…'
  return '交给 CoreCoder 一个任务…'
})
const headerStatus = computed(() => ({
  idle: '就绪', running: '正在执行', waiting_confirmation: '等待你的确认',
  cancelling: '正在停止', cancelled: '已取消',
  interrupted: '上次运行已中断', error: '上次运行失败',
})[store.activeSession?.status || 'idle'])
const composerHint = computed(() => {
  if (store.activeSession?.status === 'cancelling') return '正在停止任务…'
  if (store.isRunning) return '点击停止按钮中断任务'
  return 'Enter 发送 · Shift Enter 换行'
})

function completedCount(tools: ToolCall[]) { return tools.filter(tool => tool.status === 'done').length }
function useExample(value: string) { inputText.value = value; textarea.value?.focus(); resizeTextarea() }
function resizeTextarea() {
  if (!textarea.value) return
  textarea.value.style.height = 'auto'
  textarea.value.style.height = `${Math.min(textarea.value.scrollHeight, 180)}px`
}
async function handleSubmit() {
  const text = inputText.value.trim()
  if (!text || inputDisabled.value) return
  inputText.value = ''
  await nextTick()
  resizeTextarea()
  await sendMessage(text)
}

watch(() => store.messages.map(message => `${message.content.length}:${message.toolCalls?.length || 0}`).join(','), async () => {
  await nextTick()
  if (scrollArea.value) scrollArea.value.scrollTop = scrollArea.value.scrollHeight
})
</script>

<style scoped>
/* === 动画 === */
@keyframes bounce { 0%,60%,100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-3px); opacity: 1; } }
@keyframes caret-blink { 50% { opacity: 0; } }
.waiting-dot { animation: bounce 1.2s infinite ease-in-out; }
.typing-caret { animation: caret-blink .8s steps(1) infinite; }

/* === 状态指示灯颜色 === */
.status-running { @apply bg-primary-500; }
.status-waiting_confirmation { @apply bg-warning; }
.status-error { @apply bg-danger; }
.status-interrupted { background: #8c6fba; }

/* === 用户消息行（反转布局） === */
.message-user { flex-direction: row-reverse; }
.message-user .message-avatar { @apply bg-brand-200 text-brand-700; }
.message-user .message-column { display: flex; flex-direction: column; align-items: flex-end; }
.message-user .message-bubble { @apply border-[#355fbd] bg-primary-500 text-white; border-radius: 17px 5px 17px 17px; box-shadow: 0 5px 16px rgba(55,103,214,.14); }

/* === 普通消息气泡圆角 === */
.message-bubble { border-radius: 5px 17px 17px 17px; }
.message-bubble.streaming { border-radius: 17px 17px 17px 17px; }

/* === 执行轨迹折叠箭头 === */
.trace-chevron { transition: transform .18s; }
.trace-chevron.collapsed { transform: rotate(-90deg); }

/* === 空状态描述（不能用 :not() 完全替代的选择器） === */
.empty-state-desc { max-width: 470px; margin: 12px 0 25px; color: #748093; font-size: 13px; line-height: 1.65; }

/* === 输入框 focus + 停止按钮 === */
.composer-box { transition: border-color .16s, box-shadow .16s; }
.composer-box:focus-within { border-color: #8ca8e4; box-shadow: 0 9px 28px rgba(30,43,59,.09), 0 0 0 3px rgba(55,103,214,.08); }
.stop-btn { background: #c95454; }
.stop-btn:not(:disabled):hover { background: #b33a3a; }

/* === 无障碍 === */
@media (prefers-reduced-motion: reduce) {
  .smooth-scroll { scroll-behavior: auto; }
  .waiting-dot, .typing-caret { animation: none; }
  .composer-box { transition: none; }
}
</style>

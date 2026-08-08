<template>
  <section class="chat-panel">
    <header class="chat-header">
      <button class="menu-button" type="button" aria-label="打开对话列表" @click="store.sidebarOpen = true">
        <svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
      </button>
      <div class="chat-heading">
        <h1>{{ store.activeSession?.title || '新对话' }}</h1>
        <span><i :class="`status-${store.activeSession?.status || 'idle'}`"></i>{{ headerStatus }}</span>
      </div>
      <div class="model-chip">{{ store.activeSession?.model || 'CoreCoder' }}</div>
    </header>

    <div ref="scrollArea" class="messages-area">
      <div v-if="!store.messages.length" class="empty-state">
        <div class="empty-mark"><span>&gt;_</span></div>
        <p class="empty-eyebrow">{{ store.workspaceName }}</p>
        <h2>从一个具体任务开始</h2>
        <p>描述你想检查、修改或理解的代码。CoreCoder 会把每一步工具操作留在对话轨迹里。</p>
        <div class="prompt-examples">
          <button type="button" @click="useExample('阅读项目并说明它的核心架构')">说明项目架构</button>
          <button type="button" @click="useExample('检查当前改动，找出可能的问题')">检查当前改动</button>
          <button type="button" @click="useExample('运行测试并修复失败项')">运行并修复测试</button>
        </div>
      </div>

      <div v-else class="conversation">
        <article v-for="msg in store.messages" :key="msg.id" class="message-row" :class="`message-${msg.role}`">
          <div class="message-avatar" aria-hidden="true">{{ msg.role === 'user' ? '你' : 'C' }}</div>
          <div class="message-column">
            <div class="message-meta">{{ msg.role === 'user' ? '你' : 'CoreCoder' }}</div>
            <div v-if="msg.role === 'assistant' && msg.toolCalls?.length" class="agent-trace">
              <div class="trace-heading">
                <span>执行轨迹</span>
                <span>{{ completedCount(msg.toolCalls) }}/{{ msg.toolCalls.length }}</span>
              </div>
              <ToolCallCard
                v-for="(tool, index) in msg.toolCalls"
                :key="tool.id"
                :tool-call="tool"
                :style="{ '--trace-index': index }"
              />
            </div>
            <div v-if="msg.role === 'assistant' && !msg.content && !msg.toolCalls?.length && msg.isStreaming" class="waiting-state">
              <span class="waiting-pulse"><i></i><i></i><i></i></span>
              <span>{{ msg.statusText || '等待模型响应' }}</span>
            </div>
            <div
              v-if="msg.role === 'user' || msg.content"
              class="message-bubble"
              :class="{ streaming: msg.isStreaming }"
            >
              <div v-if="msg.content" class="message-content">
                {{ msg.content }}<span v-if="msg.isStreaming" class="typing-caret" aria-hidden="true"></span>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>

    <div class="composer-wrap">
      <div v-if="store.notice" class="notice" role="status">
        <span>{{ store.notice }}</span><button type="button" @click="store.notice = ''">×</button>
      </div>
      <form class="composer" @submit.prevent="handleSubmit">
        <textarea
          ref="textarea"
          v-model="inputText"
          rows="1"
          :placeholder="composerPlaceholder"
          :disabled="inputDisabled"
          @input="resizeTextarea"
          @keydown.enter.exact.prevent="handleSubmit"
        ></textarea>
        <div class="composer-foot">
          <span>Enter 发送 · Shift Enter 换行</span>
          <button type="submit" :disabled="!inputText.trim() || inputDisabled" aria-label="发送消息">
            <svg viewBox="0 0 20 20"><path d="M10 15V5m0 0L6 9m4-4 4 4" /></svg>
          </button>
        </div>
      </form>
      <p class="composer-note">CoreCoder 会在执行写入或高风险命令前请求确认。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useChatStore, type ToolCall } from '../stores/chatStore'
import { useAgentStream } from '../composables/useAgentStream'
import ToolCallCard from './ToolCallCard.vue'

const store = useChatStore()
const { sendMessage } = useAgentStream()
const inputText = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)
const scrollArea = ref<HTMLElement | null>(null)

const inputDisabled = computed(() => store.isRunning)
const composerPlaceholder = computed(() => {
  if (store.runningSessionId && store.runningSessionId !== store.activeSessionId) return '另一个对话正在执行，请等待它完成…'
  if (store.activeSession?.status === 'waiting_confirmation') return '请先处理待确认操作…'
  if (store.isRunning) return 'CoreCoder 正在执行当前任务…'
  return '交给 CoreCoder 一个任务…'
})
const headerStatus = computed(() => ({
  idle: '就绪', running: '正在执行', waiting_confirmation: '等待你的确认',
  interrupted: '上次运行已中断', error: '上次运行失败',
})[store.activeSession?.status || 'idle'])

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
.chat-panel { min-width: 0; height: 100%; display: flex; flex: 1; flex-direction: column; background: #f5f7fa; color: #263343; }
.chat-header { height: 67px; flex: 0 0 67px; display: flex; align-items: center; gap: 12px; padding: 0 25px; border-bottom: 1px solid #e2e7ed; background: rgba(255,255,255,.86); backdrop-filter: blur(12px); }
.menu-button { display: none; width: 36px; height: 36px; place-items: center; border: 1px solid #dbe2ea; border-radius: 9px; background: #fff; }
.menu-button svg { width: 19px; fill: none; stroke: #516074; stroke-linecap: round; stroke-width: 1.7; }
.chat-heading { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.chat-heading h1 { overflow: hidden; margin: 0; color: #202b38; font-size: 14px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.chat-heading span { display: flex; align-items: center; gap: 6px; color: #8591a0; font-size: 10px; }
.chat-heading i { width: 5px; height: 5px; border-radius: 50%; background: #9aa5b2; }
.chat-heading .status-running { background: #3767d6; }
.chat-heading .status-waiting_confirmation { background: #d18b26; }
.chat-heading .status-error { background: #c95454; }
.model-chip { margin-left: auto; padding: 5px 8px; border: 1px solid #dfe5ec; border-radius: 7px; background: #f7f9fb; color: #718096; font: 500 10px Consolas, monospace; }
.messages-area { min-height: 0; flex: 1; overflow-y: auto; scroll-behavior: smooth; }
.conversation { width: min(820px, calc(100% - 40px)); margin: 0 auto; padding: 42px 0 34px; }
.message-row { display: flex; align-items: flex-start; gap: 11px; margin-bottom: 29px; }
.message-user { flex-direction: row-reverse; }
.message-avatar { width: 28px; height: 28px; flex: 0 0 28px; display: grid; place-items: center; margin-top: 18px; border-radius: 8px; background: #17202a; color: #fff; font: 700 10px Consolas, monospace; }
.message-user .message-avatar { background: #dce5f5; color: #345287; }
.message-column { max-width: min(88%, 700px); min-width: 0; }
.message-user .message-column { display: flex; flex-direction: column; align-items: flex-end; }
.message-meta { margin: 0 5px 6px; color: #8390a1; font-size: 10px; font-weight: 700; }
.message-bubble { min-width: 56px; padding: 15px 17px; border: 1px solid #dfe5ec; border-radius: 5px 17px 17px 17px; background: #fff; box-shadow: 0 2px 10px rgba(30,43,59,.045); }
.message-user .message-bubble { border-color: #355fbd; border-radius: 17px 5px 17px 17px; background: #3767d6; color: #fff; box-shadow: 0 5px 16px rgba(55,103,214,.14); }
.message-content { font-size: 14px; line-height: 1.72; white-space: pre-wrap; overflow-wrap: anywhere; }
.agent-trace { min-width: min(520px, 65vw); margin-bottom: 11px; padding: 13px 15px; border: 1px solid #dfe5ec; border-radius: 5px 14px 14px 14px; background: rgba(255,255,255,.62); }
.trace-heading { display: flex; justify-content: space-between; margin-bottom: 12px; color: #7d8999; font: 700 9px Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.waiting-state { min-height: 24px; display: flex; align-items: center; gap: 9px; padding: 2px 4px; color: #7d8999; font: 500 11px Consolas, monospace; }
.waiting-pulse { display: flex; gap: 3px; }
.waiting-pulse i { width: 4px; height: 4px; border-radius: 50%; background: #7690c7; animation: bounce 1.2s infinite ease-in-out; }
.waiting-pulse i:nth-child(2) { animation-delay: .12s; }.waiting-pulse i:nth-child(3) { animation-delay: .24s; }
.typing-caret { display: inline-block; width: 1.5px; height: 1em; margin-left: 2px; vertical-align: -.12em; background: #3767d6; animation: caret-blink .8s steps(1) infinite; }
.empty-state { width: min(660px, calc(100% - 40px)); min-height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; margin: 0 auto; padding: 48px 0 120px; text-align: center; }
.empty-mark { width: 58px; height: 58px; display: grid; place-items: center; margin-bottom: 22px; border: 1px solid #d6dee8; border-radius: 17px; background: #fff; color: #3767d6; box-shadow: 0 10px 30px rgba(30,43,59,.07); transform: rotate(-3deg); }
.empty-mark span { font: 700 16px Consolas, monospace; transform: rotate(3deg); }
.empty-eyebrow { margin: 0 0 8px; color: #74839a; font: 700 10px Consolas, monospace; letter-spacing: .1em; text-transform: uppercase; }
.empty-state h2 { margin: 0; color: #202b38; font-size: 25px; letter-spacing: -.025em; }
.empty-state > p:not(.empty-eyebrow) { max-width: 470px; margin: 12px 0 25px; color: #748093; font-size: 13px; line-height: 1.65; }
.prompt-examples { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.prompt-examples button { padding: 9px 12px; border: 1px solid #d9e0e8; border-radius: 9px; background: rgba(255,255,255,.72); color: #526176; font: 600 11px Lato, sans-serif; cursor: pointer; }
.prompt-examples button:hover { border-color: #b9c7d9; background: #fff; color: #315cae; }
.composer-wrap { width: min(840px, calc(100% - 40px)); flex: 0 0 auto; margin: 0 auto; padding: 0 0 16px; }
.notice { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 8px; padding: 8px 11px; border: 1px solid #ead8b8; border-radius: 8px; background: #fff9ed; color: #845f24; font-size: 11px; }
.notice button { border: 0; background: none; color: inherit; cursor: pointer; }
.composer { padding: 12px 13px 10px 16px; border: 1px solid #cfd8e3; border-radius: 16px; background: #fff; box-shadow: 0 9px 28px rgba(30,43,59,.09); transition: border-color .16s, box-shadow .16s; }
.composer:focus-within { border-color: #8ca8e4; box-shadow: 0 9px 28px rgba(30,43,59,.09), 0 0 0 3px rgba(55,103,214,.08); }
.composer textarea { width: 100%; max-height: 180px; resize: none; border: 0; outline: 0; background: transparent; color: #273445; font: 14px/1.55 Lato, "Microsoft YaHei", sans-serif; }
.composer textarea::placeholder { color: #9aa5b2; }
.composer textarea:disabled { cursor: not-allowed; }
.composer-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 7px; }
.composer-foot > span { color: #a0aab6; font: 500 9px Consolas, monospace; }
.composer-foot button { width: 31px; height: 31px; display: grid; place-items: center; border: 0; border-radius: 9px; background: #263343; color: #fff; cursor: pointer; }
.composer-foot button:disabled { background: #dbe1e8; color: #98a3b1; cursor: default; }
.composer-foot button:not(:disabled):hover { background: #3767d6; }
.composer-foot svg { width: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
.composer-note { margin: 7px 0 0; color: #9ba5b2; font-size: 9px; text-align: center; }
@keyframes bounce { 0%,60%,100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-3px); opacity: 1; } }
@keyframes caret-blink { 50% { opacity: 0; } }
@media (max-width: 760px) {
  .chat-header { height: 60px; flex-basis: 60px; padding: 0 14px; }
  .menu-button { display: grid; }
  .model-chip { display: none; }
  .conversation { width: calc(100% - 24px); padding-top: 25px; }
  .message-column { max-width: calc(100% - 39px); }
  .message-bubble { padding: 13px 14px; }
  .agent-trace { min-width: min(68vw, 440px); }
  .composer-wrap { width: calc(100% - 20px); padding-bottom: 9px; }
  .composer-foot > span { display: none; }
  .composer-foot { justify-content: flex-end; }
  .empty-state { width: calc(100% - 32px); padding-bottom: 80px; }
}
@media (prefers-reduced-motion: reduce) { .messages-area { scroll-behavior: auto; } .waiting-pulse i, .typing-caret { animation: none; } .composer { transition: none; } }
</style>

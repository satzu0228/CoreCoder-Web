<template>
  <aside class="session-sidebar" :class="{ 'is-open': store.sidebarOpen }">
    <div class="workspace-mark">
      <div class="brand-glyph" aria-hidden="true">C</div>
      <div class="workspace-copy">
        <span class="product-name">CoreCoder</span>
        <strong :title="store.workspaceName">{{ store.workspaceName }}</strong>
      </div>
      <button class="mobile-close" type="button" aria-label="关闭对话列表" @click="store.sidebarOpen = false">×</button>
    </div>

    <button class="new-chat" type="button" @click="handleCreate">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      新建对话
      <span class="new-chat-key">Ctrl N</span>
    </button>

    <div class="history-label">
      <span>对话记录</span>
      <span>{{ store.sessions.length }}</span>
    </div>

    <nav class="session-list" aria-label="工作空间对话">
      <button
        v-for="session in store.sessions"
        :key="session.id"
        type="button"
        class="session-item"
        :class="{ active: session.id === store.activeSessionId }"
        @click="selectSession(session.id)"
      >
        <span class="session-state" :class="`state-${session.status}`" aria-hidden="true"></span>
        <span class="session-main">
          <input
            v-if="editingId === session.id"
            ref="renameInput"
            v-model="editingTitle"
            class="rename-input"
            maxlength="80"
            @click.stop
            @keydown.enter.prevent="commitRename(session.id)"
            @keydown.escape.prevent="editingId = null"
            @blur="commitRename(session.id)"
          />
          <span v-else class="session-title">{{ session.title }}</span>
          <span class="session-preview">{{ session.preview || statusLabel(session.status) }}</span>
        </span>
        <span class="session-time">{{ relativeTime(session.updated_at) }}</span>
        <span v-if="session.id === store.activeSessionId && editingId !== session.id" class="session-actions">
          <span class="action-icon" title="重命名" @click.stop="startRename(session.id, session.title)">✎</span>
          <span class="action-icon danger" title="删除" @click.stop="handleDelete(session.id, session.title)">×</span>
        </span>
      </button>
    </nav>

    <div class="sidebar-foot">
      <span class="connection-dot"></span>
      本地工作空间
      <span>仅你可见</span>
    </div>
  </aside>
  <button v-if="store.sidebarOpen" class="sidebar-scrim" aria-label="关闭对话列表" @click="store.sidebarOpen = false"></button>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useAgentStream } from '../composables/useAgentStream'
import { useChatStore, type SessionStatus } from '../stores/chatStore'

const store = useChatStore()
const { createSession, deleteSession, renameSession, selectSession } = useAgentStream()
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const renameInput = ref<HTMLInputElement[] | null>(null)

function statusLabel(status: SessionStatus) {
  return ({
    idle: '暂无消息', running: '正在执行…', waiting_confirmation: '等待确认',
    interrupted: '上次运行已中断', error: '运行失败',
  })[status]
}

function relativeTime(value: string) {
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return ''
  const seconds = Math.max(0, (Date.now() - timestamp) / 1000)
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(timestamp)
}

async function handleCreate() {
  try { await createSession() } catch (error) { store.notice = String(error) }
}

async function startRename(id: string, title: string) {
  editingId.value = id
  editingTitle.value = title
  await nextTick()
  renameInput.value?.[0]?.focus()
  renameInput.value?.[0]?.select()
}

async function commitRename(id: string) {
  if (editingId.value !== id) return
  const title = editingTitle.value.trim()
  editingId.value = null
  if (!title) return
  try { await renameSession(id, title) } catch (error) { store.notice = String(error) }
}

async function handleDelete(id: string, title: string) {
  if (!window.confirm(`删除“${title}”？此操作无法撤销。`)) return
  try { await deleteSession(id) } catch (error) { store.notice = error instanceof Error ? error.message : String(error) }
}

function onShortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
    event.preventDefault()
    void handleCreate()
  }
}

onMounted(() => window.addEventListener('keydown', onShortcut))
onUnmounted(() => window.removeEventListener('keydown', onShortcut))
</script>

<style scoped>
.session-sidebar { width: 284px; height: 100%; flex: 0 0 284px; display: flex; flex-direction: column; padding: 18px 14px 12px; background: #eef2f6; border-right: 1px solid #dfe5ec; color: #263343; }
.workspace-mark { display: flex; align-items: center; gap: 11px; min-height: 42px; padding: 0 5px; }
.brand-glyph { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; background: #17202a; color: #fff; font: 700 15px/1 Consolas, monospace; box-shadow: inset 0 0 0 1px rgba(255,255,255,.1); }
.workspace-copy { min-width: 0; display: flex; flex: 1; flex-direction: column; line-height: 1.15; }
.product-name { color: #728094; font: 600 10px/1.3 Consolas, monospace; letter-spacing: .1em; text-transform: uppercase; }
.workspace-copy strong { overflow: hidden; margin-top: 3px; font-size: 14px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.mobile-close { display: none; border: 0; background: none; color: #657286; font-size: 24px; }
.new-chat { width: 100%; height: 42px; display: flex; align-items: center; gap: 9px; margin: 20px 0 22px; padding: 0 12px; border: 1px solid #ccd5e0; border-radius: 11px; background: rgba(255,255,255,.72); color: #263343; font: 700 13px Lato, sans-serif; cursor: pointer; box-shadow: 0 1px 2px rgba(23,32,42,.04); transition: background .16s, border-color .16s, transform .16s; }
.new-chat:hover { border-color: #aebac9; background: #fff; transform: translateY(-1px); }
.new-chat:focus-visible { outline: 3px solid rgba(55,103,214,.22); outline-offset: 2px; }
.new-chat svg { width: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-width: 1.8; }
.new-chat-key { margin-left: auto; color: #8995a5; font: 500 10px Consolas, monospace; }
.history-label { display: flex; justify-content: space-between; padding: 0 8px 8px; color: #7a8798; font: 700 10px Consolas, monospace; letter-spacing: .08em; text-transform: uppercase; }
.session-list { min-height: 0; flex: 1; overflow-y: auto; padding: 2px; scrollbar-width: thin; }
.session-item { position: relative; width: 100%; min-height: 66px; display: grid; grid-template-columns: 8px minmax(0,1fr) auto; align-items: start; gap: 9px; margin-bottom: 4px; padding: 11px 10px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.session-item:hover { background: rgba(255,255,255,.58); }
.session-item.active { border-color: #d8e0e9; background: #fff; box-shadow: 0 2px 8px rgba(24,38,57,.05); }
.session-state { width: 6px; height: 6px; margin-top: 6px; border-radius: 50%; background: #b1bbc7; }
.state-running { background: #3767d6; box-shadow: 0 0 0 4px rgba(55,103,214,.11); animation: pulse 1.6s ease-in-out infinite; }
.state-waiting_confirmation { background: #d18b26; box-shadow: 0 0 0 4px rgba(209,139,38,.12); }
.state-error { background: #c95454; }
.state-interrupted { background: #8c6fba; }
.session-main { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.session-title { overflow: hidden; color: #263343; font-size: 13px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.session-preview { overflow: hidden; color: #8490a0; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.session-time { color: #98a3b1; font: 500 9px Consolas, monospace; white-space: nowrap; }
.session-actions { position: absolute; right: 7px; bottom: 7px; display: flex; gap: 2px; padding-left: 12px; background: linear-gradient(90deg, transparent, #fff 28%); }
.action-icon { width: 22px; height: 22px; display: grid; place-items: center; border-radius: 6px; color: #758294; font-size: 13px; }
.action-icon:hover { background: #edf1f5; color: #263343; }
.action-icon.danger:hover { background: #fff0f0; color: #b33f3f; }
.rename-input { width: 100%; border: 0; border-bottom: 1px solid #3767d6; outline: 0; background: transparent; color: #263343; font: 700 13px Lato, sans-serif; }
.sidebar-foot { display: grid; grid-template-columns: 8px 1fr auto; align-items: center; gap: 8px; padding: 12px 8px 2px; border-top: 1px solid #dce3eb; color: #738093; font-size: 10px; }
.sidebar-foot > span:last-child { color: #9aa5b2; }
.connection-dot { width: 6px; height: 6px; border-radius: 50%; background: #1f8a78; }
.sidebar-scrim { display: none; }
@keyframes pulse { 50% { opacity: .45; } }
@media (max-width: 760px) {
  .session-sidebar { position: fixed; inset: 0 auto 0 0; z-index: 50; width: min(88vw, 310px); transform: translateX(-102%); box-shadow: 20px 0 50px rgba(23,32,42,.16); transition: transform .22s ease; }
  .session-sidebar.is-open { transform: translateX(0); }
  .mobile-close { display: block; cursor: pointer; }
  .sidebar-scrim { position: fixed; inset: 0; z-index: 40; display: block; border: 0; background: rgba(20,29,40,.35); }
}
@media (prefers-reduced-motion: reduce) { .state-running { animation: none; } .session-sidebar, .new-chat { transition: none; } }
</style>

<template>
  <aside
    class="w-[284px] h-full shrink-0 flex flex-col px-[14px] pt-[18px] pb-3 bg-brand-100 border-r border-brand-200 text-brand-800
           max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:w-[min(88vw,310px)] max-md:shadow-[20px_0_50px_rgba(23,32,42,.16)] max-md:transition-transform max-md:duration-[220ms] max-md:ease max-md:-translate-x-[102%]"
    :class="{ 'is-open': store.sidebarOpen }"
  >
    <div class="flex items-center gap-[11px] min-h-[42px] px-[5px]">
      <div class="w-8 h-8 grid place-items-center rounded-[9px] bg-brand-950 text-white font-bold text-[15px] font-mono shadow-[inset_0_0_0_1px_rgba(255,255,255,.1)]" aria-hidden="true">C</div>
      <div class="min-w-0 flex flex-col flex-1 leading-[1.15]">
        <span class="text-brand-600 font-semibold text-[10px] font-mono tracking-[0.1em] uppercase">CoreCoder</span>
        <strong class="overflow-hidden mt-[3px] text-sm font-bold truncate" :title="store.workspaceName">{{ store.workspaceName }}</strong>
      </div>
      <button class="hidden max-md:block border-0 bg-transparent text-brand-600 text-2xl cursor-pointer" type="button" aria-label="关闭对话列表" @click="store.sidebarOpen = false">×</button>
    </div>

    <button
      class="w-full h-[42px] flex items-center gap-[9px] mt-5 mb-[22px] px-3 border border-brand-300 rounded-[11px] bg-white/70 text-brand-800 font-bold text-[13px] cursor-pointer shadow-[0_1px_2px_rgba(23,32,42,.04)] transition-all duration-[160ms] hover:border-brand-400 hover:bg-white hover:-translate-y-px focus-visible:outline-[3px] focus-visible:outline-primary-500/20 focus-visible:outline-offset-2"
      type="button"
      @click="handleCreate"
    >
      <svg class="w-[17px] fill-none stroke-current" style="stroke-linecap:round;stroke-width:1.8" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      新建对话
      <span class="ml-auto text-brand-500 font-medium text-[10px] font-mono">Ctrl N</span>
    </button>

    <div class="flex justify-between px-2 pb-2 text-brand-500 font-bold text-[10px] font-mono tracking-[0.08em] uppercase">
      <span>对话记录</span>
      <span>{{ store.sessions.length }}</span>
    </div>

    <nav class="min-h-0 flex-1 overflow-y-auto p-0.5 scrollbar-thin" aria-label="工作空间对话">
      <button
        v-for="session in store.sessions"
        :key="session.id"
        type="button"
        class="relative w-full min-h-[66px] grid grid-cols-[8px_minmax(0,1fr)_auto] items-start gap-[9px] mb-1 px-[10px] py-[11px] border border-transparent rounded-[10px] bg-transparent text-left cursor-pointer hover:bg-white/60"
        :class="{ active: session.id === store.activeSessionId }"
        @click="selectSession(session.id)"
      >
        <span class="w-1.5 h-1.5 mt-1.5 rounded-full bg-brand-300" :class="`state-${session.status}`" aria-hidden="true"></span>
        <span class="min-w-0 flex flex-col gap-[5px]">
          <input
            v-if="editingId === session.id"
            ref="renameInput"
            v-model="editingTitle"
            class="w-full border-0 border-b border-primary-500 outline-0 bg-transparent text-brand-800 font-bold text-[13px]"
            maxlength="80"
            @click.stop
            @keydown.enter.prevent="commitRename(session.id)"
            @keydown.escape.prevent="editingId = null"
            @blur="commitRename(session.id)"
          />
          <span v-else class="overflow-hidden text-brand-800 text-[13px] font-bold truncate">{{ session.title }}</span>
          <span class="overflow-hidden text-brand-500 text-[11px] truncate">{{ session.preview || statusLabel(session.status) }}</span>
        </span>
        <span class="text-brand-400 font-medium text-[9px] font-mono whitespace-nowrap">{{ relativeTime(session.updated_at) }}</span>
        <span v-if="session.id === store.activeSessionId && editingId !== session.id" class="session-actions">
          <span class="action-icon" title="重命名" @click.stop="startRename(session.id, session.title)">✎</span>
          <span class="action-icon danger" title="删除" @click.stop="handleDelete(session.id, session.title)">×</span>
        </span>
      </button>
    </nav>

    <div class="grid grid-cols-[8px_1fr_auto] items-center gap-2 pt-3 pb-0.5 px-2 border-t border-brand-200 text-brand-600 text-[10px]">
      <span class="w-1.5 h-1.5 rounded-full bg-success"></span>
      本地工作空间
      <span class="text-brand-400">仅你可见</span>
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
    cancelling: '正在停止', cancelled: '已取消',
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
  if (!window.confirm(`删除"${title}"？此操作无法撤销。`)) return
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
/* 动画 + reduced-motion + 移动端侧边栏叠加层 + 操作按钮渐变 */
@keyframes pulse { 50% { opacity: .45; } }
.is-open { transform: translateX(0) !important; }
.active { @apply border-brand-200 bg-white shadow-[0_2px_8px_rgba(24,38,57,.05)]; }
.state-running { @apply bg-primary-500 shadow-[0_0_0_4px_rgba(55,103,214,.11)]; animation: pulse 1.6s ease-in-out infinite; }
.state-waiting_confirmation { @apply bg-warning shadow-[0_0_0_4px_rgba(209,139,38,.12)]; }
.state-error { @apply bg-danger; }
.state-interrupted { background: #8c6fba; }
.session-actions { position: absolute; right: 7px; bottom: 7px; display: flex; gap: 2px; padding-left: 12px; background: linear-gradient(90deg, transparent, #fff 28%); }
.action-icon { width: 22px; height: 22px; display: grid; place-items: center; border-radius: 6px; color: #758294; font-size: 13px; }
.action-icon:hover { @apply bg-brand-100 text-brand-800; }
.action-icon.danger:hover { background: #fff0f0; color: #b33f3f; }
.sidebar-scrim { @apply hidden max-md:block fixed inset-0 z-40 border-0 bg-brand-950/35; }
.scrollbar-thin { scrollbar-width: thin; }
@media (prefers-reduced-motion: reduce) {
  .state-running { animation: none; }
  aside, button { transition: none !important; }
}
</style>

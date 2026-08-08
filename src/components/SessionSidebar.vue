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
      class="w-full h-[42px] flex items-center gap-[9px] mt-5 mb-[14px] px-3 border border-brand-300 rounded-[11px] bg-white/70 text-brand-800 font-bold text-[13px] cursor-pointer shadow-[0_1px_2px_rgba(23,32,42,.04)] transition-all duration-[160ms] hover:border-brand-400 hover:bg-white hover:-translate-y-px focus-visible:outline-[3px] focus-visible:outline-primary-500/20 focus-visible:outline-offset-2"
      type="button"
      @click="handleCreate"
    >
      <svg class="w-[17px] fill-none stroke-current" style="stroke-linecap:round;stroke-width:1.8" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      新建对话
      <span class="ml-auto text-brand-500 font-medium text-[10px] font-mono">Ctrl N</span>
    </button>

    <!-- 搜索框 -->
    <div class="relative mx-0.5 mb-2">
      <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 fill-none stroke-brand-400" style="stroke-width:1.8" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input
        v-model="searchText"
        type="text"
        placeholder="搜索对话…"
        class="w-full h-[34px] pl-7 pr-7 border border-brand-200 rounded-[9px] bg-white/60 text-brand-800 text-[12px] outline-0 placeholder:text-brand-400 focus:border-primary-300 focus:bg-white"
        @input="onSearchInput"
      />
      <button v-if="searchText" class="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 grid place-items-center border-0 bg-transparent text-brand-400 cursor-pointer text-xs" type="button" aria-label="清除搜索" @click="clearSearch">×</button>
    </div>

    <!-- 工具栏 -->
    <div class="flex justify-between items-center px-2 pb-2 text-brand-500 font-bold text-[10px] font-mono tracking-[0.08em] uppercase">
      <span>对话记录</span>
      <div class="flex items-center gap-1.5">
        <button v-if="!selectMode" class="border-0 bg-transparent text-brand-400 cursor-pointer text-[9px] hover:text-brand-700" type="button" @click="selectMode = true">选择</button>
        <button v-else class="border-0 bg-transparent text-brand-600 cursor-pointer text-[9px] hover:text-brand-800" type="button" @click="cancelSelectMode">取消</button>
        <span>{{ activeSessions.length }}</span>
      </div>
    </div>

    <nav class="min-h-0 flex-1 overflow-y-auto p-0.5 scrollbar-thin" aria-label="工作空间对话">
      <div
        v-for="session in activeSessions"
        :key="session.id"
        class="session-row relative w-full min-h-[66px] mb-1 border border-transparent rounded-[10px]"
        :class="[sessionClass(session.id), { 'actions-open': openActionId === session.id }]"
      >
        <button
          type="button"
          class="session-main w-full min-h-[64px] grid items-start gap-[9px] px-[10px] py-[11px] border-0 rounded-[9px] bg-transparent text-left cursor-pointer"
          :style="{ gridTemplateColumns: selectMode ? '20px 8px minmax(0,1fr) auto' : '8px minmax(0,1fr) auto' }"
          @click="onSessionClick(session.id)"
        >
          <span v-if="selectMode" class="w-4 h-4 mt-1 rounded border-2 flex items-center justify-center" :class="selectedIds.has(session.id) ? 'border-primary-500 bg-primary-500' : 'border-brand-300 bg-white'">
            <svg v-if="selectedIds.has(session.id)" class="w-2.5 h-2.5 fill-none stroke-white" style="stroke-width:2.5" viewBox="0 0 10 10"><path d="M2 5l2 2 4-4"/></svg>
          </span>
          <span class="w-1.5 h-1.5 mt-1.5 rounded-full bg-brand-300" :class="`state-${session.status}`" aria-hidden="true"></span>
          <span class="session-copy min-w-0 flex flex-col gap-[5px]">
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
        </button>
        <button
          v-if="editingId !== session.id && !selectMode"
          class="session-menu-trigger"
          :class="{ visible: openActionId === session.id }"
          type="button"
          title="更多操作"
          aria-label="打开对话操作菜单"
          :aria-expanded="openActionId === session.id"
          @click.stop="toggleActionMenu(session.id, $event)"
        >
          <span></span><span></span><span></span>
        </button>
      </div>
    </nav>

    <!-- 已归档区域 -->
    <div v-if="archivedSessions.length" class="border-t border-brand-200 pt-1">
      <button class="flex items-center gap-[7px] w-full px-2 py-1.5 border-0 bg-transparent text-brand-500 font-bold text-[10px] font-mono tracking-[0.08em] uppercase cursor-pointer hover:text-brand-700" type="button" @click="showArchived = !showArchived">
        <svg viewBox="0 0 16 16" class="w-[13px] shrink-0 fill-none stroke-current transition-transform duration-[180ms]" style="stroke-width:1.5" :class="{ 'rotate-[-90deg]': !showArchived }" aria-hidden="true">
          <path d="m5 6 3 3 3-3" />
        </svg>
        <span>已归档</span>
        <span class="ml-auto text-brand-400 text-[9px] font-sans">{{ archivedSessions.length }}</span>
      </button>
      <div v-show="showArchived" class="max-h-[160px] overflow-y-auto scrollbar-thin">
        <button
          v-for="session in archivedSessions"
          :key="session.id"
          type="button"
          class="relative w-full min-h-[52px] grid grid-cols-[8px_minmax(0,1fr)_auto] items-start gap-[9px] mb-1 px-[10px] py-[8px] border border-transparent rounded-[10px] bg-transparent text-left cursor-pointer hover:bg-white/60"
          @click="selectSession(session.id)"
        >
          <span class="w-1.5 h-1.5 mt-1.5 rounded-full bg-brand-300" aria-hidden="true"></span>
          <span class="min-w-0 flex flex-col gap-[3px]">
            <span class="overflow-hidden text-brand-600 text-[12px] font-bold truncate">{{ session.title }}</span>
            <span class="overflow-hidden text-brand-400 text-[10px] truncate">{{ relativeTime(session.updated_at) }}</span>
          </span>
          <span class="action-icon" title="取消归档" @click.stop="handleArchive(session.id)">↩</span>
        </button>
      </div>
    </div>

    <!-- 批量删除操作栏 -->
    <div v-if="selectMode && selectedIds.size > 0" class="flex items-center gap-2 px-3 py-2 border-t border-brand-200 bg-brand-50">
      <span class="text-brand-600 text-[11px] font-bold">已选 {{ selectedIds.size }}</span>
      <button class="ml-auto px-3 py-1 border-0 rounded-md bg-danger text-white text-[11px] cursor-pointer hover:bg-[#b33a3a]" type="button" @click="handleBatchDelete">删除</button>
    </div>

    <div class="grid grid-cols-[8px_1fr_auto] items-center gap-2 pt-3 pb-0.5 px-2 border-t border-brand-200 text-brand-600 text-[10px]">
      <span class="w-1.5 h-1.5 rounded-full bg-success"></span>
      本地工作空间
      <span class="text-brand-400">仅你可见</span>
    </div>
  </aside>
  <Teleport to="body">
    <div
      v-if="openActionId"
      class="session-action-menu"
      :style="actionMenuStyle"
      role="menu"
      @click.stop
    >
      <button type="button" role="menuitem" @click="handleMenuRename">重命名</button>
      <button type="button" role="menuitem" @click="handleMenuArchive">归档</button>
      <button class="danger" type="button" role="menuitem" @click="handleMenuDelete">删除</button>
    </div>
  </Teleport>
  <button v-if="store.sidebarOpen" class="sidebar-scrim" aria-label="关闭对话列表" @click="store.sidebarOpen = false"></button>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useAgentStream } from '../composables/useAgentStream'
import { useChatStore, type SessionStatus } from '../stores/chatStore'

const store = useChatStore()
const { createSession, deleteSession, renameSession, selectSession, toggleArchive, batchDeleteSessions, refreshSessions } = useAgentStream()
const editingId = ref<string | null>(null)
const editingTitle = ref('')
const renameInput = ref<HTMLInputElement[] | null>(null)
const searchText = ref('')
const showArchived = ref(false)
const selectMode = ref(false)
const selectedIds = ref(new Set<string>())
const openActionId = ref<string | null>(null)
const actionMenuPosition = ref({ top: 0, left: 0 })
let searchTimer: number | null = null

const activeSessions = computed(() => store.sessions.filter(s => !s.archived))
const archivedSessions = computed(() => store.sessions.filter(s => s.archived))
const actionMenuStyle = computed(() => ({
  top: `${actionMenuPosition.value.top}px`,
  left: `${actionMenuPosition.value.left}px`,
}))

function sessionClass(id: string) {
  const classes: string[] = []
  if (id === store.activeSessionId) classes.push('active')
  return classes.join(' ')
}

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

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    const q = searchText.value.trim()
    store.searchQuery = q
    void refreshSessions(q || undefined, q ? true : false)
  }, 200)
}

function clearSearch() {
  searchText.value = ''
  store.searchQuery = ''
  void refreshSessions()
}

function onSessionClick(id: string) {
  if (selectMode.value) {
    toggleSelect(id)
  } else {
    void selectSession(id)
  }
}

function toggleSelect(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function cancelSelectMode() {
  selectMode.value = false
  selectedIds.value = new Set()
}

function toggleActionMenu(id: string, event: MouseEvent) {
  if (openActionId.value === id) {
    openActionId.value = null
    return
  }
  const trigger = event.currentTarget as HTMLElement
  const rect = trigger.getBoundingClientRect()
  const menuWidth = 124
  const menuHeight = 112
  const top = rect.bottom + 6 + menuHeight <= window.innerHeight
    ? rect.bottom + 6
    : Math.max(8, rect.top - menuHeight - 6)
  actionMenuPosition.value = {
    top,
    left: Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8)),
  }
  openActionId.value = id
}

function closeActionMenu() {
  openActionId.value = null
}

function actionSession() {
  return store.sessions.find(session => session.id === openActionId.value)
}

function handleMenuRename() {
  const session = actionSession()
  closeActionMenu()
  if (session) void startRename(session.id, session.title)
}

function handleMenuArchive() {
  const session = actionSession()
  closeActionMenu()
  if (session) void handleArchive(session.id)
}

function handleMenuDelete() {
  const session = actionSession()
  closeActionMenu()
  if (session) void handleDelete(session.id, session.title)
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

async function handleArchive(id: string) {
  try { await toggleArchive(id) } catch (error) { store.notice = String(error) }
}

async function handleDelete(id: string, title: string) {
  if (!window.confirm(`删除"${title}"？此操作无法撤销。`)) return
  try { await deleteSession(id) } catch (error) { store.notice = error instanceof Error ? error.message : String(error) }
}

async function handleBatchDelete() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!window.confirm(`确定删除 ${ids.length} 个对话？此操作无法撤销。`)) return
  try {
    await batchDeleteSessions(ids)
    cancelSelectMode()
  } catch (error) {
    store.notice = error instanceof Error ? error.message : String(error)
  }
}

function onShortcut(event: KeyboardEvent) {
  if (event.key === 'Escape' && openActionId.value) {
    closeActionMenu()
    return
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') {
    event.preventDefault()
    void handleCreate()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onShortcut)
  window.addEventListener('click', closeActionMenu)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onShortcut)
  window.removeEventListener('click', closeActionMenu)
})
</script>

<style scoped>
/* 动画 + reduced-motion + 移动端侧边栏叠加层 + 操作按钮渐变 */
@keyframes pulse { 50% { opacity: .45; } }
.is-open { transform: translateX(0) !important; }
.session-row { transition: background-color .16s, border-color .16s, box-shadow .16s; }
.session-row:hover { @apply bg-white/60; }
.active { @apply border-brand-200 bg-white shadow-[0_2px_8px_rgba(24,38,57,.05)]; }
.state-running { @apply bg-primary-500 shadow-[0_0_0_4px_rgba(55,103,214,.11)]; animation: pulse 1.6s ease-in-out infinite; }
.state-waiting_confirmation { @apply bg-warning shadow-[0_0_0_4px_rgba(209,139,38,.12)]; }
.state-error { @apply bg-danger; }
.state-interrupted { background: #8c6fba; }
.session-copy { transition: padding-right .16s; }
.session-menu-trigger { position: absolute; right: 7px; bottom: 7px; width: 25px; height: 22px; display: flex; align-items: center; justify-content: center; gap: 2.5px; padding: 0; border: 0; border-radius: 6px; opacity: 0; visibility: hidden; transform: translateY(2px); pointer-events: none; background: rgba(255,255,255,.96); color: #758294; cursor: pointer; transition: opacity .14s, transform .14s, visibility .14s, background-color .14s; }
.session-menu-trigger span { width: 3px; height: 3px; border-radius: 50%; background: currentColor; }
.session-menu-trigger:hover { @apply bg-brand-100 text-brand-800; }
.session-row:hover .session-menu-trigger,
.session-row:has(.session-main:focus-visible) .session-menu-trigger,
.session-menu-trigger.visible { opacity: 1; visibility: visible; transform: translateY(0); pointer-events: auto; }
.session-row:hover .session-copy,
.session-row:has(.session-main:focus-visible) .session-copy,
.session-row.actions-open .session-copy { padding-right: 28px; }
.action-icon { width: 22px; height: 22px; display: grid; place-items: center; padding: 0; border: 0; border-radius: 6px; background: transparent; color: #758294; font-size: 13px; cursor: pointer; }
.action-icon:hover { @apply bg-brand-100 text-brand-800; }
.action-icon.danger:hover { background: #fff0f0; color: #b33f3f; }
.sidebar-scrim { @apply hidden max-md:block fixed inset-0 z-40 border-0 bg-brand-950/35; }
.scrollbar-thin { scrollbar-width: thin; }
@media (prefers-reduced-motion: reduce) {
  .state-running { animation: none; }
  aside, button { transition: none !important; }
}
@media (hover: none) {
  .session-row.active .session-menu-trigger { opacity: 1; visibility: visible; transform: none; pointer-events: auto; }
  .session-row.active .session-copy { padding-right: 28px; }
}
</style>

<style>
.session-action-menu { position: fixed; z-index: 210; width: 124px; padding: 5px; border: 1px solid #d9e0e8; border-radius: 10px; background: #fff; box-shadow: 0 12px 30px rgba(23,32,42,.16); }
.session-action-menu button { width: 100%; height: 32px; display: flex; align-items: center; padding: 0 10px; border: 0; border-radius: 7px; background: transparent; color: #526071; font-size: 12px; font-weight: 600; text-align: left; cursor: pointer; }
.session-action-menu button:hover,
.session-action-menu button:focus-visible { background: #f0f3f7; color: #1e2b3b; outline: none; }
.session-action-menu button.danger { color: #b33f3f; }
.session-action-menu button.danger:hover,
.session-action-menu button.danger:focus-visible { background: #fff0f0; }
</style>

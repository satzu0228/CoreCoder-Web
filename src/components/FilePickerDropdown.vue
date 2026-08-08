<template>
  <div class="relative" ref="rootEl">
    <button
      type="button"
      class="w-[31px] h-[31px] grid place-items-center border border-brand-200 rounded-[9px] bg-white/70 text-brand-500 cursor-pointer hover:border-brand-300 hover:text-primary-600 transition-colors"
      title="插入文件引用"
      @click="toggle"
    >
      <svg class="w-[15px] fill-none stroke-current" style="stroke-linecap:round;stroke-linejoin:round;stroke-width:1.8" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12M10 4v12"/></svg>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        class="fixed z-[200] w-[min(420px,88vw)] border border-brand-200 rounded-[13px] bg-white shadow-[0_16px_44px_rgba(23,32,42,.15)] overflow-hidden"
        :style="popoverStyle"
      >
        <!-- 搜索 -->
        <div class="flex items-center gap-2 px-3 py-2 border-b border-brand-100">
          <svg class="w-3.5 h-3.5 shrink-0 fill-none stroke-brand-400" style="stroke-width:1.8" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <input
            ref="searchInput"
            v-model="filterText"
            type="text"
            placeholder="搜索文件…"
            class="flex-1 border-0 outline-0 bg-transparent text-brand-800 text-[12px] placeholder:text-brand-400"
            @input="onFilterInput"
            @keydown="onKeydown"
          />
        </div>
        <!-- 面包屑 -->
        <div v-if="currentPath !== '.'" class="flex items-center gap-1 px-3 py-1.5 text-[10px] font-mono text-brand-500 border-b border-brand-100 bg-brand-50">
          <button class="border-0 bg-transparent text-primary-500 cursor-pointer hover:text-primary-700" type="button" @click="navigateTo('.')">~</button>
          <span v-for="(seg, i) in pathSegments" :key="i" class="flex items-center gap-1">
            <span class="text-brand-300">/</span>
            <button
              v-if="i < pathSegments.length - 1"
              class="border-0 bg-transparent text-primary-500 cursor-pointer hover:text-primary-700"
              type="button"
              @click="navigateTo(pathSegments.slice(0, i + 1).join('/'))"
            >{{ seg }}</button>
            <span v-else class="text-brand-700 font-bold">{{ seg }}</span>
          </span>
        </div>
        <!-- 条目列表 -->
        <div class="max-h-[260px] overflow-y-auto scrollbar-thin">
          <div v-if="loading" class="px-3 py-6 text-center text-brand-400 text-[11px]">加载中…</div>
          <div v-else-if="!filteredEntries.length" class="px-3 py-6 text-center text-brand-400 text-[11px]">无匹配文件</div>
          <button
            v-for="(entry, idx) in filteredEntries"
            :key="entry.path"
            :ref="el => { if (el) itemRefs[idx] = el as HTMLElement }"
            type="button"
            class="w-full flex items-center gap-2.5 px-3 py-[7px] border-0 bg-transparent text-left cursor-pointer hover:bg-brand-50 text-[12px]"
            :class="{ 'bg-brand-50': idx === highlightIndex }"
            @click="selectEntry(entry)"
          >
            <span v-if="entry.type === 'dir'" class="text-warning text-[13px] shrink-0">📁</span>
            <span v-else class="text-brand-400 text-[13px] shrink-0">📄</span>
            <span class="overflow-hidden text-brand-800 truncate">{{ entry.name }}</span>
            <span v-if="entry.type === 'dir'" class="ml-auto text-brand-300 text-[9px]">›</span>
          </button>
        </div>
        <!-- 底部提示 -->
        <div class="px-3 py-1.5 border-t border-brand-100 text-brand-400 text-[9px]">
          选择文件以插入引用 · Esc 关闭
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

interface TreeEntry {
  name: string
  type: 'dir' | 'file'
  path: string
}

const emit = defineEmits<{
  (e: 'select', path: string): void
}>()

const open = ref(false)
const loading = ref(false)
const entries = ref<TreeEntry[]>([])
const currentPath = ref('.')
const filterText = ref('')
const highlightIndex = ref(0)
const rootEl = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const itemRefs = ref<Record<number, HTMLElement>>({})
let filterTimer: number | null = null

const popoverStyle = computed(() => {
  if (!rootEl.value) return {}
  const rect = rootEl.value.getBoundingClientRect()
  return {
    left: `${Math.max(8, rect.left - 8)}px`,
    bottom: `${window.innerHeight - rect.top + 8}px`,
  }
})

const pathSegments = computed(() => {
  if (currentPath.value === '.') return []
  return currentPath.value.split('/').filter(Boolean)
})

const filteredEntries = computed(() => {
  if (!filterText.value.trim()) return entries.value
  const q = filterText.value.toLowerCase()
  return entries.value.filter(e => e.name.toLowerCase().includes(q))
})

async function fetchTree(path: string) {
  loading.value = true
  try {
    const token = sessionStorage.getItem('corecoder-token') || ''
    const response = await fetch(`/api/tree?path=${encodeURIComponent(path)}`, {
      headers: { 'X-CoreCoder-Token': token },
    })
    if (!response.ok) {
      entries.value = []
      return
    }
    const data = await response.json()
    entries.value = (data.entries || []) as TreeEntry[]
    highlightIndex.value = 0
  } catch {
    entries.value = []
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    currentPath.value = '.'
    filterText.value = ''
    void fetchTree('.')
    void nextTick(() => searchInput.value?.focus())
  }
}

function navigateTo(path: string) {
  currentPath.value = path
  filterText.value = ''
  void fetchTree(path)
  void nextTick(() => searchInput.value?.focus())
}

function selectEntry(entry: TreeEntry) {
  if (entry.type === 'dir') {
    navigateTo(entry.path)
    return
  }
  emit('select', entry.path)
  close()
}

function close() {
  open.value = false
  filterText.value = ''
}

function onFilterInput() {
  highlightIndex.value = 0
  if (filterTimer) clearTimeout(filterTimer)
  filterTimer = window.setTimeout(() => {
    // Keep highlight in bounds
    highlightIndex.value = Math.min(highlightIndex.value, Math.max(0, filteredEntries.value.length - 1))
  }, 100)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    highlightIndex.value = Math.min(highlightIndex.value + 1, filteredEntries.value.length - 1)
    scrollToHighlighted()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlightIndex.value = Math.max(0, highlightIndex.value - 1)
    scrollToHighlighted()
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const entry = filteredEntries.value[highlightIndex.value]
    if (entry) selectEntry(entry)
  } else if (event.key === 'Escape') {
    close()
  }
}

function scrollToHighlighted() {
  void nextTick(() => {
    const el = itemRefs.value[highlightIndex.value]
    el?.scrollIntoView({ block: 'nearest' })
  })
}

function onClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  // The popover is teleported to body — check if click is outside both root and popover
  if (rootEl.value && !rootEl.value.contains(target)) {
    // Check if click is on the teleported popover
    const popover = document.querySelector('.fixed.z-\\[200\\]')
    if (popover && !popover.contains(target)) {
      close()
    }
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<style scoped>
.scrollbar-thin { scrollbar-width: thin; }
</style>

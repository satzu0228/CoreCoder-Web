<template>
  <div class="file-tree">
    <div class="tree-header">
      <span>Files</span>
      <span v-if="rows.length > 1" class="file-count">{{ rows.length - 1 }}</span>
    </div>
    <div
      ref="viewport"
      class="tree-content"
      role="tree"
      @scroll="onScroll"
    >
      <div v-if="errorMessage" class="tree-message tree-error">{{ errorMessage }}</div>
      <div v-if="!rootNode" class="tree-message">Loading workspace…</div>
      <template v-else>
        <div :style="{ height: `${topSpacer}px` }"></div>
        <button
          v-for="row in visibleRows"
          :key="row.node.path"
          type="button"
          class="tree-row"
          role="treeitem"
          :aria-level="row.node.depth + 1"
          :aria-expanded="row.node.type === 'dir' ? row.node.expanded : undefined"
          :style="{ paddingLeft: `${8 + row.node.depth * 14}px` }"
          @click="handleNodeClick(row.node)"
        >
          <span v-if="row.node.type === 'dir'" class="tree-icon">
            {{ row.node.loading ? '…' : row.node.expanded ? '▼' : '▶' }}
          </span>
          <span v-else class="tree-icon">·</span>
          <span class="node-name">{{ row.node.name }}</span>
        </button>
        <div :style="{ height: `${bottomSpacer}px` }"></div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

interface Props {
  token: string
}

interface ApiEntry {
  name: string
  path: string
  type: 'dir' | 'file'
}

interface TreeNode extends ApiEntry {
  depth: number
  children?: TreeNode[]
  expanded: boolean
  loaded: boolean
  loading: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  fileSelected: [{ path: string; content: string }]
}>()

const ROW_HEIGHT = 28
const OVERSCAN = 8
const rootNode = ref<TreeNode | null>(null)
const viewport = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportHeight = ref(400)
const errorMessage = ref('')
let resizeObserver: ResizeObserver | null = null

const rows = computed(() => {
  const flattened: TreeNode[] = []
  const visit = (node: TreeNode) => {
    flattened.push(node)
    if (node.type === 'dir' && node.expanded) {
      for (const child of node.children || []) visit(child)
    }
  }
  if (rootNode.value) visit(rootNode.value)
  return flattened
})

const startIndex = computed(() => Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN))
const endIndex = computed(() => Math.min(
  rows.value.length,
  Math.ceil((scrollTop.value + viewportHeight.value) / ROW_HEIGHT) + OVERSCAN,
))
const visibleRows = computed(() => rows.value
  .slice(startIndex.value, endIndex.value)
  .map((node, offset) => ({ node, index: startIndex.value + offset })))
const topSpacer = computed(() => startIndex.value * ROW_HEIGHT)
const bottomSpacer = computed(() => Math.max(0, (rows.value.length - endIndex.value) * ROW_HEIGHT))

function makeNode(entry: ApiEntry, depth: number): TreeNode {
  return { ...entry, depth, expanded: false, loaded: false, loading: false }
}

async function loadChildren(node: TreeNode) {
  if (node.loaded || node.loading) return
  node.loading = true
  try {
    const response = await fetch(`/api/tree?path=${encodeURIComponent(node.path)}`, {
      headers: { 'X-CoreCoder-Token': props.token },
    })
    const data = await response.json()
    if (!response.ok || data.error) throw new Error(data.error || `Request failed: ${response.status}`)
    node.children = (data.entries || []).map((entry: ApiEntry) => makeNode(entry, node.depth + 1))
    node.loaded = true
  } finally {
    node.loading = false
  }
}

async function loadTree() {
  if (!props.token) return
  errorMessage.value = ''
  const root = makeNode({ name: 'workspace', path: '.', type: 'dir' }, 0)
  root.expanded = true
  rootNode.value = root
  try {
    await loadChildren(root)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load workspace'
  }
}

async function handleNodeClick(node: TreeNode) {
  if (node.type === 'dir') {
    node.expanded = !node.expanded
    if (node.expanded && !node.loaded) {
      try {
        await loadChildren(node)
      } catch (error) {
        node.expanded = false
        errorMessage.value = error instanceof Error ? error.message : 'Failed to load directory'
      }
    }
    return
  }

  try {
    const response = await fetch(`/api/file?path=${encodeURIComponent(node.path)}`, {
      headers: { 'X-CoreCoder-Token': props.token },
    })
    const data = await response.json()
    if (!response.ok || data.error) throw new Error(data.error || `Request failed: ${response.status}`)
    emit('fileSelected', { path: node.path, content: data.content })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Failed to read file'
  }
}

function onScroll(event: Event) {
  scrollTop.value = (event.currentTarget as HTMLElement).scrollTop
}

watch(() => props.token, token => {
  if (token) void loadTree()
}, { immediate: true })

onMounted(() => {
  if (!viewport.value) return
  resizeObserver = new ResizeObserver(entries => {
    viewportHeight.value = entries[0]?.contentRect.height || 400
  })
  resizeObserver.observe(viewport.value)
})

onUnmounted(() => resizeObserver?.disconnect())
</script>

<style scoped>
.file-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid #e0e0e0;
  background: #fafafa;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #e0e0e0;
}

.file-count {
  color: #999;
  font-size: 11px;
  font-weight: 500;
}

.tree-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 0;
}

.tree-row {
  display: flex;
  align-items: center;
  width: 100%;
  height: 28px;
  gap: 6px;
  padding-top: 0;
  padding-right: 8px;
  padding-bottom: 0;
  color: #333;
  font: inherit;
  font-size: 13px;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.tree-row:hover,
.tree-row:focus-visible {
  background: #eceff3;
  outline: none;
}

.tree-icon {
  flex: 0 0 14px;
  color: #777;
  font-size: 10px;
  text-align: center;
}

.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-message {
  padding: 16px 12px;
  color: #777;
  font-size: 12px;
}

.tree-error {
  color: #b42318;
}
</style>

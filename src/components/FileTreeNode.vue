<template>
  <div class="tree-node">
    <div class="node-label" @click="handleClick">
      <span v-if="node.type === 'dir'" class="expand-icon">
        {{ expanded ? '▼' : '▶' }}
      </span>
      <span v-else class="file-icon">📄</span>
      <span class="node-name">{{ node.name }}</span>
    </div>
    <div v-if="expanded && childrenList.length > 0" class="children">
      <FileTreeNode
        v-for="child in childrenList"
        :key="child.path"
        :node="child"
        :token="token"
        :depth="depth + 1"
        @file-selected="$emit('fileSelected', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface TreeNode {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: TreeNode[]
}

interface Props {
  node: TreeNode
  token: string
  depth?: number
}

const props = withDefaults(defineProps<Props>(), {
  depth: 0
})

const emit = defineEmits<{
  fileSelected: [{ path: string; content: string }]
}>()

// Root node (depth 0) should be expanded by default
const expanded = ref(props.depth === 0)

const handleClick = async () => {
  if (props.node.type === 'file') {
    // Load file content
    try {
      const response = await fetch(`/api/file?path=${encodeURIComponent(props.node.path)}`, {
        headers: { 'x-corecoder-token': props.token }
      })
      if (!response.ok) {
        console.error('Failed to load file:', response.status)
        return
      }
      const data = await response.json()
      if (data.error) {
        console.error('File error:', data.error)
        return
      }
      emit('fileSelected', {
        path: props.node.path,
        content: data.content
      })
    } catch (error) {
      console.error('Error loading file:', error)
    }
  } else {
    // Toggle directory expansion
    expanded.value = !expanded.value
    if (expanded.value && (!props.node.children || props.node.children.length === 0)) {
      // Load children if not already loaded
      try {
        const response = await fetch(`/api/tree?path=${encodeURIComponent(props.node.path)}`, {
          headers: { 'x-corecoder-token': props.token }
        })
        if (!response.ok) {
          console.error('Failed to load tree:', response.status)
          expanded.value = false
          return
        }
        const data = await response.json()
        if (data.error) {
          console.error('Tree error:', data.error)
          expanded.value = false
          return
        }
        props.node.children = data.entries || []
      } catch (error) {
        console.error('Error loading tree:', error)
        expanded.value = false
      }
    }
  }
}

const childrenList = computed(() => props.node.children || [])
</script>

<style scoped>
.tree-node {
  user-select: none;
}

.node-label {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 13px;
  gap: 6px;
}

.node-label:hover {
  background: #f0f0f0;
}

.expand-icon {
  display: inline-block;
  width: 16px;
  text-align: center;
  font-size: 11px;
  color: #666;
}

.file-icon {
  display: inline-block;
  width: 16px;
  text-align: center;
  font-size: 12px;
}

.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.children {
  margin-left: 16px;
}
</style>

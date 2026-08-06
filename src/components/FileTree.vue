<template>
  <div class="file-tree">
    <div class="tree-header">Files</div>
    <div class="tree-content">
      <FileTreeNode
        v-if="rootNode"
        :node="rootNode"
        :token="token"
        @file-selected="onFileSelected"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import FileTreeNode from './FileTreeNode.vue'

interface Props {
  token: string
}

interface TreeNode {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: TreeNode[]
  expanded?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  fileSelected: [{ path: string; content: string }]
}>()

const rootNode = ref<TreeNode | null>(null)

const onFileSelected = (file: { path: string; content: string }) => {
  emit('fileSelected', file)
}

const loadTree = async () => {
  if (!props.token) {
    console.warn('Cannot load tree: token is not set')
    return
  }
  try {
    const response = await fetch(`/api/tree?path=.`, {
      headers: { 'x-corecoder-token': props.token }
    })
    if (!response.ok) {
      console.error('Failed to load tree:', response.status)
      return
    }
    const data = await response.json()
    if (data.error) {
      console.error('Tree error:', data.error)
      return
    }

    rootNode.value = {
      name: 'workspace',
      path: '.',
      type: 'dir',
      children: data.entries || [],
      expanded: true
    }
  } catch (error) {
    console.error('Error loading tree:', error)
  }
}

// Watch token and load tree when it becomes available
watch(() => props.token, (newToken) => {
  if (newToken) {
    loadTree()
  }
}, { immediate: true })
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
  padding: 12px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #e0e0e0;
}

.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
</style>

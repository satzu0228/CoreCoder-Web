<template>
  <div class="diff-viewer">
    <div v-if="loading" class="loading">Loading Monaco Editor...</div>
    <div ref="editorContainer" class="editor-container" :style="{ display: loading ? 'none' : undefined }"></div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'

interface Props {
  oldContent: string
  newContent: string
  fileName: string
}

const props = defineProps<Props>()

const editorContainer = ref<HTMLElement | null>(null)
const loading = ref(true)
let editor: any = null

onMounted(async () => {
  try {
    // Dynamically import Monaco Editor only when needed
    const monaco = await import('monaco-editor')

    loading.value = false
    await nextTick()

    if (!editorContainer.value) return

    editor = monaco.editor.createDiffEditor(editorContainer.value, {
      automaticLayout: true,
      readOnly: true,
      renderSideBySide: true,
      minimap: { enabled: true }
    })

    editor.setModel({
      original: monaco.editor.createModel(props.oldContent, 'text/plain'),
      modified: monaco.editor.createModel(props.newContent, 'text/plain')
    })
  } catch (error) {
    console.error('Failed to load Monaco Editor:', error)
    loading.value = false
  }
})
</script>

<style scoped>
.diff-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.editor-container {
  flex: 1;
  min-height: 0;
}
</style>

<template>
  <div class="diff-viewer">
    <div v-if="loading" class="loading">Loading Monaco Editor...</div>
    <div ref="editorContainer" class="editor-container" :style="{ display: loading ? 'none' : undefined }"></div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { languageForFile, loadMonaco } from '../lib/monaco'

interface Props {
  oldContent: string
  newContent: string
  fileName: string
}

const props = defineProps<Props>()

const editorContainer = ref<HTMLElement | null>(null)
const loading = ref(true)
let editor: import('monaco-editor/esm/vs/editor/editor.api').editor.IStandaloneDiffEditor | null = null
let originalModel: import('monaco-editor/esm/vs/editor/editor.api').editor.ITextModel | null = null
let modifiedModel: import('monaco-editor/esm/vs/editor/editor.api').editor.ITextModel | null = null

onMounted(async () => {
  try {
    const monaco = await loadMonaco()

    loading.value = false
    await nextTick()

    if (!editorContainer.value) return

    editor = monaco.editor.createDiffEditor(editorContainer.value, {
      automaticLayout: true,
      readOnly: true,
      renderSideBySide: true,
      minimap: { enabled: true }
    })

    const language = languageForFile(props.fileName)
    originalModel = monaco.editor.createModel(props.oldContent, language)
    modifiedModel = monaco.editor.createModel(props.newContent, language)
    editor.setModel({ original: originalModel, modified: modifiedModel })
  } catch (error) {
    console.error('Failed to load Monaco Editor:', error)
    loading.value = false
  }
})

onUnmounted(() => {
  editor?.dispose()
  originalModel?.dispose()
  modifiedModel?.dispose()
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

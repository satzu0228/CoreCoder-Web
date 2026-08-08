<template>
  <div class="flex flex-col h-full bg-white">
    <div v-if="loading" class="flex items-center justify-center h-full text-brand-500">Loading Monaco Editor...</div>
    <div ref="editorContainer" class="flex-1 min-h-0" :style="{ display: loading ? 'none' : undefined }"></div>
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

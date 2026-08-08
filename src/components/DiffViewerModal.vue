<template>
  <Teleport to="body">
    <div v-if="store.diffViewerOpen" class="fixed inset-0 z-[1100] flex items-center justify-center bg-brand-950/50 backdrop-blur-sm" @click="close">
      <div class="bg-white border border-white/35 rounded-2xl shadow-2xl w-[90%] max-w-[1200px] h-[80vh] max-h-[800px] flex flex-col" @click.stop>
        <div class="flex justify-between items-center py-[15px] px-[18px] border-b border-brand-200">
          <div>
            <span class="block mb-[3px] text-brand-500 font-bold text-[9px] font-mono tracking-widest uppercase">文件变更</span>
            <h3 class="m-0 text-brand-800 font-semibold text-xs font-mono">{{ store.diffViewerData.fileName }}</h3>
          </div>
          <button @click="close" class="bg-transparent border-0 cursor-pointer text-xl text-brand-600 p-1 hover:text-black" aria-label="关闭 diff">×</button>
        </div>
        <div class="flex-1 overflow-hidden">
          <DiffViewer
            :old-content="store.diffViewerData.oldContent"
            :new-content="store.diffViewerData.newContent"
            :file-name="store.diffViewerData.fileName"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useChatStore } from '../stores/chatStore'
import DiffViewer from './DiffViewer.vue'

const store = useChatStore()

const close = () => {
  store.closeDiffViewer()
}
</script>

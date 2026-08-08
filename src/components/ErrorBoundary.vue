<template>
  <div v-if="captured" class="mx-4 my-2 p-4 border border-[#f0c0c0] rounded-xl bg-[#fff5f5] text-[#b33a3a] text-sm">
    <p class="font-bold m-0 mb-1">{{ fallbackText || '页面发生错误' }}</p>
    <p class="m-0 mb-3 text-[#8a4444] leading-relaxed max-w-[600px]">{{ message }}</p>
    <button
      class="px-3 py-1.5 border border-[#e0b8b8] rounded-lg bg-white text-[#c95454] text-xs font-semibold cursor-pointer hover:bg-[#fff0f0]"
      @click="captured = null"
    >
      重试
    </button>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

defineProps<{ fallbackText?: string }>()

const captured = ref<unknown>(null)

const message = ref('')

onErrorCaptured((err: unknown, _instance, info: string) => {
  message.value = err instanceof Error ? err.message : String(err)
  captured.value = err
  console.error(`[ErrorBoundary] ${info}:`, err)
  return false // 阻止继续传播
})
</script>

<template>
  <div class="h-1.5 bg-white/10 rounded-full overflow-hidden">
    <div 
      class="h-full bg-gradient-to-r from-[#ffc107] to-[#ff9800] rounded-full transition-all duration-500"
      :style="{ width: `${percentage}%` }"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
}>()

const percentage = computed(() => {
  return Math.min(100, (props.score / 10) * 100)
})
</script>

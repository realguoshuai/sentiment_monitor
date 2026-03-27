<template>
  <span 
    class="inline-block px-4 py-1.5 rounded-full text-sm font-semibold"
    :class="badgeClass"
  >
    {{ label }} ({{ formattedScore }})
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  label: string
}>()

const badgeClass = computed(() => {
  if (props.score > 0.1) return 'bg-gradient-to-r from-[#00b09b] to-[#96c93d] text-white'
  if (props.score < -0.1) return 'bg-gradient-to-r from-[#ff6b6b] to-[#ee5a24] text-white'
  return 'bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white'
})

const formattedScore = computed(() => {
  const sign = props.score > 0 ? '+' : ''
  return `${sign}${props.score.toFixed(3)}`
})
</script>

<template>
  <div 
    class="glass-card border-white/5 hover:border-cyan-500/20 transition-all overflow-hidden"
    :class="compact ? 'p-2.5' : 'p-6'"
  >
    <div class="flex items-center justify-between">
      <div>
        <p class="text-gray-400" :class="compact ? 'text-[9px] -mb-0.5' : 'text-sm mb-1'">{{ title }}</p>
        <div class="flex items-baseline gap-2">
          <span class="font-bold text-white leading-tight" :class="compact ? 'text-lg' : 'text-3xl'">{{ value }}</span>
          <span v-if="subvalue" :class="[subvalueColor, compact ? 'text-[9px]' : 'text-sm']" class="font-medium">
            {{ subvalue }}
          </span>
        </div>
      </div>
      <div 
        :class="[iconBgClass, compact ? 'w-7 h-7 rounded-md' : 'w-12 h-12 rounded-xl']" 
        class="flex items-center justify-center shrink-0"
      >
        <svg :class="[iconColorClass, compact ? 'w-3.5 h-3.5' : 'w-6 h-6']" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <!-- Chart Icon -->
          <template v-if="icon === 'chart'">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </template>
          <!-- News Icon -->
          <template v-else-if="icon === 'news'">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9.5a2.5 2.5 0 00-2.5-2.5H15"/>
          </template>
          <!-- Doc Icon -->
          <template v-else-if="icon === 'doc'">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </template>
          <!-- Emoji Icon -->
          <template v-else-if="icon === 'emoji'">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </template>
        </svg>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  value: string | number
  subvalue?: string
  icon: 'chart' | 'news' | 'doc' | 'emoji'
  color: 'blue' | 'cyan' | 'purple' | 'green' | 'red' | 'yellow'
  compact?: boolean
}>(), {
  compact: false
})

const iconBgClass = computed(() => {
  const classes: Record<string, string> = {
    blue: 'bg-indigo-500/10',
    cyan: 'bg-cyan-500/10',
    purple: 'bg-violet-500/10',
    green: 'bg-emerald-500/10',
    red: 'bg-rose-500/10',
    yellow: 'bg-amber-500/10'
  }
  return classes[props.color]
})

const iconColorClass = computed(() => {
  const classes: Record<string, string> = {
    blue: 'text-indigo-400',
    cyan: 'text-cyan-400',
    purple: 'text-violet-400',
    green: 'text-emerald-400',
    red: 'text-rose-400',
    yellow: 'text-amber-400'
  }
  return classes[props.color]
})

const subvalueColor = computed(() => {
  const classes: Record<string, string> = {
    blue: 'text-indigo-400/80',
    cyan: 'text-cyan-400/80',
    purple: 'text-violet-400/80',
    green: 'text-emerald-400/80',
    red: 'text-rose-400/80',
    yellow: 'text-amber-400/80'
  }
  return classes[props.color]
})
</script>

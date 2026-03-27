<template>
  <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all">
    <div class="flex items-start gap-3">
      <span class="text-lg">{{ sourceIcon }}</span>
      <div class="flex-1 min-w-0">
        <a 
          v-if="item.url"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          class="text-indigo-700 font-bold hover:text-indigo-500 hover:underline cursor-pointer block break-words"
        >
          {{ item.title }}
        </a>
        <span v-else class="text-slate-800 font-medium break-words">{{ item.title }}</span>
        
        <div class="flex flex-wrap gap-4 mt-2 text-sm text-slate-500">
          <span class="text-emerald-700 font-bold">{{ source }}</span>
          <span>{{ item.pub_date }}</span>
          <span v-if="item.org" class="text-amber-700 font-bold">{{ item.org }}</span>
          <span v-if="item.rating" class="text-amber-600 font-bold">★ {{ item.rating }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { News, Report, Announcement } from '@/api'

const props = defineProps<{
  item: News | Report | Announcement
  type: string
}>()

const sourceIcons: Record<string, string> = {
  '东方财富': '📰',
  '机构调研': '📊',
  '巨潮资讯': '📋',
  '系统': '⚙️'
}

const source = computed(() => {
  if ('source' in props.item) return props.item.source
  if ('org' in props.item) return '机构研报'
  return '公告'
})

const sourceIcon = computed(() => {
  return sourceIcons[source.value] || '📄'
})
</script>

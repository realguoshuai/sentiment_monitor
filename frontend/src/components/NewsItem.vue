<template>
  <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all">
    <div class="flex items-start gap-3">
      <span class="text-lg">{{ sourceIcon }}</span>
      <div class="flex-1 min-w-0">
        <!-- 标题：点击跳转到主链接 -->
        <a
          v-if="primaryUrl"
          :href="primaryUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-indigo-700 font-bold hover:text-indigo-500 hover:underline cursor-pointer block break-words"
        >
          {{ item.title }}
        </a>
        <span v-else class="text-slate-800 font-medium break-words">{{ item.title }}</span>

        <!-- 元信息 -->
        <div class="flex flex-wrap items-center gap-3 mt-2 text-sm text-slate-500">
          <span class="text-emerald-700 font-bold">{{ source }}</span>
          <span>{{ item.pub_date }}</span>
          <span v-if="item.org" class="text-amber-700 font-bold">{{ item.org }}</span>
          <span v-if="item.rating" class="text-amber-600 font-bold">★ {{ item.rating }}</span>

          <!-- 多链接下拉 -->
          <div v-if="allLinks.length > 1" class="relative" ref="dropdownRef">
            <button
              @click.stop="showDropdown = !showDropdown"
              class="flex items-center gap-1 px-2 py-0.5 text-xs bg-slate-100 hover:bg-slate-200 rounded transition-colors"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
              </svg>
              {{ allLinks.length }} 个来源
            </button>
            <div
              v-if="showDropdown"
              class="absolute left-0 mt-1 w-64 bg-white rounded-lg shadow-lg border border-slate-200 z-50 py-1 max-h-48 overflow-y-auto"
            >
              <a
                v-for="(link, idx) in allLinks"
                :key="idx"
                :href="link"
                target="_blank"
                rel="noopener noreferrer"
                class="block px-3 py-2 text-xs text-slate-600 hover:bg-indigo-50 hover:text-indigo-600 truncate transition-colors"
                @click="showDropdown = false"
              >
                {{ formatUrl(link) }}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { News, Report, Announcement } from '@/api'

const props = defineProps<{
  item: News | Report | Announcement
  type: string
}>()

const showDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const sourceIcons: Record<string, string> = {
  '东方财富': '📰',
  '新浪财经': '📰',
  '雪球': '❄️',
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

// 获取主链接
const primaryUrl = computed(() => {
  return props.item.url || ''
})

// 获取所有链接
const allLinks = computed(() => {
  // 如果是 News 类型且有 urls 字段
  if ('urls' in props.item && Array.isArray(props.item.urls)) {
    const urls = props.item.urls.filter(u => u)
    return urls.length > 0 ? urls : (props.item.url ? [props.item.url] : [])
  }
  // 否则使用单个 url
  return props.item.url ? [props.item.url] : []
})

// 格式化 URL 显示
function formatUrl(url: string): string {
  try {
    const u = new URL(url)
    return u.hostname + u.pathname.substring(0, 30)
  } catch {
    return url.substring(0, 40)
  }
}

// 点击外部关闭下拉菜单
function handleClickOutside(event: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

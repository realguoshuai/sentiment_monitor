<template>
  <div class="space-y-4 text-slate-800">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-bold text-slate-900">财报 / 业绩预告日历</h2>
        <p class="text-[11px] text-slate-500">
          仅监控股 · 前瞻 {{ calendar.lookahead_days }} 天
          <span v-if="calendar.monitored_count"> · 监控 {{ calendar.monitored_count }} 只</span>
        </p>
      </div>
      <button
        @click="load"
        :disabled="loading"
        class="rounded bg-cyan-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-cyan-500 disabled:bg-slate-400"
      >
        {{ loading ? '加载中…' : '↻ 刷新' }}
      </button>
    </div>

    <div v-if="error" class="rounded-lg bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
      {{ error }}
    </div>

    <div v-if="!loading && !error && !grouped.length" class="rounded-lg bg-slate-50 px-3 py-6 text-center text-[12px] text-slate-400">
      未来 {{ calendar.lookahead_days }} 天内没有监控股的财报 / 业绩预告披露。
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="group in grouped"
        :key="group.date"
        class="rounded-lg border border-slate-200 bg-white"
      >
        <div class="flex items-center justify-between border-b border-slate-100 px-3 py-1.5">
          <span class="text-[12px] font-bold text-slate-800">{{ group.date }}</span>
          <span class="text-[10px] text-slate-400">{{ group.items.length }} 条</span>
        </div>
        <div class="divide-y divide-slate-50">
          <div
            v-for="(ev, i) in group.items"
            :key="i"
            class="flex items-center gap-2 px-3 py-1.5"
          >
            <span
              class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold"
              :class="ev.type === '财报' ? 'bg-cyan-100 text-cyan-700' : 'bg-amber-100 text-amber-700'"
            >
              {{ ev.type }}
            </span>
            <router-link
              :to="`/stock/${ev.symbol}`"
              class="shrink-0 font-mono text-[11px] font-bold text-slate-700 hover:text-cyan-700"
            >
              {{ ev.symbol }}
            </router-link>
            <span class="shrink-0 truncate text-[11px] text-slate-600">{{ ev.name }}</span>
            <span class="flex-1 truncate text-right text-[11px] text-slate-500">{{ ev.summary }}</span>
          </div>
        </div>
      </div>
    </div>

    <p v-if="calendar.generated_at" class="text-[10px] text-slate-400">
      数据生成于 {{ calendar.generated_at }} · 来源 东方财富
      <span v-if="calendar.periods_checked?.length"> · 报告期 {{ calendar.periods_checked.join(', ') }}</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { stockApi } from '@/api'

const calendar = ref<any>({ lookahead_days: 120, monitored_count: 0, events: [] })
const loading = ref(false)
const error = ref('')

const grouped = computed(() => {
  const events: any[] = calendar.value.events || []
  const map = new Map<string, any[]>()
  for (const ev of events) {
    if (!map.has(ev.disclosure_date)) map.set(ev.disclosure_date, [])
    map.get(ev.disclosure_date)!.push(ev)
  }
  return Array.from(map.entries()).map(([date, items]) => ({ date, items }))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await stockApi.getEarningsCalendar()
    if (data) calendar.value = data
  } catch (e: any) {
    error.value = '加载财报日历失败：' + (e?.message || e)
    console.error('earnings calendar load failed', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

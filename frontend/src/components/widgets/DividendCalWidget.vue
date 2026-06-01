<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <div class="text-xs font-bold text-slate-200">{{ currentYear }} 分红日历</div>
      <div class="flex gap-1">
        <button class="rounded px-2 py-0.5 text-[10px] text-slate-400 hover:bg-white/5" @click="currentYear--">◀</button>
        <span class="text-[10px] font-mono text-slate-300">{{ currentYear }}</span>
        <button class="rounded px-2 py-0.5 text-[10px] text-slate-400 hover:bg-white/5" @click="currentYear++">▶</button>
      </div>
    </div>

    <!-- 12-month grid -->
    <div class="grid grid-cols-3 gap-1.5">
      <div
        v-for="m in 12"
        :key="m"
        class="rounded-lg border p-2 transition-colors"
        :class="monthBorderClass(m)"
      >
        <div class="mb-1 flex items-center justify-between">
          <span class="text-[10px] font-bold" :class="m === nowMonth && currentYear === nowYear ? 'text-cyan-400' : 'text-slate-400'">
            {{ m }}月
          </span>
          <span v-if="monthDividends(m).length > 0" class="text-[9px] font-mono text-emerald-400">
            {{ monthTotal(m).toFixed(0) }}
          </span>
        </div>
        <div class="space-y-0.5">
          <div
            v-for="d in monthDividends(m)"
            :key="d.symbol"
            class="flex items-center justify-between rounded px-1 py-0.5 text-[9px] bg-slate-800/40"
          >
            <span class="truncate text-slate-300">{{ d.name }}</span>
            <span class="font-mono text-emerald-400">{{ d.days_left ?? '--' }}天</span>
          </div>
          <div v-if="monthDividends(m).length === 0" class="text-[9px] text-slate-600">—</div>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="flex items-center gap-3 text-[9px] text-slate-500">
      <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded bg-emerald-500/30 border border-emerald-500/50"></span>有分红</span>
      <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded bg-cyan-500/30 border border-cyan-500/50"></span>当月</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

const store = useSentimentStore()

const now = new Date()
const nowMonth = now.getMonth() + 1
const nowYear = now.getFullYear()
const currentYear = ref(nowYear)

interface DividendEntry {
  symbol: string
  name: string
  date: string | null
  days_left: number | null
  month: number
}

const allDividends = computed<DividendEntry[]>(() => {
  const cal = store.dividendCalendar || []
  return cal
    .filter((d: any) => d.date)
    .map((d: any) => {
      const dt = new Date(d.date)
      return {
        symbol: d.symbol,
        name: d.name,
        date: d.date,
        days_left: d.days_left,
        month: dt.getMonth() + 1,
      }
    })
    .filter((d: DividendEntry) => {
      const dt = new Date(d.date!)
      return dt.getFullYear() === currentYear.value
    })
})

function monthDividends(m: number): DividendEntry[] {
  return allDividends.value.filter((d) => d.month === m)
}

function monthTotal(m: number): number {
  // estimate: sum of (stock price * dividend_yield / 100) for each stock with dividend in this month
  const divs = monthDividends(m)
  let total = 0
  for (const d of divs) {
    const price = store.realtimePrices?.[d.symbol]?.price ?? 0
    const dy = store.realtimePrices?.[d.symbol]?.dividend_yield ?? 0
    total += price * dy / 100
  }
  return total
}

function monthBorderClass(m: number) {
  const divs = monthDividends(m)
  if (m === nowMonth && currentYear.value === nowYear) return 'border-cyan-500/40 bg-cyan-500/5'
  if (divs.length > 0) return 'border-emerald-500/30 bg-emerald-500/5'
  return 'border-slate-700/30 bg-transparent'
}
</script>

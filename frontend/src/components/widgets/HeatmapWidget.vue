<template>
  <div class="space-y-3">
    <div class="text-[10px] text-slate-500">
      Treemap 展示监控股票的市值分布，颜色按行业区分。
    </div>
    <div ref="chartRef" class="w-full" style="height: 280px;"></div>
    <div v-if="hhi > 0" class="rounded-lg border border-slate-200 bg-slate-50/80 p-2 text-[10px]">
      <span class="text-slate-500">HHI 指数:</span>
      <span class="ml-1 font-mono font-bold" :class="hhiClass">{{ hhi.toFixed(0) }}</span>
      <span class="ml-2 text-slate-500">({{ hhiLabel }})</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import { echarts, type ECharts } from '@/lib/echarts'

const store = useSentimentStore()
const chartRef = ref<HTMLDivElement>()
let chart: ECharts | null = null

const COLORS = [
  '#22d3ee', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
  '#fb923c', '#38bdf8', '#4ade80', '#e879f9', '#facc15',
]

const industryMap = computed(() => {
  const map: Record<string, string> = {}
  for (const s of store.stocks) {
    map[s.symbol] = s.industry || '未分类'
  }
  return map
})

const industries = computed(() => {
  const set = new Set(Object.values(industryMap.value))
  return [...set]
})

const chartData = computed(() => {
  const grouped: Record<string, any[]> = {}
  for (const s of store.dashboardStocks) {
    const ind = industryMap.value[s.stock_symbol] || '未分类'
    if (!grouped[ind]) grouped[ind] = []
    const price = store.realtimePrices?.[s.stock_symbol]
    grouped[ind].push({
      name: s.stock_name,
      value: price?.market_cap ?? 1,
    })
  }
  return Object.entries(grouped).map(([name, children], i) => ({
    name,
    itemStyle: { color: COLORS[i % COLORS.length] },
    children,
  }))
})

const hhi = computed(() => {
  const total = chartData.value.reduce((sum, ind) => sum + ind.children.reduce((s: number, c: any) => s + c.value, 0), 0)
  if (total <= 0) return 0
  let hhiVal = 0
  for (const ind of chartData.value) {
    for (const c of ind.children) {
      const pct = (c.value / total) * 100
      hhiVal += pct * pct
    }
  }
  return hhiVal
})

const hhiClass = computed(() => {
  if (hhi.value < 1500) return 'text-emerald-400'
  if (hhi.value < 2500) return 'text-amber-400'
  return 'text-rose-400'
})

const hhiLabel = computed(() => {
  if (hhi.value < 1500) return '分散'
  if (hhi.value < 2500) return '适中'
  return '集中'
})

function updateChart() {
  if (!chart) return
  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(100, 116, 139, 0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: (p: any) => {
        if (p.data.children) return `<b>${p.name}</b>`
        const v = p.value
        const label = v >= 1e12 ? (v / 1e12).toFixed(1) + '万亿' : v >= 1e8 ? (v / 1e8).toFixed(0) + '亿' : v
        return `<b>${p.name}</b><br/>市值: ${label}`
      },
    },
    series: [{
      type: 'treemap',
      data: chartData.value,
      width: '100%',
      height: '100%',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        fontSize: 10,
        color: '#fff',
        formatter: (p: any) => p.data.children ? p.name : p.name,
      },
      itemStyle: {
        borderColor: '#0f172a',
        borderWidth: 2,
        gapWidth: 2,
      },
      levels: [
        { itemStyle: { borderColor: '#1e293b', borderWidth: 3 } },
        { label: { fontSize: 10 }, itemStyle: { borderColor: '#334155', borderWidth: 1 } },
      ],
    }],
  })
}

onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})

watch(chartData, updateChart, { deep: true })
</script>

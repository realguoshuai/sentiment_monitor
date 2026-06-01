<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between">
      <div class="text-[10px] text-slate-500">
        按行业分组，面积 = 市值。无市值数据时按等权显示。
      </div>
      <span v-if="!hasMarketCap" class="text-[9px] text-amber-500 font-bold">等权模式</span>
    </div>
    <div ref="chartRef" class="w-full" style="height: 260px;"></div>
    <div v-if="hhi > 0" class="rounded-lg border border-slate-200 bg-slate-50 p-2 text-[10px]">
      <span class="text-slate-500">HHI 指数:</span>
      <span class="ml-1 font-mono font-bold" :class="hhiClass">{{ hhi.toFixed(0) }}</span>
      <span class="ml-2 text-slate-500">({{ hhiLabel }})</span>
    </div>
    <!-- Legend: industry colors -->
    <div class="flex flex-wrap gap-2">
      <span
        v-for="(color, ind) in industryColors"
        :key="ind"
        class="flex items-center gap-1 text-[9px] text-slate-500"
      >
        <span class="inline-block h-2 w-2 rounded" :style="{ backgroundColor: color }"></span>
        {{ ind }}
      </span>
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
  '#6ee7b7', '#93c5fd', '#fcd34d', '#fca5a5', '#c4b5fd',
]

// Get industry for a stock from store.stocks (has industry field)
function getIndustry(symbol: string): string {
  const stock = store.stocks.find((s: any) => s.symbol === symbol)
  return (stock?.industry || '').trim() || '未分类'
}

function getMarketCap(symbol: string): number {
  return store.realtimePrices?.[symbol]?.market_cap ?? 0
}

const hasMarketCap = computed(() =>
  store.dashboardStocks.some((s) => getMarketCap(s.stock_symbol) > 0)
)

// Build industry -> color mapping
const industryColors = computed(() => {
  const map: Record<string, string> = {}
  const industries = new Set(store.dashboardStocks.map((s) => getIndustry(s.stock_symbol)))
  let i = 0
  for (const ind of industries) {
    map[ind] = COLORS[i % COLORS.length]
    i++
  }
  return map
})

const chartData = computed(() => {
  const grouped: Record<string, { name: string; value: number }[]> = {}

  for (const s of store.dashboardStocks) {
    const ind = getIndustry(s.stock_symbol)
    const cap = getMarketCap(s.stock_symbol)
    const value = cap > 0 ? cap : 1 // fallback to equal weight

    if (!grouped[ind]) grouped[ind] = []
    grouped[ind].push({ name: s.stock_name || s.stock_symbol, value })
  }

  return Object.entries(grouped).map(([name, children]) => ({
    name,
    itemStyle: { color: industryColors.value[name] || COLORS[0] },
    children,
  }))
})

const hhi = computed(() => {
  const total = chartData.value.reduce(
    (sum, ind) => sum + ind.children.reduce((s, c) => s + c.value, 0), 0
  )
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
  if (hhi.value < 1500) return 'text-emerald-600'
  if (hhi.value < 2500) return 'text-amber-600'
  return 'text-rose-500'
})

const hhiLabel = computed(() => {
  if (hhi.value < 1500) return '分散'
  if (hhi.value < 2500) return '适中'
  return '集中'
})

function updateChart() {
  if (!chart) return
  const data = chartData.value
  if (!data.length || data.every((d) => !d.children.length)) return

  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(100, 116, 139, 0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
      formatter: (p: any) => {
        if (p.data.children) return `<b>${p.name}</b> (${p.data.children.length}只)`
        const v = p.value
        const label = v >= 1e12 ? (v / 1e12).toFixed(1) + '万亿'
          : v >= 1e8 ? (v / 1e8).toFixed(0) + '亿'
          : v > 1 ? v.toFixed(0) : '等权'
        return `<b>${p.name}</b><br/>市值: ${label}`
      },
    },
    series: [{
      type: 'treemap',
      data,
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
        borderColor: '#fff',
        borderWidth: 2,
        gapWidth: 2,
      },
      levels: [
        { itemStyle: { borderColor: '#e2e8f0', borderWidth: 3 } },
        { label: { fontSize: 10 }, itemStyle: { borderColor: '#f1f5f9', borderWidth: 1 } },
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

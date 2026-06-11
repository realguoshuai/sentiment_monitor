<template>
  <div ref="chartRef" class="w-full h-full min-h-[150px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { echarts, type ECharts, type EChartsOption } from '@/lib/echarts'
import type { SentimentData } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'

const props = withDefaults(defineProps<{
  data: SentimentData[]
  height?: number
}>(), {
  height: 320
})

const chartRef = ref<HTMLDivElement>()
let chart: ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
  window.addEventListener('resize', handleResize)
}

const updateChart = () => {
  if (!chart) return

  const store = useSentimentStore()

  // Sort by total ROI descending
  const sortedData = [...props.data].sort((a, b) => {
    const pA = store.realtimePrices[a.stock_symbol]
    const pB = store.realtimePrices[b.stock_symbol]
    const roiA = pA ? store.calculateROI(a.stock_symbol, pA.pe, pA.pb, pA.dividend_yield) : 0
    const roiB = pB ? store.calculateROI(b.stock_symbol, pB.pe, pB.pb, pB.dividend_yield) : 0
    return roiB - roiA
  })

  const stockNames = sortedData.map(d => d.stock_name)

  // Split ROI into two components
  const capitalReturns = sortedData.map(d => {
    const p = store.realtimePrices[d.stock_symbol]
    if (!p || p.pe <= 0 || p.pb <= 0) return 0
    return parseFloat((100 / p.pe).toFixed(2))
  })

  const dividendReturns = sortedData.map(d => {
    const p = store.realtimePrices[d.stock_symbol]
    return p ? parseFloat((p.dividend_yield || 0).toFixed(2)) : 0
  })

  // Reverse for bottom-up rendering (ECharts category axis renders bottom to top)
  const names = [...stockNames].reverse()
  const capital = [...capitalReturns].reverse()
  const dividend = [...dividendReturns].reverse()

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#334155',
      borderWidth: 1,
      textStyle: { color: '#fff', fontSize: 11 },
      formatter: (params: any) => {
        const name = params[0]?.name
        if (!name) return ''
        const item = sortedData.find(d => d.stock_name === name)
        if (!item) return name

        const rt = store.realtimePrices[item.stock_symbol]
        const capVal = params.find((p: any) => p.seriesName === '资本回报')?.value ?? 0
        const divVal = params.find((p: any) => p.seriesName === '分红回报')?.value ?? 0
        const total = capVal + divVal

        if (!rt) return `${name}: ${total.toFixed(2)}%`

        return `
          <div style="font-weight:bold;margin-bottom:4px;">${name}</div>
          <div style="display:flex;justify-content:space-between;gap:16px;">
            <span style="color:#94a3b8;">资本回报</span>
            <span style="font-family:monospace;color:#06b6d4;">${capVal.toFixed(2)}%</span>
          </div>
          <div style="display:flex;justify-content:space-between;gap:16px;">
            <span style="color:#94a3b8;">分红回报</span>
            <span style="font-family:monospace;color:#ec4899;">${divVal.toFixed(2)}%</span>
          </div>
          <div style="border-top:1px solid #334155;margin-top:4px;padding-top:4px;display:flex;justify-content:space-between;gap:16px;">
            <span style="color:#94a3b8;">合计 ROI</span>
            <span style="font-family:monospace;font-weight:bold;color:#f1f5f9;">${total.toFixed(2)}%</span>
          </div>
        `
      },
    },
    legend: {
      show: true,
      top: 0,
      right: 0,
      textStyle: { color: '#94a3b8', fontSize: 10 },
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: {
      left: 4,
      right: 50,
      top: 24,
      bottom: 0,
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#64748b', fontSize: 9, formatter: (v: number) => v + '%' },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#cbd5e1', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: '资本回报',
        type: 'bar',
        stack: 'roi',
        barWidth: 14,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#0e7490' },
            { offset: 1, color: '#22d3ee' },
          ]),
          borderRadius: [0, 0, 0, 0],
        },
        emphasis: { itemStyle: { color: '#67e8f9' } },
        data: capital,
      },
      {
        name: '分红回报',
        type: 'bar',
        stack: 'roi',
        barWidth: 14,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#9d174d' },
            { offset: 1, color: '#f472b6' },
          ]),
          borderRadius: [0, 3, 3, 0],
        },
        emphasis: { itemStyle: { color: '#f9a8d4' } },
        data: dividend,
        label: {
          show: true,
          position: 'right',
          color: '#e2e8f0',
          fontSize: 10,
          fontWeight: 'bold',
          fontFamily: 'monospace',
          formatter: (p: any) => {
            const total = (capital[p.dataIndex] || 0) + (p.value || 0)
            return total.toFixed(1) + '%'
          },
        },
      },
    ],
  }

  chart.setOption(option, true)
}

const handleResize = () => chart?.resize()

onMounted(() => {
  initChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

watch(() => props.data, updateChart, { deep: true })
</script>

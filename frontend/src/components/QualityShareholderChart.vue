<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { echarts, type ECharts } from '@/lib/echarts'

const props = defineProps<{
  shareholderHistory: any[]
  stockName: string
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: ECharts | null = null

const formatPrice = (v?: number | null) => {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

const formatCount = (v?: number | null) => {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const formatCompactNumber = (v?: number | null) => {
  if (v === undefined || v === null || Number.isNaN(Number(v))) return '--'
  const numeric = Number(v)
  const absValue = Math.abs(numeric)
  if (absValue >= 1e8) return `${(numeric / 1e8).toFixed(1)}亿`
  if (absValue >= 1e4) return `${(numeric / 1e4).toFixed(0)}万`
  if (absValue >= 1e3) return `${(numeric / 1e3).toFixed(0)}k`
  return `${Math.round(numeric)}`
}

const toFiniteOrNull = (value: unknown) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const initChart = () => {
  if (!chartRef.value || !props.shareholderHistory.length) return
  chart?.dispose()

  const dates = props.shareholderHistory.map((item: any) => item.date)
  const priceSeries = props.shareholderHistory.map((item: any) => toFiniteOrNull(item.price))
  const holderSeries = props.shareholderHistory.map((item: any) => toFiniteOrNull(item.holder_count))

  const tooltipFormatter = (params: any[]) => {
    const dataIndex = params?.[0]?.dataIndex ?? 0
    const point = props.shareholderHistory[dataIndex] || {}
    const lines = [
      `<div style="font-weight:800;margin-bottom:8px;">${point.date || '--'}</div>`,
      `<div style="color:#94a3b8;margin-bottom:8px;">股东统计日 ${point.date || '--'}</div>`,
    ]
    if (point.notice_date) {
      lines.push(`<div style="color:#94a3b8;margin-bottom:8px;">公告日 ${point.notice_date}</div>`)
    } else {
      lines.push('<div style="margin-bottom:8px;"></div>')
    }

    params.forEach((item: any) => {
      const value = item.value
      let formatted = '--'
      if (item.seriesName === '股价') formatted = formatPrice(value)
      if (item.seriesName === '股东户数') formatted = formatCount(value)
      lines.push(
        `<div style="display:flex;justify-content:space-between;gap:20px;margin:4px 0;">
          <span>${item.marker}${item.seriesName}</span>
          <strong>${formatted}</strong>
        </div>`
      )
    })

    return `<div style="min-width:220px;">${lines.join('')}</div>`
  }

  chart = echarts.init(chartRef.value)
  chart.setOption({
    backgroundColor: 'transparent',
    title: {
      text: `${props.stockName} 筹码结构对齐`,
      left: 'center',
      top: 0,
      textStyle: { color: '#1e293b', fontSize: 16, fontWeight: 800 },
    },
    tooltip: { trigger: 'axis', formatter: tooltipFormatter },
    legend: { bottom: 0, textStyle: { color: '#64748b' } },
    grid: { top: 60, left: 50, right: 60, bottom: 60 },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#94a3b8' } },
    yAxis: [
      { type: 'value', name: '股价', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      { type: 'value', name: '股东户数', axisLabel: { color: '#94a3b8', formatter: (v: number) => formatCompactNumber(v) }, splitLine: { show: false } },
    ],
    series: [
      { name: '股价', type: 'line', smooth: true, data: priceSeries, lineStyle: { width: 3 }, color: '#2563eb' },
      { name: '股东户数', type: 'line', yAxisIndex: 1, smooth: true, data: holderSeries, lineStyle: { width: 3 }, color: '#f59e0b' },
    ],
  })
}

const handleResize = () => chart?.resize()

watch(() => props.shareholderHistory, () => initChart(), { deep: true })

onMounted(() => { initChart(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); chart?.dispose() })
</script>

<style scoped>
.chart-container { height: 500px; }
</style>

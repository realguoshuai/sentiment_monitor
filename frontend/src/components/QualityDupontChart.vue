<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { echarts, type ECharts } from '@/lib/echarts'

const props = defineProps<{ data: any[] }>()

const chartRef = ref<HTMLElement | null>(null)
let chart: ECharts | null = null

const years = computed(() => props.data.map((item: any) => item.year))

const initChart = () => {
  if (!chartRef.value || !years.value.length) return
  chart?.dispose()
  chart = echarts.init(chartRef.value)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => Number(v).toFixed(2) },
    legend: { bottom: 0, textStyle: { color: '#64748b' } },
    grid: { top: 40, left: 50, right: 30, bottom: 60 },
    xAxis: { type: 'category', data: years.value, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
    series: [
      { name: 'Net Margin', type: 'line', stack: 'Total', areaStyle: { opacity: 0.3 }, emphasis: { focus: 'series' }, data: props.data.map((d: any) => d.net_margin), color: '#3b82f6' },
      { name: 'Asset Turnover x10', type: 'line', stack: 'Total', areaStyle: { opacity: 0.3 }, emphasis: { focus: 'series' }, data: props.data.map((d: any) => d.asset_turnover * 10), color: '#10b981' },
      { name: 'Equity Multiplier', type: 'line', stack: 'Total', areaStyle: { opacity: 0.3 }, emphasis: { focus: 'series' }, data: props.data.map((d: any) => d.equity_multiplier), color: '#f59e0b' },
      { name: 'ROE', type: 'line', data: props.data.map((d: any) => d.roe), lineStyle: { width: 4, type: 'dotted' }, color: '#ef4444' },
    ],
  })
}

const handleResize = () => chart?.resize()

watch(() => props.data, () => initChart(), { deep: true })

onMounted(() => { initChart(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); chart?.dispose() })
</script>

<style scoped>
.chart-container { height: 400px; }
</style>

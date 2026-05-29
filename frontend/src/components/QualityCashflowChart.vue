<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { echarts, type ECharts } from '@/lib/echarts'
import { safeNum } from '@/lib/chart'

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
    grid: { top: 40, left: 50, right: 50, bottom: 60 },
    xAxis: { type: 'category', data: years.value, axisLabel: { color: '#94a3b8' } },
    yAxis: [
      { type: 'value', name: 'Amount', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      { type: 'value', name: 'Ratio (%)', axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series: [
      { name: 'CFO', type: 'bar', data: props.data.map((d: any) => safeNum(d.cfo)), color: '#0f766e' },
      { name: 'FCF', type: 'bar', data: props.data.map((d: any) => safeNum(d.fcf)), color: '#2563eb' },
      { name: 'CFO / Profit', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.cfo_to_profit_pct)), lineStyle: { width: 3 }, color: '#f59e0b' },
      { name: 'FCF / Profit', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.fcf_to_profit_pct)), lineStyle: { width: 3 }, color: '#ef4444' },
      { name: 'Capex Intensity', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.capex_intensity_pct)), lineStyle: { width: 2, type: 'dashed' }, color: '#8b5cf6' },
    ],
  })
}

const handleResize = () => chart?.resize()

watch(() => props.data, () => initChart(), { deep: true })

onMounted(() => { initChart(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); chart?.dispose() })
</script>

<style scoped>
.chart-container { height: 500px; }
</style>

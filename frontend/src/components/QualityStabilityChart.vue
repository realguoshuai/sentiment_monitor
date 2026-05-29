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
      { type: 'value', name: 'Growth (%)', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      { type: 'value', name: 'Return (%)', axisLabel: { color: '#94a3b8' }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Revenue Growth', type: 'bar', data: props.data.map((d: any) => safeNum(d.revenue_growth_pct)), color: '#94a3b8' },
      { name: 'ROE', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.roe)), lineStyle: { width: 3 }, color: '#2563eb' },
      { name: 'ROIC Proxy', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.roic_proxy_pct)), lineStyle: { width: 3 }, color: '#f59e0b' },
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

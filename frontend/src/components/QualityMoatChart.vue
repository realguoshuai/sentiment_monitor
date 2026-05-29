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
    grid: { top: 40, left: 50, right: 30, bottom: 60 },
    xAxis: { type: 'category', data: years.value, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8', formatter: '{value}%' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
    series: [
      { name: '毛利率', type: 'line', smooth: true, data: props.data.map((d: any) => safeNum(d.gross_margin)), lineStyle: { width: 3 }, color: '#6366f1' },
      { name: '净利率', type: 'line', smooth: true, data: props.data.map((d: any) => safeNum(d.net_margin)), lineStyle: { width: 3 }, color: '#10b981' },
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

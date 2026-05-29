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
      { name: 'Cash', type: 'bar', data: props.data.map((d: any) => safeNum(d.cash_balance)), color: '#10b981' },
      { name: 'Interest Debt', type: 'bar', data: props.data.map((d: any) => safeNum(d.interest_bearing_debt)), color: '#ef4444' },
      { name: 'Debt / Equity', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.debt_to_equity_pct)), lineStyle: { width: 3 }, color: '#2563eb' },
      { name: 'Short Debt Coverage', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => d.short_debt > 0 ? safeNum(d.short_debt_coverage_pct) : null), lineStyle: { width: 3 }, color: '#f59e0b' },
      { name: 'Working Asset / Revenue', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.receivable_inventory_prepay_to_revenue_pct)), lineStyle: { width: 2, type: 'dashed' }, color: '#8b5cf6' },
      { name: 'Goodwill / Equity', type: 'line', yAxisIndex: 1, data: props.data.map((d: any) => safeNum(d.goodwill_to_equity_pct)), lineStyle: { width: 2, type: 'dotted' }, color: '#64748b' },
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

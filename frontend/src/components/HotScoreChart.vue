<template>
  <div ref="chartRef" class="w-full h-full min-h-[150px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { SentimentData } from '@/api'

const props = withDefaults(defineProps<{
  data: SentimentData[]
  height?: number
}>(), {
  height: 320
})

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return
  
  chart = echarts.init(chartRef.value)
  updateChart()
  
  window.addEventListener('resize', handleResize)
}

const updateChart = () => {
  if (!chart) return
  
  // Sort by hot_score descending
  const sortedData = [...props.data].sort((a, b) => b.hot_score - a.hot_score)
  const stockNames = sortedData.map(d => d.stock_name)
  const hotScores = sortedData.map(d => d.hot_score)
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(0,0,0,0.8)',
      borderColor: '#374151',
      textStyle: { color: '#fff' },
      formatter: '{b}: {c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: stockNames.reverse(),
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#fff' }
    },
    series: [{
      name: '热度分值',
      type: 'bar',
      data: hotScores.reverse(),
      barWidth: '50%',
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#06b6d4' },
          { offset: 1, color: '#3b82f6' }
        ]),
        borderRadius: [0, 4, 4, 0]
      },
      label: {
        show: true,
        position: 'right',
        formatter: '{c}',
        color: '#fff'
      }
    }]
  }
  
  chart.setOption(option)
}

const handleResize = () => {
  chart?.resize()
}

onMounted(() => {
  initChart()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => props.data, () => {
  updateChart()
}, { deep: true })
</script>

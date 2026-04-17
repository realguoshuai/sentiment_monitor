<template>
  <div ref="chartRef" class="w-full h-full min-h-[150px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { echarts, type ECharts, type EChartsOption } from '@/lib/echarts'
import type { SentimentData } from '@/api'

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
  
  const stockNames = props.data.map(d => d.stock_name)
  const sentimentScores = props.data.map(d => ({
    value: d.sentiment_score,
    itemStyle: {
      color: d.sentiment_score > 0.2 ? '#10b981' : 
             d.sentiment_score < -0.2 ? '#ef4444' : '#f59e0b'
    }
  }))
  
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(0,0,0,0.8)',
      borderColor: '#374151',
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: stockNames,
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', rotate: 30 }
    },
    yAxis: {
      type: 'value',
      name: '情感得分',
      nameTextStyle: { color: '#9ca3af' },
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
    },
    series: [{
      name: '情感得分',
      type: 'bar',
      data: sentimentScores,
      barWidth: '60%',
      label: {
        show: true,
        position: 'top',
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

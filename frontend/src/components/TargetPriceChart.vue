<template>
  <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden">
    <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-slate-800">
      <svg class="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
      </svg>
      机构目标价追踪共识图
    </h3>
    
    <div v-if="chartData.length === 0" class="flex flex-col items-center justify-center h-[300px] text-slate-400">
      <svg class="w-12 h-12 mb-3 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
      </svg>
      <p>近期研报未解析到明确的目标价结构</p>
    </div>
    
    <div v-else class="h-[300px] w-full">
      <v-chart class="chart" :option="chartOption" autoresize />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import '@/lib/echarts'
import VChart from 'vue-echarts'
import type { Report } from '@/api'

const props = defineProps<{
  reports: Report[]
  currentPrice?: number
}>()

const extractTargetPrice = (title: string): number | null => {
  // Try to match common patterns like "目标价30元", "目标价格上调至10.5", "目标价: 11元"
  const match = title.match(/目标价(?:格)?(?:为|至|上调至|下调至|维持在|维持|：|:)?\s*([0-9]+\.[0-9]+|[0-9]+)\s*(?:元|块)/)
  if (match && match[1]) {
    return parseFloat(match[1])
  }
  return null
}

const chartData = computed(() => {
  if (!props.reports) return []
  
  const points = []
  for (const r of props.reports) {
    const price = extractTargetPrice(r.title)
    if (price) {
      points.push({
        name: r.org,
        value: [r.pub_date, price, r.title, r.rating] // x, y, title, rating
      })
    }
  }
  
  // Sort primarily by date
  return points.sort((a, b) => new Date(a.value[0]).getTime() - new Date(b.value[0]).getTime())
})

const avgTargetPrice = computed(() => {
  if (chartData.value.length === 0) return null
  const sum = chartData.value.reduce((acc, pt) => acc + (pt.value[1] as number), 0)
  return sum / chartData.value.length
})

const chartOption = computed(() => {
  if (chartData.value.length === 0) return {}

  const series = [
    {
      name: '机构目标价',
      type: 'scatter',
      symbolSize: 12,
      itemStyle: {
        color: '#8b5cf6', // Violet
        opacity: 0.8,
        borderColor: '#fff',
        borderWidth: 1
      },
      data: chartData.value
    }
  ]

  const markLines = []
  
  if (props.currentPrice && props.currentPrice > 0) {
    markLines.push({
      name: '当前价格',
      yAxis: props.currentPrice,
      label: { formatter: `当前价 {c}`, position: 'end', color: '#f43f5e' },
      lineStyle: { type: 'dashed', color: '#f43f5e', width: 2 }
    })
  }
  
  if (avgTargetPrice.value) {
    markLines.push({
      name: '机构均价',
      yAxis: avgTargetPrice.value,
      label: { formatter: `平均目标价 {c}`, position: 'insideStartTop', color: '#8b5cf6' },
      lineStyle: { type: 'solid', color: '#8b5cf6', width: 2, opacity: 0.5 }
    })
  }

  if (markLines.length > 0) {
    series[0].markLine = {
      symbol: ['none', 'none'],
      data: markLines
    }
  }

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b' },
      padding: 12,
      formatter: function (params: any) {
        const pt = params.data.value
        return `
          <div class="font-bold text-sm mb-1">${params.data.name}</div>
          <div class="text-xs text-slate-500 mb-2">${pt[0]}</div>
          <div class="flex justify-between items-center mb-1">
            <span class="text-slate-500 mr-4">目标价:</span>
            <span class="font-bold text-violet-600 font-mono text-lg">${pt[1]} 元</span>
          </div>
          <div class="flex justify-between items-center mb-2">
            <span class="text-slate-500 mr-4">评级:</span>
            <span class="font-bold text-amber-500">${pt[3] || '无'}</span>
          </div>
          <div class="text-[10px] text-slate-400 mt-2 border-t pt-2 w-48 whitespace-normal leading-relaxed">
            "${pt[2]}"
          </div>
        `
      }
    },
    grid: {
      left: 10,
      right: 60,
      top: 20,
      bottom: 10,
      containLabel: true
    },
    xAxis: {
      type: 'time',
      splitLine: { show: false },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#64748b', fontSize: 10, formatter: '{MM}-{dd}' }
    },
    yAxis: {
      type: 'value',
      scale: true, // Don't start from 0
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#64748b', fontSize: 10, margin: 12 }
    },
    series: series
  }
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>

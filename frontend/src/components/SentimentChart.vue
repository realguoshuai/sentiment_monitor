<template>
  <div ref="chartRef" class="w-full h-full min-h-[150px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { echarts, type ECharts, type EChartsOption } from '@/lib/echarts'
import type { SentimentData } from '@/api'

const props = withDefaults(defineProps<{
  data: any
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
  if (!chart || !props.data?.dates) return
  
  const { dates, avg_line, stock_data, top_items } = props.data
  const displayDates = dates.map((d: string) => d.slice(5)) // MM-DD
  
  // 颜色面板
  const colors = ['#38bdf8', '#fbbf24', '#f472b6', '#34d399', '#a78bfa', '#fb7185', '#2dd4bf']
  
  const series: any[] = []
  
  // 1. 添加全场均值线 (粗虚线)
  series.push({
    name: '全场均值',
    type: 'line',
    data: avg_line,
    smooth: true,
    lineStyle: { width: 4, type: 'dashed', color: 'rgba(255, 255, 255, 0.4)' },
    itemStyle: { color: 'rgba(255, 255, 255, 0.6)' },
    connectNulls: true, // 连接全场均值的断点
    z: 10
  })
  
  // 2. 添加各股票趋势线
  Object.entries(stock_data).forEach(([name, values], idx) => {
    series.push({
      name,
      type: 'line',
      data: values,
      smooth: true,
      symbolSize: 6,
      lineStyle: { width: 2 },
      itemStyle: { color: colors[idx % colors.length] },
      connectNulls: true, // 连接断点
    })
  })
  
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      triggerOn: 'mousemove|click', // 悬浮和点击都能触发
      enterable: true, // 允许鼠标进入 tooltip，方便点链接
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#334155',
      borderWidth: 1,
      padding: 0, // 内部 padding 由 html 控制
      textStyle: { color: '#f8fafc', fontSize: 11 },
      confine: true,
      formatter: (params: any) => {
        const dateStr = dates[params[0].dataIndex]
        const dayNews = top_items[dateStr] || []
        
        let html = `<div class="p-1 max-w-[240px]">
          <div class="font-bold mb-2 text-slate-400 border-b border-slate-700 pb-1">${dateStr}</div>`
        
        // 遍历所有股票分值
        params.forEach((p: any) => {
          if (p.value === null || p.value === undefined) return
          const colorClass = p.value >= 0 ? 'text-emerald-400' : 'text-rose-400'
          html += `<div class="flex justify-between items-center gap-4 mb-1">
            <span class="text-slate-300 text-[10px]">${p.seriesName}:</span>
            <span class="font-mono font-bold ${colorClass} text-[10px]">${p.value > 0 ? '+' : ''}${p.value}</span>
          </div>`
        })
        
        if (dayNews.length) {
          html += `<div class="border-t border-slate-700 pt-2 mt-2">
            <div class="text-[9px] text-slate-500 uppercase tracking-wider mb-1">今日爆点新闻</div>`
          dayNews.forEach((news: any) => {
            const dotColor = news.score >= 0 ? '#10b981' : '#ef4444'
            const newsLink = news.url ? `<a href="${news.url}" target="_blank" class="hover:text-indigo-400 underline decoration-slate-600 underline-offset-2">` : '<span>'
            const newsLinkEnd = news.url ? '</a>' : '</span>'
            html += `<div class="flex items-start gap-1.5 mb-1.5 last:mb-0 group/news">
              <span class="mt-1.5 w-1 h-1 shrink-0 rounded-full" style="background:${dotColor}"></span>
              <div class="text-[10px] text-slate-300 leading-snug line-clamp-2">
                ${newsLink}${news.title}${newsLinkEnd}
              </div>
            </div>`
          })
          html += `</div>`
        }
        html += `</div>`
        return html
      }
    },
    legend: {
      type: 'scroll',
      top: 0,
      textStyle: { color: '#94a3b8', fontSize: 10 },
      icon: 'circle',
      pageTextStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '5%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: displayDates,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      min: -1,
      max: 1,
      splitNumber: 4,
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } }
    },
    series
  }
  
  chart.setOption(option, true) // true 表示不合并，完全重绘
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

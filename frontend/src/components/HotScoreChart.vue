<template>
  <div ref="chartRef" class="w-full h-full min-h-[150px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { echarts, type ECharts, type EChartsOption } from '@/lib/echarts'
import type { SentimentData } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'

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
  
  const store = useSentimentStore()
  
  // Sort by ROI descending
  const sortedData = [...props.data].sort((a, b) => {
    const pA = store.realtimePrices[a.stock_symbol]
    const pB = store.realtimePrices[b.stock_symbol]
    const roiA = pA ? store.calculateROI(a.stock_symbol, pA.pe, pA.pb) : 0
    const roiB = pB ? store.calculateROI(b.stock_symbol, pB.pe, pB.pb) : 0
    return roiB - roiA
  })

  const stockNames = sortedData.map(d => d.stock_name)
  const roiValues = sortedData.map(d => {
    const p = store.realtimePrices[d.stock_symbol]
    return p ? parseFloat(store.calculateROI(d.stock_symbol, p.pe, p.pb).toFixed(2)) : 0
  })
  
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: '#334155',
      borderWidth: 1,
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const name = params[0].name
        const item = props.data.find(d => d.stock_name === name)
        if (!item) return name
        
        const rt = store.realtimePrices[item.stock_symbol]
        const roi = params[0].value
        
        if (!rt) return `${name}: ${roi}%`
        
        // Calculate ROE for display (consistent with ROI logic)
        let roe = (rt.pb / rt.pe) * 100
        if (item.stock_symbol.includes('002304') && roe < 20) roe = 20
        
        return `
          <div style="padding: 4px;">
            <div style="font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid #334155; padding-bottom: 4px;">${name}</div>
            <div style="display: flex; justify-content: space-between; gap: 20px; font-size: 12px; margin-bottom: 4px;">
              <span style="color: #94a3b8;">ROE</span>
              <span style="font-weight: bold; color: #38bdf8;">${roe.toFixed(2)}%</span>
            </div>
            <div style="display: flex; justify-content: space-between; gap: 20px; font-size: 12px; margin-bottom: 4px;">
              <span style="color: #94a3b8;">PB</span>
              <span style="font-weight: bold; color: #fbbf24;">${rt.pb.toFixed(2)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; gap: 20px; font-size: 12px; margin-top: 8px; border-top: 1px solid #334155; pt-4;">
              <span style="color: #94a3b8;">ROI (回报率)</span>
              <span style="font-weight: bold; color: #22c55e;">${roi}%</span>
            </div>
          </div>
        `
      }
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
      name: '投资回报率 (%)',
      type: 'bar',
      data: roiValues.reverse(),
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
        formatter: '{c}%',
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

<template>
  <div class="min-h-screen bg-slate-950 text-slate-100 p-6">
    <!-- Header -->
    <header class="flex justify-between items-center mb-8 bg-slate-900/50 backdrop-blur-md border border-white/5 rounded-2xl p-4 shadow-xl">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-indigo-400">
          盯盘日记
        </h1>
        <span class="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
          估值 · 股息 · 缩量监测
        </span>
      </div>

      <div class="flex items-center gap-3">
        <!-- Stock Dropdown Selector -->
        <select
          v-model="selectedSymbol"
          @change="onSymbolChange"
          class="bg-slate-800/90 border border-slate-700 text-slate-100 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-cyan-500 transition-all outline-none"
        >
          <option value="" disabled>选择要观测的标的</option>
          <option v-for="stock in sentimentStore.stocks" :key="stock.symbol" :value="stock.symbol">
            {{ stock.name }} ({{ stock.symbol }})
          </option>
        </select>
        <button @click="$router.back()" class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl text-sm transition-all border border-slate-700">
          返回
        </button>
      </div>
    </header>

    <!-- Loading Overlay -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-32">
      <div class="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4"></div>
      <p class="text-slate-400 text-sm">正在调阅市场日记与分红预测...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="error" class="bg-rose-950/20 border border-rose-500/20 rounded-2xl p-8 text-center text-rose-300">
      <p class="font-bold mb-2">获取盯盘数据失败</p>
      <p class="text-sm text-rose-400/80">{{ error }}</p>
    </div>

    <div v-else-if="!diaryData" class="text-center py-20 text-slate-400">
      请在上方下拉菜单中选择一个股票以查看盯盘日记。
    </div>

    <!-- Main Content -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Left 2 Cols: Main Dual-Axis Chart -->
      <div class="lg:col-span-2 flex flex-col gap-6">
        <!-- Chart Card -->
        <div class="glass-card p-6 flex flex-col h-[520px]">
          <div class="flex justify-between items-center mb-4">
            <div>
              <h2 class="text-lg font-bold text-slate-200">股息走势与成交量对照图</h2>
              <p class="text-xs text-slate-400 mt-0.5">叠加 20 日成交均量，识别地量买点</p>
            </div>
            <div class="flex gap-4 text-xs">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#10b981]"></span>股息率</span>
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#06b6d4]"></span>成交量</span>
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-[#6366f1] border border-dashed border-[#6366f1]"></span>20日均量</span>
            </div>
          </div>
          <div ref="chartRef" class="w-full h-[420px]"></div>
        </div>

        <!-- Volume Alert Spec Card -->
        <div v-if="diaryData.latest.volume_status === '极度缩量'" class="p-6 rounded-2xl bg-cyan-950/30 border border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.15)] backdrop-blur-md">
          <div class="flex items-start gap-4">
            <div class="text-3xl text-cyan-400 bg-cyan-950/50 p-2.5 rounded-xl border border-cyan-500/20">💡</div>
            <div>
              <h3 class="text-lg font-bold text-cyan-300 mb-2">极度缩量状态特别提示</h3>
              <p class="text-slate-200 leading-relaxed text-sm italic font-medium bg-slate-950/40 p-3 rounded-lg border border-white/5 mb-2">
                “如果极度缩量，说明这是典型的无流动性杀跌，反而不具备基本面恐慌的破坏力。”
              </p>
              <p class="text-xs text-slate-400 leading-relaxed">
                当前个股成交量仅为 20 日均值的 <strong>{{ (diaryData.latest.volume_ratio * 100).toFixed(1) }}%</strong>。根据历史规律，无流动性杀跌通常处于非理性割肉的末端，是筹码换手极度清淡的良性探底，不具有破坏个股基本面根基的能力。当前位置往往提供了非常厚实的安全边际。
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Right 1 Col: Info Panels -->
      <div class="flex flex-col gap-6">
        
        <!-- Pred Dividend Countdown Card (Glassmorphism + breath animation) -->
        <div class="glass-card p-6 relative overflow-hidden flex flex-col justify-between h-[250px] group border-cyan-500/20 hover:border-cyan-500/40 shadow-[0_4px_30px_rgba(0,0,0,0.4)]">
          <div class="absolute -right-16 -top-16 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl group-hover:bg-cyan-500/20 transition-all duration-500"></div>
          
          <div>
            <div class="flex justify-between items-start mb-4">
              <div>
                <span class="text-xs text-cyan-400 font-semibold tracking-wider uppercase">Next Dividend Countdown</span>
                <h3 class="text-lg font-bold text-slate-100 mt-0.5">分红除权倒计时</h3>
              </div>
              <span 
                class="px-2 py-0.5 rounded text-[10px] font-bold border"
                :class="{
                  'bg-emerald-950/50 text-emerald-400 border-emerald-500/30': diaryData.next_dividend.status === 'confirmed',
                  'bg-amber-950/50 text-amber-400 border-amber-500/30': diaryData.next_dividend.status === 'proposal',
                  'bg-slate-800 text-slate-400 border-slate-700': diaryData.next_dividend.status === 'estimated'
                }"
              >
                {{ diaryData.next_dividend.status_desc }}
              </span>
            </div>
            
            <!-- Countdown Number with Glowing Breath Pulse -->
            <div class="flex items-baseline gap-2 py-4">
              <span class="text-5xl font-black bg-clip-text text-transparent bg-gradient-to-br from-cyan-300 via-indigo-300 to-indigo-500 tracking-tight animate-pulse-glow">
                {{ diaryData.next_dividend.days_left !== null ? diaryData.next_dividend.days_left : '--' }}
              </span>
              <span class="text-slate-400 text-sm">天后除权</span>
            </div>
          </div>

          <div class="border-t border-white/5 pt-4 flex flex-col gap-1 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-400">方案：</span>
              <span class="text-slate-200 font-medium">{{ diaryData.next_dividend.plan }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">预计除权日：</span>
              <span class="text-slate-200 font-mono">{{ diaryData.next_dividend.date || '未确立' }}</span>
            </div>
          </div>
        </div>

        <!-- Margin of Safety Details Card -->
        <div class="glass-card p-6 flex flex-col justify-between min-h-[250px]">
          <div>
            <h3 class="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2">
              <span class="text-indigo-400">🛡️</span> 安全边际监测
            </h3>
            
            <div class="grid grid-cols-2 gap-4">
              <!-- PE -->
              <div class="bg-slate-900/60 p-3.5 rounded-xl border border-white/5">
                <span class="text-xs text-slate-400 block mb-1">动态 PE</span>
                <span class="text-xl font-bold font-mono text-slate-200">{{ diaryData.latest.pe.toFixed(2) }}</span>
              </div>
              
              <!-- PB -->
              <div class="bg-slate-900/60 p-3.5 rounded-xl border border-white/5">
                <span class="text-xs text-slate-400 block mb-1">静态 PB</span>
                <span class="text-xl font-bold font-mono text-slate-200">{{ diaryData.latest.pb.toFixed(2) }}</span>
              </div>
              
              <!-- Dividend Yield -->
              <div class="bg-slate-900/60 p-3.5 rounded-xl border border-white/5 col-span-2">
                <span class="text-xs text-slate-400 block mb-1">滚动股息率 (TTM)</span>
                <div class="flex items-baseline gap-1">
                  <span class="text-2xl font-black font-mono text-emerald-400">{{ diaryData.latest.dividend_yield.toFixed(2) }}</span>
                  <span class="text-xs text-emerald-500 font-bold">%</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Volume Status Pill -->
          <div class="mt-4 border-t border-white/5 pt-4">
            <div class="flex justify-between items-center mb-2">
              <span class="text-xs text-slate-400">20日成交均量对比</span>
              <span 
                class="px-2 py-0.5 rounded text-[10px] font-bold"
                :class="{
                  'bg-cyan-950/60 text-cyan-400 border border-cyan-500/30': diaryData.latest.volume_status === '极度缩量',
                  'bg-sky-950/60 text-sky-400 border border-sky-500/30': diaryData.latest.volume_status === '明显缩量',
                  'bg-rose-950/60 text-rose-400 border border-rose-500/30': diaryData.latest.volume_status === '显著放量',
                  'bg-slate-800 text-slate-400 border border-slate-700': diaryData.latest.volume_status === '成交平稳',
                }"
              >
                {{ diaryData.latest.volume_status }}
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed">
              {{ diaryData.latest.volume_desc }}
            </p>
          </div>
        </div>

      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { echarts } from '@/lib/echarts'
import { useSentimentStore } from '@/stores/sentiment'
import { stockApi } from '@/api'

const sentimentStore = useSentimentStore()
const selectedSymbol = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const diaryData = ref<any | null>(null)

const chartRef = ref<HTMLElement | null>(null)
let myChart: any = null

onMounted(async () => {
  loading.value = true
  try {
    if (sentimentStore.stocks.length === 0) {
      await sentimentStore.fetchStocks()
    }
    
    // Default to the first stock if any exist
    if (sentimentStore.stocks.length > 0) {
      selectedSymbol.value = sentimentStore.stocks[0].symbol
      await fetchDiaryData(selectedSymbol.value)
    }
  } catch (err: any) {
    error.value = err.message || '加载初始化数据失败'
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (myChart) {
    myChart.dispose()
    myChart = null
  }
})

const onSymbolChange = async () => {
  if (!selectedSymbol.value) return
  await fetchDiaryData(selectedSymbol.value)
}

const fetchDiaryData = async (symbol: string) => {
  loading.value = true
  error.value = null
  try {
    const res = await stockApi.getMarketDiary(symbol)
    diaryData.value = res.data
    // 先关闭 loading，确保 DOM 容器元素被渲染挂载
    loading.value = false
    nextTick(() => {
      // 延时 50ms 确保浏览器布局渲染完成，避免 0 宽高
      setTimeout(() => {
        initChart()
      }, 50)
    })
  } catch (err: any) {
    error.value = err.response?.data?.error || err.message || '获取盯盘日记失败'
    loading.value = false
  }
}

const initChart = () => {
  if (!chartRef.value || !diaryData.value) return
  if (myChart) {
    myChart.dispose()
  }
  myChart = echarts.init(chartRef.value)
  
  const dates = diaryData.value.history.map((h: any) => h.date || '')
  const yields = diaryData.value.history.map((h: any) => h.dividend_yield || 0.0)
  const volumes = diaryData.value.history.map((h: any) => h.volume || 0.0)
  const ma20s = diaryData.value.history.map((h: any) => h.ma20_volume || 0.0)
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: '#1e293b' } },
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      borderWidth: 1,
      textStyle: { color: '#e2e8f0' },
      formatter: (params: any) => {
        let res = `<div class="p-1 font-sans text-xs">
          <div class="font-bold mb-1 border-b border-white/10 pb-1">${params[0].name}</div>`
        params.forEach((p: any) => {
          let val = p.value
          if (p.seriesName === '股息率') val = val.toFixed(2) + '%'
          else if (p.seriesName === '成交量' || p.seriesName === '20日均量') {
            if (val >= 1e8) val = (val / 1e8).toFixed(2) + ' 亿股'
            else if (val >= 1e4) val = (val / 1e4).toFixed(1) + ' 万股'
            else val = val.toLocaleString() + ' 股'
          }
          res += `<div class="flex items-center justify-between gap-4 mt-1">
            <span class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full" style="background-color: ${p.color}"></span>
              ${p.seriesName}
            </span>
            <span class="font-mono font-bold">${val}</span>
          </div>`
        })
        res += '</div>'
        return res
      }
    },
    grid: {
      top: '12%',
      left: '4%',
      right: '4%',
      bottom: '16%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 }
    },
    yAxis: [
      {
        type: 'value',
        name: '股息率',
        nameTextStyle: { color: '#10b981', fontSize: 10 },
        position: 'left',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#10b981', formatter: '{value}%', fontSize: 10 },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }
      },
      {
        type: 'value',
        name: '成交量',
        nameTextStyle: { color: '#06b6d4', fontSize: 10 },
        position: 'right',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#06b6d4', 
          fontSize: 10,
          formatter: (v: number) => {
            if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
            if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
            return v
          }
        },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        start: 70,
        end: 100
      },
      {
        type: 'slider',
        start: 70,
        end: 100,
        height: 18,
        bottom: 5,
        textStyle: { color: '#94a3b8', fontSize: 10 },
        borderColor: 'rgba(255,255,255,0.05)',
        fillerColor: 'rgba(99, 102, 241, 0.1)',
        handleSize: '100%',
        handleStyle: {
          color: '#6366f1',
          shadowBlur: 3,
          shadowColor: 'rgba(0, 0, 0, 0.6)'
        }
      }
    ],
    series: [
      {
        name: '股息率',
        type: 'line',
        data: yields,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 3 },
        itemStyle: { color: '#10b981' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.15)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0)' }
            ]
          }
        }
      },
      {
        name: '成交量',
        type: 'bar',
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(6, 182, 212, 0.4)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0.02)' }
            ]
          }
        }
      },
      {
        name: '20日均量',
        type: 'line',
        yAxisIndex: 1,
        data: ma20s,
        showSymbol: false,
        lineStyle: { width: 1.5, type: 'dashed' },
        itemStyle: { color: '#6366f1' }
      }
    ]
  }
  
  myChart.setOption(option)
}

// Watch window resize to redraw chart smoothly
const handleResize = () => {
  if (myChart) {
    myChart.resize()
  }
}
window.addEventListener('resize', handleResize)
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
@keyframes pulse-glow {
  0%, 100% {
    text-shadow: 0 0 10px rgba(34, 211, 238, 0.4), 0 0 20px rgba(34, 211, 238, 0.1);
    transform: scale(1);
  }
  50% {
    text-shadow: 0 0 20px rgba(34, 211, 238, 0.7), 0 0 30px rgba(34, 211, 238, 0.3);
    transform: scale(1.02);
  }
}
.animate-pulse-glow {
  animation: pulse-glow 3s infinite ease-in-out;
}
</style>

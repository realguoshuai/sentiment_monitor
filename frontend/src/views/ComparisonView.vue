<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <!-- Header -->
    <header class="bg-white/80 backdrop-blur-xl border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <router-link to="/" class="p-2 hover:bg-slate-100 rounded-lg transition group">
            <svg class="w-6 h-6 text-slate-500 group-hover:text-slate-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
          </router-link>
          <div>
            <h1 class="text-xl font-bold text-gradient from-indigo-600 to-cyan-600">价差对冲分析终端</h1>
            <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Expert Hedging Terminal</p>
          </div>
        </div>

        <!-- Mode Switch -->
        <div class="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button 
            @click="timeRange = 'intraday'"
            :class="[
              'px-4 py-1.5 rounded-lg text-xs font-bold transition-all',
              timeRange === 'intraday' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-700'
            ]"
          >
            分时价差
          </button>
          <button 
            @click="timeRange = 'historical'"
            :class="[
              'px-4 py-1.5 rounded-lg text-xs font-bold transition-all',
              timeRange === 'historical' ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-700'
            ]"
          >
            历史价差 (30D)
          </button>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-8">
      <!-- Selection Sector -->
      <div class="bg-white rounded-2xl shadow-sm p-6 mb-8 border border-slate-200">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold flex items-center gap-2 text-slate-800">
            <svg class="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
            </svg>
            对比标的录入 (选择2只)
          </h2>
          <div class="text-[10px] text-indigo-500 font-bold uppercase tracking-tighter">
            Hedge Correlation Mode
          </div>
        </div>
        <div class="flex flex-wrap gap-3">
          <button
            v-for="stock in store.sentimentData"
            :key="stock.stock_symbol"
            @click="toggleStock(stock.stock_symbol)"
            :class="[
              'px-4 py-2 rounded-xl border transition-all flex items-center gap-2 font-bold',
              selectedSymbols.includes(stock.stock_symbol)
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700 shadow-sm'
                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50'
            ]"
          >
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: getStockColor(stock.stock_symbol) }"></span>
            <span>{{ stock.stock_name }}</span>
            <span class="text-[10px] opacity-50 font-mono">{{ stock.stock_symbol }}</span>
          </button>
        </div>
      </div>

      <!-- Spread Analysis Dashboard -->
      <div v-if="selectedSymbols.length === 2" class="space-y-6">
        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <div class="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
                <svg class="w-12 h-12 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
             </div>
             <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">当前对冲价差 (Spread)</h4>
             <div class="flex items-baseline gap-2 relative z-10">
                <span class="text-4xl font-black font-mono tracking-tighter" :class="priceDiffColor">
                  {{ currentDiff > 0 ? '+' : '' }}{{ currentDiff.toFixed(2) }}
                </span>
                <span class="text-xs text-slate-500 font-bold uppercase">CNY</span>
             </div>
          </div>
          <div v-for="sym in selectedSymbols" :key="sym" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
             <div class="flex justify-between items-center mb-3">
                <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{{ getStockName(sym) }}</h4>
                <span class="text-[10px] font-mono text-slate-400">{{ sym }}</span>
             </div>
             <div class="flex items-baseline gap-2">
                <span class="text-3xl font-bold font-mono text-slate-800">{{ rtPrices[sym]?.price.toFixed(2) || '--.--' }}</span>
                <span class="text-xs text-slate-500 font-bold uppercase">CNY</span>
                <span v-if="rtPrices[sym]" :class="rtPrices[sym].change_percent > 0 ? 'text-rose-600' : 'text-emerald-600'" class="text-[10px] font-bold ml-auto bg-slate-50 px-2 py-1 rounded">
                  {{ rtPrices[sym].change_percent > 0 ? '+' : '' }}{{ rtPrices[sym].change_percent.toFixed(2) }}%
                </span>
             </div>
          </div>
        </div>

        <!-- Main Spread Chart -->
        <div class="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm relative min-h-[550px]">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-10">
            <div>
              <h3 class="text-lg font-bold flex items-center gap-3 text-slate-800">
                <div class="w-1.5 h-6 bg-indigo-500 rounded-full"></div>
                {{ timeRange === 'intraday' ? '实时分时对冲走势' : '历史日线收盘价差' }}
              </h3>
              <p class="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">{{ timeRange === 'intraday' ? 'Intraday Hedge Pulse' : 'Historical Data Key-Join Analysis' }}</p>
            </div>
            
            <div class="flex items-center gap-3 bg-slate-50 px-4 py-2 rounded-xl border border-slate-200">
               <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Status:</span>
               <div class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)] animate-pulse"></span>
                  <span class="text-[11px] font-mono font-bold text-emerald-700 uppercase tracking-tighter">Live ISO-GRID</span>
               </div>
            </div>
          </div>

          <div ref="priceSpreadRef" class="w-full h-[450px]"></div>
          
          <div v-if="loadingPrice" class="absolute inset-0 bg-white/70 backdrop-blur-[2px] flex items-center justify-center rounded-2xl z-20">
             <div class="flex flex-col items-center gap-4 bg-white px-8 py-6 rounded-2xl shadow-xl border border-slate-100">
                <div class="w-10 h-10 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin"></div>
                <div class="text-center">
                   <p class="text-sm font-bold text-slate-800 uppercase tracking-widest">Loading Analytics</p>
                   <p class="text-[10px] text-slate-500 mt-1 font-mono uppercase">Synchronizing Time-Series Data...</p>
                </div>
             </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-32 bg-white rounded-[2rem] shadow-sm border border-dashed border-slate-300">
        <div class="w-24 h-24 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-8">
          <svg class="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
          </svg>
        </div>
        <h3 class="text-2xl font-black text-slate-800 uppercase tracking-tight">终端未就绪</h3>
        <p class="text-slate-500 mt-3 max-w-sm mx-auto text-sm leading-relaxed">
          请在上方监控列表中精确选择 <span class="text-indigo-600 font-bold underline underline-offset-4">2 只股票</span> 以启动基准对冲分析。系统将自动对齐时间轴并计算实时溢价。
        </p>
      </div>
    </main>

    <footer class="max-w-7xl mx-auto px-6 py-8 border-t border-slate-200 flex flex-col md:flex-row justify-between items-center gap-4">
       <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">© 2026 Sentiment Monitor Hedging Terminal</div>
       <div class="flex items-center gap-6">
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest hover:text-indigo-500 cursor-help transition-colors">Tencent Finance API Integrated</span>
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest hover:text-indigo-500 cursor-help transition-colors">ISO-GRID Date-Key Join Mode</span>
       </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import { stockApi, type RealtimePrice } from '@/api'
import * as echarts from 'echarts'

const store = useSentimentStore()
const timeRange = ref<'intraday' | 'historical'>('intraday')
const selectedSymbols = ref<string[]>([])
const loadingPrice = ref(false)
const rtPrices = ref<Record<string, RealtimePrice>>({})
const comparisonData = ref<any[]>([])
const historicalCache = ref<Record<string, any>>({})

const colors = ['#6366f1', '#14b8a6', '#f43f5e', '#f59e0b', '#8b5cf6', '#22c55e']

// Chart refs
const priceSpreadRef = ref<HTMLElement>()
let priceChart: echarts.ECharts | null = null

function getStockName(symbol: string) {
  return store.sentimentData.find(s => s.stock_symbol === symbol)?.stock_name || symbol
}

function getStockColor(symbol: string) {
  const index = store.sentimentData.findIndex(s => s.stock_symbol === symbol)
  return colors[index % colors.length]
}

function toggleStock(symbol: string) {
  if (selectedSymbols.value.includes(symbol)) {
    selectedSymbols.value = selectedSymbols.value.filter(s => s !== symbol)
  } else {
    if (selectedSymbols.value.length >= 2) {
      selectedSymbols.value = [selectedSymbols.value[1], symbol]
    } else {
      selectedSymbols.value.push(symbol)
    }
  }
}

const currentDiff = computed(() => {
  if (selectedSymbols.value.length < 2) return 0
  const p1 = rtPrices.value[selectedSymbols.value[0]]?.price || 0
  const p2 = rtPrices.value[selectedSymbols.value[1]]?.price || 0
  return p1 - p2
})

const priceDiffColor = computed(() => {
  if (currentDiff.value > 0) return 'text-rose-600'
  if (currentDiff.value < 0) return 'text-emerald-600'
  return 'text-slate-500'
})

// Data Fetching
async function fetchComparisonData() {
  if (selectedSymbols.value.length !== 2) return
  loadingPrice.value = true
  try {
    const symbols = selectedSymbols.value
    // 1. Fetch Realtime for Summary (Use 'last' for summary metrics)
    const rtLastResp = await stockApi.getComparisonRealtime(symbols, 'last')
    rtPrices.value = rtLastResp.data as any
    
    // 2. Fetch Time-Series for Chart
    if (timeRange.value === 'historical') {
      const cacheKey = symbols.sort().join(',')
      let data
      if (historicalCache.value[cacheKey]) {
        data = historicalCache.value[cacheKey]
      } else {
        const histResp = await stockApi.getComparisonHistorical(symbols, 30)
        data = histResp.data
        historicalCache.value[cacheKey] = data
      }
      
      const s1 = data[symbols[0]] || []
      const s2 = data[symbols[1]] || []
      comparisonData.value = s1.map((item: any, idx: number) => {
        const item2 = s2[idx]
        return { 
          time: item.date, 
          p1: item.price, 
          p2: item2 ? item2.price : 0, 
          diff: item2 ? (item.price - item2.price) : 0 
        }
      })
    } else {
      // Intraday
      const rtMinResp = await stockApi.getComparisonRealtime(symbols, 'minute')
      const data = rtMinResp.data
      const s1 = data[symbols[0]] || []
      const s2 = data[symbols[1]] || []
      comparisonData.value = s1.map((item: any, idx: number) => {
        const item2 = s2[idx]
        const formattedTime = `${item.time.slice(0, 2)}:${item.time.slice(2, 4)}`
        return { 
          time: formattedTime, 
          p1: item.price, 
          p2: item2 ? item2.price : 0, 
          diff: item2 ? (item.price - item2.price) : 0 
        }
      })
    }
    updatePriceChart()
  } catch (e) {
    console.error('Fetch Comparison Error', e)
    comparisonData.value = []
  } finally {
    loadingPrice.value = false
  }
}

function updatePriceChart() {
  if (!priceSpreadRef.value) return
  if (!priceChart) priceChart = echarts.init(priceSpreadRef.value)
  if (!comparisonData.value.length) {
    priceChart.clear()
    return
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: 'rgba(226, 232, 240, 1)',
      borderWidth: 1,
      padding: 0,
      textStyle: { color: '#1e293b' },
      extraCssText: 'box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.1); border-radius: 8px;',
      axisPointer: { lineStyle: { color: 'rgba(99, 102, 241, 0.6)', width: 2, type: 'dashed' } },
      formatter: (params: any) => {
        const data = comparisonData.value[params[0].dataIndex]
        const n1 = getStockName(selectedSymbols.value[0])
        const n2 = getStockName(selectedSymbols.value[1])
        return `
          <div class="p-3 min-w-[200px]">
            <div class="text-[10px] text-slate-500 font-bold mb-3 uppercase tracking-widest border-b border-slate-100 pb-2">${data.time}</div>
            <div class="space-y-2 mb-3">
              <div class="flex justify-between items-center">
                <span class="text-[11px] text-indigo-600 font-bold">${n1}</span>
                <span class="text-xs font-mono font-bold text-slate-800">${data.p1.toFixed(2)}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-[11px] text-emerald-600 font-bold">${n2}</span>
                <span class="text-xs font-mono font-bold text-slate-800">${data.p2.toFixed(2)}</span>
              </div>
            </div>
            <div class="bg-slate-50 p-2 rounded-lg flex justify-between items-center border border-slate-100">
              <span class="text-[10px] text-slate-500 font-bold uppercase">对冲价差 (Diff)</span>
              <span class="text-sm font-black font-mono ${data.diff > 0 ? 'text-rose-600' : 'text-emerald-600'}">
                ${data.diff > 0 ? '+' : ''}${data.diff.toFixed(2)}
              </span>
            </div>
          </div>
        `
      }
    },
    grid: { left: '1%', right: '1%', bottom: '5%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: comparisonData.value.map(d => d.time.length > 5 ? d.time.slice(5) : d.time), 
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
      axisLabel: { color: '#475569', fontSize: 10, fontWeight: '800', fontFamily: 'Monaco, Inter' },
      axisPointer: { show: true }
    },
    yAxis: {
      type: 'value',
      scale: true,
      position: 'right',
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.05)' } },
      axisLabel: { color: '#475569', fontSize: 10, fontWeight: '800', fontFamily: 'Monaco, Inter' }
    },
    series: [
      {
        name: 'Spread',
        type: 'line',
        showSymbol: false,
        smooth: true,
        data: comparisonData.value.map(d => d.diff),
        lineStyle: { width: 3, color: '#6366f1', shadowBlur: 10, shadowColor: 'rgba(99, 102, 241, 0.2)' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(99, 102, 241, 0.15)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0)' }
          ])
        },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: 0, lineStyle: { color: 'rgba(0,0,0,0.15)', type: 'solid', width: 1.5 } }],
          label: { show: false }
        }
      }
    ]
  }
  priceChart.setOption(option)
}

onMounted(async () => {
  if (!store.sentimentData.length) await store.fetchLatestSentiment()
  
  const hasDonge = store.sentimentData.find(s => s.stock_symbol === 'SZ000423')
  const hasYanghe = store.sentimentData.find(s => s.stock_symbol === 'SZ002304')
  
  if (hasDonge && hasYanghe) {
    selectedSymbols.value = ['SZ000423', 'SZ002304']
  } else if (store.sentimentData.length >= 2) {
    selectedSymbols.value = [store.sentimentData[0].stock_symbol, store.sentimentData[1].stock_symbol]
  }
  
  window.addEventListener('resize', () => priceChart?.resize())
})

onUnmounted(() => {
  window.removeEventListener('resize', () => priceChart?.resize())
  priceChart?.dispose()
})

watch([selectedSymbols, timeRange], () => {
  fetchComparisonData()
}, { deep: true, immediate: true })
</script>

<style scoped>
.text-gradient {
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-image: linear-gradient(to right, var(--tw-gradient-from), var(--tw-gradient-to));
}
</style>

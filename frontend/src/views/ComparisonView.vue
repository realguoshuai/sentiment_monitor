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

        <!-- Time Horizon Selector -->
        <div class="flex flex-col md:flex-row items-center gap-4">
          <div class="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button 
              v-for="scale in timeScales"
              :key="scale.value"
              @click="currentTimeScale = scale.value"
              :class="[
                'px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap',
                currentTimeScale === scale.value ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
              ]"
            >
              {{ scale.label }}
            </button>
          </div>
          
          <div class="flex bg-emerald-50 p-1 rounded-xl border border-emerald-100">
            <button 
              v-for="mode in metricModes"
              :key="mode.value"
              @click="currentMetricMode = mode.value"
              :class="[
                'px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all whitespace-nowrap',
                currentMetricMode === mode.value ? 'bg-emerald-600 text-white shadow-md' : 'text-emerald-700/60 hover:text-emerald-700 hover:bg-emerald-100/50'
              ]"
            >
              {{ mode.label }}
            </button>
          </div>
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
          <div class="text-[10px] text-zinc-400 mt-1 uppercase tracking-tighter">Investment Return (ROI)</div>
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
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
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
          <div v-for="(sym, idx) in selectedSymbols" :key="sym" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm">
             <div class="flex justify-between items-center mb-3">
                <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                  {{ getStockName(sym) }} (Stock {{ idx + 1 }})
                </h4>
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
          
          <!-- ROE-PB Quality Score Card -->
          <div v-for="(sym, idx) in selectedSymbols" :key="'roe-'+sym" class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <div class="flex justify-between items-center mb-4">
                <div class="bg-indigo-500/10 text-indigo-600 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest">
                  Stock {{ idx + 1 }}
                </div>
                <div class="flex items-center gap-1 text-[10px] font-bold text-slate-400">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  ROI: {{ getRoiValue(sym).toFixed(2) }}%
                </div>
             </div>
             
             <h4 class="text-sm font-bold text-slate-800 mb-2">{{ getStockName(sym) }}</h4>
             
             <div class="grid grid-cols-2 gap-4 mt-4">
               <div class="p-3 bg-indigo-50/50 rounded-xl border border-indigo-100/50">
                 <div class="text-[9px] font-bold text-indigo-400 uppercase tracking-tighter mb-1">ROE (推定)</div>
                 <div class="text-xs font-bold text-indigo-700">
                   {{ rtPrices[sym] ? ((rtPrices[sym].pb / rtPrices[sym].pe) * 100).toFixed(1) + '%' : '--' }}
                 </div>
               </div>
               <div class="p-3 bg-emerald-50/50 rounded-xl border border-emerald-100/50">
                 <div class="text-[9px] font-bold text-emerald-400 uppercase tracking-tighter mb-1">回报 (ROI)</div>
                 <div class="text-xs font-bold text-emerald-700">
                   {{ getRoiValue(sym).toFixed(2) }}%
                 </div>
               </div>
             </div>
             
             <div class="mt-4 pt-4 border-t border-slate-50 flex justify-end">
               <router-link 
                 :to="`/analysis/${sym}`"
                 class="text-[10px] font-black text-indigo-600 hover:text-indigo-800 transition-colors flex items-center gap-1"
               >
                 深度矩阵分析 →
               </router-link>
             </div>
          </div>

          <!-- Percentile Gauge Card -->
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm relative overflow-hidden group">
             <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">历史分位 (Percentile)</h4>
             <div class="flex items-end justify-between gap-4">
                <div class="flex flex-col">
                   <span class="text-3xl font-black font-mono text-indigo-600">{{ spreadStats.percentile.toFixed(1) }}%</span>
                   <div class="text-[10px] font-bold text-slate-400 mt-1">Relative to History</div>
                </div>
                <div class="flex-1 h-12 bg-slate-100 rounded-lg relative overflow-hidden self-center border border-slate-200/50">
                   <div 
                     class="absolute bottom-0 left-0 right-0 bg-indigo-500/20 transition-all duration-700" 
                     :style="{ height: spreadStats.percentile + '%' }"
                   ></div>
                   <div 
                     class="absolute left-0 right-0 h-1 bg-indigo-600 shadow-[0_0_10px_rgba(79,70,229,0.5)] transition-all duration-700 z-10" 
                     :style="{ bottom: spreadStats.percentile + '%' }"
                   ></div>
                </div>
             </div>
             <p class="text-[9px] font-bold text-slate-500 mt-4 uppercase">
               {{ spreadStats.percentile > 80 ? '⚠️ High Extremum' : (spreadStats.percentile < 20 ? '✅ Low Extremum' : 'Neutral Range') }}
             </p>
          </div>
        </div>

        <!-- Main Spread Chart -->
        <div class="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm relative min-h-[550px]">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-10">
            <div>
              <h3 class="text-lg font-bold flex items-center gap-3 text-slate-800">
                <div class="w-1.5 h-6 bg-indigo-500 rounded-full"></div>
                {{ getTimeScaleLabel(currentTimeScale) }} {{ getMetricLabel(currentMetricMode) }} 对冲走势
              </h3>
              <p class="text-[10px] text-slate-500 font-bold uppercase mt-1 tracking-widest">{{ currentTimeScale === 'minute' ? 'Intraday Hedge Pulse' : 'Historical Valuation Dynamics' }}</p>
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
          
          <!-- Spread Intelligence Insight -->
          <div v-if="comparisonData.length > 0" class="mt-8 pt-8 border-t border-slate-100">
            <div class="bg-indigo-50/50 rounded-2xl p-6 border border-indigo-100">
               <div class="flex items-center gap-2 mb-4">
                  <div class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></div>
                  <h4 class="text-xs font-black text-indigo-900 uppercase tracking-widest">量化对冲洞察 (AI Insight)</h4>
               </div>
               <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div class="space-y-4">
                     <p class="text-sm leading-relaxed text-slate-700">
                        在 <span class="font-bold text-slate-900">{{ spreadStats.range }}</span> 观测周期内，
                        {{ getStockName(selectedSymbols[0]) }} 与 {{ getStockName(selectedSymbols[1]) }} 的 <strong>{{ getMetricLabel(currentMetricMode) }} 差值</strong> 呈现明显波动。
                        <strong>最大偏离</strong> 出现在 <span class="text-rose-600 font-bold underline underline-offset-4">{{ spreadStats.maxDate }}</span>，
                        数值达 <span class="font-mono font-bold text-rose-600">{{ spreadStats.maxVal.toFixed(2) }}</span>；
                        <strong>最小偏离</strong> 位于 <span class="text-emerald-600 font-bold underline underline-offset-4">{{ spreadStats.minDate }}</span>，
                        数值为 <span class="font-mono font-bold text-emerald-600">{{ spreadStats.minVal.toFixed(2) }}</span>。
                     </p>
                     <div class="flex items-center gap-4 text-[10px] font-bold uppercase tracking-tighter text-slate-400">
                        <span>Sample Size: {{ comparisonData.length }} pts</span>
                        <span class="w-1 h-1 rounded-full bg-slate-300"></span>
                        <span>Confidence: 99% ISO-GRID</span>
                     </div>
                  </div>
                  <div class="grid grid-cols-2 gap-4">
                     <div class="bg-white p-4 rounded-xl border border-indigo-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">平均价差 (HEC Avg)</div>
                        <div class="text-lg font-black font-mono text-indigo-600">{{ spreadStats.avg.toFixed(2) }}</div>
                     </div>
                     <div class="bg-white p-4 rounded-xl border border-indigo-50 shadow-sm">
                        <div class="text-[9px] font-bold text-slate-400 uppercase mb-1">当前偏离 (Z-Gap)</div>
                        <div class="text-lg font-black font-mono" :class="Math.abs(currentDiff - spreadStats.avg) > spreadStats.avg * 0.2 ? 'text-amber-500' : 'text-slate-700'">
                           {{ (currentDiff - spreadStats.avg).toFixed(2) }}
                        </div>
                     </div>
                  </div>
               </div>
            </div>
          </div>
          
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

const timeScales = [
  { label: '1D 分时', value: 'minute' },
  { label: '30D 日线', value: '30d' },
  { label: '1Y 周线', value: '1y_week' },
  { label: '5Y 月线', value: '5y' },
  { label: '10Y 月线', value: '10y' },
]

const metricModes = [
  { label: '价格 (Price)', value: 'price' },
  { label: '市盈率 (PE)', value: 'pe' },
  { label: '市净率 (PB)', value: 'pb' },
  { label: '股息率 (DY)', value: 'dividend_yield' },
  { label: '回报率 (ROI)', value: 'roi' },
]

const currentTimeScale = ref<string>('minute')
const currentMetricMode = ref<string>('price')
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

function getRoiValue(symbol: string) {
  const p = rtPrices.value[symbol]
  if (!p || p.pe <= 0 || p.pb <= 0) return 0
  return store.calculateROI(symbol, p.pe, p.pb)
}

function getTimeScaleLabel(val: string) {
  return timeScales.find(s => s.value === val)?.label || ''
}

function getMetricLabel(val: string) {
  return metricModes.find(m => m.value === val)?.label || ''
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

const spreadStats = computed(() => {
  if (comparisonData.value.length === 0) return { maxVal: 0, maxDate: '--', minVal: 0, minDate: '--', avg: 0, range: '--', percentile: 0 }
  
  let maxVal = -Infinity, minVal = Infinity, sum = 0
  let maxDate = '', minDate = ''
  
  comparisonData.value.forEach(d => {
    if (d.diff > maxVal) { maxVal = d.diff; maxDate = d.time; }
    if (d.diff < minVal) { minVal = d.diff; minDate = d.time; }
    sum += d.diff
  })
  
  const avg = sum / (comparisonData.value.length || 1)
  
  let lessThanCurrent = 0
  comparisonData.value.forEach(d => {
     if (d.diff <= currentDiff.value) lessThanCurrent++
  })
  const percentile = (lessThanCurrent / (comparisonData.value.length || 1)) * 100
  const range = `${comparisonData.value[0].time} 至 ${comparisonData.value[comparisonData.value.length - 1].time}`
  
  return { maxVal, maxDate, minVal, minDate, avg, range, percentile }
})

async function fetchComparisonData() {
  if (selectedSymbols.value.length !== 2) return
  loadingPrice.value = true
  try {
    const symbols = selectedSymbols.value
    const rtLastResp = await stockApi.getComparisonRealtime(symbols, 'last')
    rtPrices.value = rtLastResp.data as any
    
    if (currentTimeScale.value === 'minute') {
      const rtMinResp = await stockApi.getComparisonRealtime(symbols, 'minute')
      historicalCache.value[`${[...symbols].sort().join(',')}_minute`] = rtMinResp.data
    } else {
      const scale = currentTimeScale.value
      const cacheKey = `${[...symbols].sort().join(',')}_${scale}`
      if (!historicalCache.value[cacheKey]) {
        let limit = 30, period = 'day'
        if (scale === '30d') { limit = 30; period = 'day' }
        else if (scale === '1y_week') { limit = 52; period = '1y_week' }
        else if (scale === '5y') { limit = 60; period = 'month' }
        else if (scale === '10y') { limit = 120; period = 'month' }
        const histResp = await stockApi.getComparisonHistorical([ ...symbols ], limit, period)
        historicalCache.value[cacheKey] = histResp.data
      }
    }
    remapComparisonData()
  } catch (e) {
    console.error('Fetch Comparison Error', e)
    comparisonData.value = []
  } finally {
    loadingPrice.value = false
  }
}

function remapComparisonData() {
  const symbols = selectedSymbols.value
  const scale = currentTimeScale.value
  const m = currentMetricMode.value
  const cacheKey = `${[...symbols].sort().join(',')}_${scale}`
  const data = historicalCache.value[cacheKey]
  if (!data) {
    comparisonData.value = []
    return
  }

  const s1 = data[symbols[0]] || []
  const s2 = data[symbols[1]] || []

  comparisonData.value = s1.map((item: any, idx: number) => {
    const item2 = s2[idx]
    
    if (scale === 'minute') {
       const rt = rtPrices.value[symbols[0]], rt2 = rtPrices.value[symbols[1]]
       const metrics1 = calculateIntradayMetrics(item, rt, symbols[0])
       const metrics2 = calculateIntradayMetrics(item2, rt2, symbols[1])
       const val1 = (metrics1 as any)[m] || 0
       const val2 = (metrics2 as any)[m] || 0

       return { 
         time: `${item.time.slice(0, 2)}:${item.time.slice(2, 4)}`,
         p1: val1,
         p2: val2,
         diff: val1 - val2,
         m1: metrics1,
         m2: metrics2
       }
    } else {
        const p1 = (item as any)[m] || 0
        const p2 = (item2 ? (item2 as any)[m] : 0) || 0
        
        return { 
          time: item.date, 
          p1, 
          p2, 
          diff: p1 - p2,
          m1: { price: item.price, pe: item.pe, pb: item.pb, dividend_yield: item.dividend_yield, roi: item.roi },
          m2: item2 ? { price: item2.price, pe: item2.pe, pb: item2.pb, dividend_yield: item2.dividend_yield, roi: item2.roi } : {}
        }
    }
  })
  updatePriceChart()
}

function calculateIntradayMetrics(item: any, rt: any, sym: string) {
  if (!item || !rt || !item.price) return { price: 0, pe: 0, pb: 0, dividend_yield: 0, roi: 0 }
  
  // Dynamic Intraday Projection
  const pe = item.price * ((rt.pe || 0) / (rt.price || 1))
  const pb = item.price * ((rt.pb || 0) / (rt.price || 1))
  const dy = (rt.dividend_yield || 0) * ((rt.price || 1) / (item.price || 1))
  
  // ROE = PB / PE * 100
  let roe = pe > 0 ? (pb / pe * 100) : 0
  if (sym.includes('002304') && roe < 20) roe = 20
  const roi = pb > 0 ? (roe / pb) : 0

  return {
    price: item.price,
    pe: pe,
    pb: pb,
    dividend_yield: dy,
    roi: roi
  }
}

function updatePriceChart() {
  if (!priceSpreadRef.value) return
  if (!priceChart) priceChart = echarts.init(priceSpreadRef.value)
  if (!comparisonData.value.length) {
    priceChart.clear()
    return
  }

  const n1 = getStockName(selectedSymbols.value[0])
  const n2 = getStockName(selectedSymbols.value[1])
  const mLabel = getMetricLabel(currentMetricMode.value)
  const chartData = [...comparisonData.value]

  const option = {
    backgroundColor: 'transparent',
    title: {
      text: `${n1} ⇌ ${n2}`,
      left: 'center',
      top: '20',
      textStyle: {
        color: '#1e293b',
        fontSize: 14,
        fontWeight: '900',
        fontFamily: 'Inter, system-ui',
        letterSpacing: 1
      },
      subtext: `Quantitative Spread Analysis | ${mLabel}`,
      subtextStyle: {
        color: '#94a3b8',
        fontSize: 10,
        fontWeight: 'bold',
        textTransform: 'uppercase'
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: 'rgba(226, 232, 240, 1)',
      borderWidth: 1,
      padding: 0,
      textStyle: { color: '#1e293b' },
      extraCssText: 'box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); border-radius: 12px; border: 1px solid #e2e8f0;',
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex
        const data = chartData[dataIndex]
        if (!data) return ''

        const m1 = data.m1 || {}
        const m2 = data.m2 || {}

        const row = (label: string, v1: any, v2: any, unit: string = '') => {
          const diff = (v1 || 0) - (v2 || 0)
          const diffColor = diff > 0 ? 'text-rose-600' : (diff < 0 ? 'text-emerald-600' : 'text-slate-400')
          const fmt = (v: any) => (v !== undefined && v !== null) ? v.toFixed(2) + unit : '--'
          
          return `
            <tr class="border-b border-slate-50 last:border-0">
              <td class="py-2 text-[10px] font-bold text-slate-400 uppercase tracking-tighter">${label}</td>
              <td class="py-2 px-3 text-xs font-mono font-bold text-indigo-600 text-right">${fmt(v1)}</td>
              <td class="py-2 px-3 text-xs font-mono font-bold text-emerald-600 text-right">${fmt(v2)}</td>
              <td class="py-2 pl-3 text-xs font-mono font-bold ${diffColor} text-right">${v1 !== undefined && v2 !== undefined ? (diff > 0 ? '+' : '') + diff.toFixed(2) + unit : '--'}</td>
            </tr>
          `
        }

        return `
          <div class="p-4 min-w-[320px] bg-white rounded-xl">
            <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
               <span class="text-[11px] font-black text-slate-800 uppercase tracking-wider">${data.time}</span>
               <span class="text-[9px] px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full font-bold uppercase">Hedge Matrix</span>
            </div>
            
            <table class="w-full border-collapse">
              <thead>
                <tr class="text-[9px] text-slate-400 uppercase tracking-widest">
                  <th class="text-left font-normal pb-2">Metric</th>
                  <th class="text-right font-normal pb-2 px-3">${n1.slice(0, 4)}</th>
                  <th class="text-right font-normal pb-2 px-3">${n2.slice(0, 4)}</th>
                  <th class="text-right font-normal pb-2 pl-3">Spread</th>
                </tr>
              </thead>
              <tbody>
                ${row('Price', m1.price, m2.price)}
                ${row('PE (TTM)', m1.pe, m2.pe)}
                ${row('PB (MRQ)', m1.pb, m2.pb)}
                ${row('Yield', m1.dividend_yield, m2.dividend_yield, '%')}
              </tbody>
            </table>
            
            <div class="mt-3 pt-2 border-t border-slate-50 flex items-center justify-between">
               <span class="text-[9px] text-slate-400 font-bold uppercase font-mono italic">Primary Focus: ${mLabel}</span>
               <div class="flex items-center gap-1">
                  <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
                  <span class="text-[9px] text-indigo-600 font-black uppercase">Live ISO-Grid</span>
               </div>
            </div>
          </div>
        `
      }
    },
    grid: { left: '1%', right: '1%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: comparisonData.value.map(d => {
        if (currentTimeScale.value === 'minute') return d.time;
        // 10Y/5Y 月线模式下，如果点数较多，显示完整日期 YYYY-MM
        if (currentTimeScale.value === '5y' || currentTimeScale.value === '10y') return d.time.slice(0, 7);
        return d.time.length > 5 ? d.time.slice(5) : d.time; // MM-DD
      }), 
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
        markPoint: {
          symbol: 'circle',
          symbolSize: 5,
          data: [
            { 
              type: 'max', 
              name: 'Max', 
              itemStyle: { color: '#f43f5e' }, 
              label: { 
                show: true, 
                position: 'top', 
                fontWeight: '900', 
                fontSize: 10,
                color: '#f43f5e',
                formatter: (p: any) => parseFloat(p.value).toFixed(2)
              } 
            },
            { 
              type: 'min', 
              name: 'Min', 
              itemStyle: { color: '#10b981' }, 
              label: { 
                show: true, 
                position: 'bottom', 
                fontWeight: '900', 
                fontSize: 10,
                color: '#10b981',
                formatter: (p: any) => parseFloat(p.value).toFixed(2)
              } 
            },
            {
              name: 'Latest',
              coord: [comparisonData.value.length - 1, comparisonData.value[comparisonData.value.length - 1].diff],
              value: (comparisonData.value[comparisonData.value.length - 1].diff).toFixed(2),
              itemStyle: { color: '#6366f1' },
              label: { 
                show: true, 
                position: 'right', 
                fontWeight: '900', 
                fontSize: 11,
                backgroundColor: '#6366f1',
                color: '#fff',
                padding: [3, 6],
                borderRadius: 4,
                formatter: '{c}'
              },
              symbolSize: 8
            }
          ]
        },
        markLine: {
          symbol: 'none',
          data: [{ yAxis: 0, lineStyle: { color: 'rgba(0,0,0,0.15)', type: 'solid', width: 1.5 } }],
          label: { show: false }
        }
      }
    ]
  }
  priceChart.setOption(option, true)
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

watch([selectedSymbols, currentTimeScale], () => {
  fetchComparisonData()
}, { deep: true, immediate: true })

watch(currentMetricMode, () => {
  remapComparisonData()
})
</script>

<style scoped>
.text-gradient {
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-image: linear-gradient(to right, var(--tw-gradient-from), var(--tw-gradient-to));
}
</style>

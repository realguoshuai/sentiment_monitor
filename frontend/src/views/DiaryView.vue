<template>
  <div class="h-screen bg-slate-950 text-slate-100 p-4 flex flex-col overflow-hidden">
    <!-- Header -->
    <header class="flex justify-between items-center mb-4 bg-slate-900/50 backdrop-blur-md border border-white/5 rounded-2xl px-4 py-3 shadow-xl shrink-0">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-indigo-400">
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
        <button
          @click="selectedSymbol && fetchDiaryData(selectedSymbol, true)"
          :disabled="loading"
          class="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-xl text-sm transition-all border border-slate-700 disabled:opacity-40"
          title="刷新数据"
        >
          <svg class="w-4 h-4" :class="{ 'animate-spin': loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M5 19A9 9 0 0019 5M19 5h-4M5 19h4"/>
          </svg>
        </button>
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
    <div v-else class="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">

      <!-- Left 2 Cols: Main Chart -->
      <div class="lg:col-span-2 flex flex-col gap-4 min-h-0">
        <!-- Chart Card -->
        <div class="glass-card p-4 flex flex-col flex-1 min-h-0">
          <div class="flex justify-between items-center mb-2 shrink-0">
            <div>
              <h2 class="text-base font-bold text-slate-200">价格与成交量走势</h2>
              <p class="text-[11px] text-slate-400">缩量买点 · 放量信号 · 价格趋势</p>
            </div>
            <div class="flex gap-4 text-xs">
              <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#f59e0b]"></span>价格</span>
              <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#06b6d4]"></span>成交量</span>
              <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-[#6366f1] border border-dashed border-[#6366f1]"></span>20日均量</span>
            </div>
          </div>
          <div ref="chartRef" class="w-full flex-1 min-h-0"></div>
        </div>

        <!-- Volume Alert Spec Card -->
        <div v-if="diaryData.latest.volume_status === '极度缩量'" class="p-4 rounded-2xl bg-cyan-950/30 border border-cyan-500/30 shadow-[0_0_30px_rgba(6,182,212,0.15)] backdrop-blur-md shrink-0">
          <div class="flex items-start gap-3">
            <div class="text-2xl text-cyan-400 bg-cyan-950/50 p-2 rounded-xl border border-cyan-500/20 shrink-0">💡</div>
            <div>
              <h3 class="text-sm font-bold text-cyan-300 mb-1">极度缩量状态特别提示</h3>
              <p class="text-xs text-slate-400 leading-relaxed">
                当前成交量仅为 20 日均值的 <strong>{{ (diaryData.latest.volume_ratio * 100).toFixed(1) }}%</strong>，属于典型的无流动性杀跌阶段，恐慌杀伤力极小，已进入高安全边际配置区。
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Right 1 Col: Info Panels -->
      <div class="flex flex-col gap-4 min-h-0">

        <!-- Pred Dividend Countdown Card -->
        <div class="glass-card p-4 relative overflow-hidden flex flex-col justify-between group border-cyan-500/20 hover:border-cyan-500/40 shadow-[0_4px_30px_rgba(0,0,0,0.4)] shrink-0">
          <div class="absolute -right-16 -top-16 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl group-hover:bg-cyan-500/20 transition-all duration-500"></div>

          <div>
            <div class="flex justify-between items-start mb-2">
              <div>
                <span class="text-[10px] text-cyan-400 font-semibold tracking-wider uppercase">Next Dividend Countdown</span>
                <h3 class="text-base font-bold text-slate-100">分红除权倒计时</h3>
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

            <!-- Countdown Number -->
            <div class="flex items-baseline gap-2 py-2">
              <span class="text-4xl font-black bg-clip-text text-transparent bg-gradient-to-br from-cyan-300 via-indigo-300 to-indigo-500 tracking-tight animate-pulse-glow">
                {{ diaryData.next_dividend.days_left !== null ? diaryData.next_dividend.days_left : '--' }}
              </span>
              <span class="text-slate-400 text-sm">天后除权</span>
            </div>
          </div>

          <div class="border-t border-white/5 pt-3 flex flex-col gap-1 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-400">方案：</span>
              <span class="text-slate-200 font-medium truncate ml-2">{{ diaryData.next_dividend.plan }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">预计除权日：</span>
              <span class="text-slate-200 font-mono">{{ diaryData.next_dividend.date || '未确立' }}</span>
            </div>
          </div>
        </div>

        <!-- Margin of Safety Details Card -->
        <div class="glass-card p-4 flex flex-col flex-1 min-h-0">
          <h3 class="text-base font-bold text-slate-100 mb-3 flex items-center gap-2 shrink-0">
            <span class="text-indigo-400">🛡️</span> 安全边际监测
          </h3>

          <div class="grid grid-cols-2 gap-3">
            <!-- PE -->
            <div class="bg-slate-900/60 p-3 rounded-xl border border-white/5">
              <span class="text-[11px] text-slate-400 block mb-0.5">动态 PE</span>
              <span class="text-lg font-bold font-mono text-slate-200">{{ (diaryData.latest?.pe ?? 0).toFixed(2) }}</span>
            </div>

            <!-- PB -->
            <div class="bg-slate-900/60 p-3 rounded-xl border border-white/5">
              <span class="text-[11px] text-slate-400 block mb-0.5">静态 PB</span>
              <span class="text-lg font-bold font-mono text-slate-200">{{ (diaryData.latest?.pb ?? 0).toFixed(2) }}</span>
            </div>

            <!-- Dividend Yield -->
            <div class="bg-slate-900/60 p-3 rounded-xl border border-white/5 col-span-2">
              <span class="text-[11px] text-slate-400 block mb-0.5">滚动股息率 (TTM)</span>
              <div class="flex items-baseline gap-1">
                <span class="text-xl font-black font-mono text-emerald-400">{{ (diaryData.latest?.dividend_yield ?? 0).toFixed(2) }}</span>
                <span class="text-xs text-emerald-500 font-bold">%</span>
              </div>
            </div>
          </div>

          <!-- Volume Status Pill -->
          <div class="mt-3 border-t border-white/5 pt-3">
            <div class="flex justify-between items-center mb-1">
              <span class="text-[11px] text-slate-400">20日成交均量对比</span>
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
            <p class="text-[11px] text-slate-400 leading-relaxed">
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
const diaryCache = ref<Record<string, any>>({})

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

const handleResize = () => {
  if (myChart) myChart.resize()
}
window.addEventListener('resize', handleResize)

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (myChart) {
    myChart.dispose()
    myChart = null
  }
  diaryCache.value = {}
})

const onSymbolChange = async () => {
  if (!selectedSymbol.value) return
  await fetchDiaryData(selectedSymbol.value)
}

let _diarySeq = 0
const fetchDiaryData = async (symbol: string, force = false) => {
  if (!force && diaryCache.value[symbol]) {
    diaryData.value = diaryCache.value[symbol]
    await nextTick()
    initChart()
    return
  }
  const seq = ++_diarySeq
  loading.value = true
  error.value = null
  try {
    const res = await stockApi.getMarketDiary(symbol)
    if (seq !== _diarySeq) return
    diaryData.value = res.data
    diaryCache.value[symbol] = res.data
    loading.value = false
    await nextTick()
    initChart()
  } catch (err: any) {
    if (seq !== _diarySeq) return
    error.value = err.response?.data?.error || err.message || '获取盯盘日记失败'
    loading.value = false
  }
}

const initChart = () => {
  if (!chartRef.value || !diaryData.value) return
  if (!diaryData.value.history || diaryData.value.history.length === 0) return
  try {
  if (myChart) {
    myChart.dispose()
  }
  myChart = echarts.init(chartRef.value)
  
  const dates = diaryData.value.history.map((h: any) => h.date || '')
  const volumes = diaryData.value.history.map((h: any) => h.volume || 0.0)
  const ma20s = diaryData.value.history.map((h: any) => h.ma20_volume || 0.0)
  const prices = diaryData.value.history.map((h: any) => h.price || 0.0)
  
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
        let res = `<div style="padding:4px;font-family:monospace;font-size:12px;">
          <div style="font-weight:bold;margin-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;">${params[0].name}</div>`
        params.forEach((p: any) => {
          let val = p.value
          if (p.seriesName === '价格') {
            val = parseFloat(val).toFixed(2) + ' 元'
          } else {
            if (val >= 1e8) val = (val / 1e8).toFixed(2) + ' 亿手'
            else if (val >= 1e4) val = (val / 1e4).toFixed(2) + ' 万手'
            else val = val.toLocaleString() + ' 手'
          }
          res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:4px;">
            <span style="display:flex;align-items:center;gap:6px;">
              <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
              ${p.seriesName}
            </span>
            <span style="font-weight:bold;">${val}</span>
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
        name: '成交量',
        nameTextStyle: { color: '#06b6d4', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#06b6d4',
          fontSize: 10,
          formatter: (v: number) => {
            if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
            if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
            return v
          }
        },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }
      },
      {
        type: 'value',
        name: '价格',
        nameTextStyle: { color: '#f59e0b', fontSize: 10 },
        position: 'right',
        scale: true,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#f59e0b',
          fontSize: 10,
          formatter: (v: number) => v.toFixed(2)
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
        name: '成交量',
        type: 'bar',
        yAxisIndex: 0,
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
        yAxisIndex: 0,
        data: ma20s,
        showSymbol: false,
        lineStyle: { width: 1.5, type: 'dashed' },
        itemStyle: { color: '#6366f1' }
      },
      {
        name: '价格',
        type: 'line',
        yAxisIndex: 1,
        data: prices,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(245, 158, 11, 0.15)' },
              { offset: 1, color: 'rgba(245, 158, 11, 0)' }
            ]
          }
        }
      }
    ]
  }
  
  myChart.setOption(option)
  } catch (e) {
    console.error('Chart init failed:', e)
  }
}

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
.glass-card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 1rem;
}
</style>

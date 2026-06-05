<template>
  <div class="h-screen bg-[#0f172a] text-slate-300 font-sans p-4 overflow-hidden flex flex-col">
    <!-- Top Header -->
    <header class="flex justify-between items-center mb-3 shrink-0">
      <div class="flex items-center gap-3">
        <div class="bg-cyan-500 rounded-lg p-2 shadow-[0_0_10px_rgba(6,182,212,0.4)]">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-xl font-black text-white tracking-wide">价值投资分析终端</h1>
            <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          </div>
          <p class="text-[10px] text-slate-500 tracking-widest mt-0.5">
            深度个股估值与投资回报监测引擎
            <span class="ml-2 px-1.5 py-0.5 bg-indigo-500/10 text-indigo-400 rounded-sm font-bold border border-indigo-500/20">开发者: @雪球小散户</span>
          </p>
        </div>
      </div>

      <div class="flex items-center gap-4">
        <div class="flex items-center gap-1.5 text-xs text-slate-400">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          上次更新: {{ lastUpdate }}
        </div>
        <div class="flex items-center gap-2">
          <button @click="showManageModal = true" class="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors tooltip group relative text-[11px]">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            监控配置
          </button>
          <router-link to="/compare" class="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors text-[11px]">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
            对比分析
          </router-link>
          <router-link to="/screener" class="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors text-[11px]">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L14 13.414V19a1 1 0 01-1.447.894l-2-1A1 1 0 0110 18v-4.586L3.293 6.707A1 1 0 013 6V4z"/></svg>
            条件选股
          </router-link>
          <router-link to="/diary" class="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors text-[11px]">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
            盯盘日记
          </router-link>
          <WidgetDock />
          <button @click="refreshData" class="flex items-center gap-1.5 px-4 py-1.5 bg-[#00df9a] hover:bg-[#00c98a] text-slate-900 font-bold rounded shadow-[0_0_10px_rgba(0,223,154,0.3)] transition-all text-xs">
            <svg class="w-3.5 h-3.5" :class="{'animate-spin': isRefreshing}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
            立即刷新
          </button>
        </div>
      </div>
    </header>

    <main class="w-full flex-1 flex flex-col min-h-0">
      <!-- Sub-header & Status -->
      <div class="flex justify-between items-center mb-2 pt-2 border-t border-slate-700/50 shrink-0">
        <div class="flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full bg-[#00df9a] shadow-[0_0_8px_rgba(0,223,154,0.8)] animate-pulse"></span>
          <span class="text-[10px] font-bold text-[#00df9a] tracking-widest">LIVE TERMINAL</span>
        </div>
        <div class="text-[9px] text-slate-500 font-mono tracking-widest">
          Quotes Update: 10s
        </div>
      </div>

      <div v-if="store.backendStarting" class="mb-3 rounded border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 shrink-0">
        本地分析服务启动中，页面已打开，数据会自动加载...
      </div>

      <div v-if="store.loading && !store.sentimentData.length" class="flex-1 flex justify-center items-center">
         <div class="w-8 h-8 border-4 border-slate-700 border-t-[#00df9a] rounded-full animate-spin"></div>
      </div>

      <template v-else>
        <!-- Section: Stock Grid -->
        <div class="mb-3 shrink-0">
          <div class="flex justify-between items-end mb-2 pr-1">
            <h2 class="text-[15px] font-bold text-white tracking-wide">个股监控看板</h2>
            <div class="text-[10px] text-slate-500 font-mono">共 {{ store.dashboardStocks.length }} 只标的</div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 max-h-[50vh] overflow-y-auto pr-1 custom-scrollbar">
            <StockCard
              v-for="data in store.dashboardStocks"
              :key="data.id"
              :data="data"
            />
          </div>
        </div>

        <!-- Section: Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0 pb-2">
          <!-- Dividend Calendar -->
          <div class="bg-[#1a2332] rounded-xl p-3.5 border border-slate-700/50 flex flex-col min-h-0">
            <div class="flex justify-between items-center mb-2 shrink-0">
               <div class="flex items-center gap-2">
                 <span class="w-1 h-3.5 bg-cyan-400 rounded-full"></span>
                 <h3 class="text-xs font-bold text-white tracking-wide">分红日历</h3>
               </div>
               <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            </div>
            <div class="flex-1 min-h-0">
               <DividendCalendar :data="store.dividendCalendar" />
            </div>
          </div>

          <!-- Hot Score Chart -->
          <div class="bg-[#1a2332] rounded-xl p-3.5 border border-slate-700/50 flex flex-col min-h-0">
            <div class="flex justify-between items-center mb-2 shrink-0">
               <div class="flex items-center gap-2">
                 <span class="w-1 h-3.5 bg-indigo-500 rounded-full"></span>
                 <h3 class="text-xs font-bold text-white tracking-wide">投资回报率</h3>
               </div>
               <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div class="flex-1 min-h-0 relative">
               <HotScoreChart :data="store.roiSortedStocks" class="absolute inset-0" />
            </div>
          </div>
        </div>
      </template>
    </main>

    <StockManagementModal :show="showManageModal" @close="showManageModal = false" />
    <ReleaseNotesModal :show="showReleaseNotes" :version="releaseVersion" @close="handleReleaseNotesClose" />

    <!-- Floating Widget Panels -->
    <WidgetContainer widgetId="portfolio" title="组合仓位 + 分红" icon="📊">
      <PortfolioWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="compound" title="复利计算器" icon="📈">
      <CompoundWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="margin" title="安全边际" icon="🛡️">
      <MarginWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="position" title="仓位管理" icon="🎯">
      <PositionWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="dividendCal" title="分红日历" icon="📅">
      <DividendCalWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="swap" title="换股计算器" icon="🔄">
      <SwapWidget />
    </WidgetContainer>
    <WidgetContainer widgetId="kelly" title="凯利仓位" icon="🎲">
      <KellyWidget />
    </WidgetContainer>

    <!-- 告警面板 -->
    <AlertPanel />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import StockCard from '@/components/StockCard.vue'
import DividendCalendar from '@/components/DividendCalendar.vue'
import HotScoreChart from '@/components/HotScoreChart.vue'
import StockManagementModal from '@/components/StockManagementModal.vue'
import ReleaseNotesModal from '@/components/ReleaseNotesModal.vue'
import WidgetDock from '@/components/WidgetDock.vue'
import AlertPanel from '@/components/AlertPanel.vue'
import WidgetContainer from '@/components/WidgetContainer.vue'
import PortfolioWidget from '@/components/widgets/PortfolioWidget.vue'
import CompoundWidget from '@/components/widgets/CompoundWidget.vue'
import MarginWidget from '@/components/widgets/MarginWidget.vue'
import PositionWidget from '@/components/widgets/PositionWidget.vue'
import DividendCalWidget from '@/components/widgets/DividendCalWidget.vue'
import SwapWidget from '@/components/widgets/SwapWidget.vue'
import KellyWidget from '@/components/widgets/KellyWidget.vue'

const store = useSentimentStore()
const showManageModal = ref(false)
const showReleaseNotes = ref(false)
const isRefreshing = ref(false)
const releaseVersion = '0.1.4'
const releaseNotesStorageKey = `sentiment-monitor-release-notes-${releaseVersion}`

const lastUpdate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const hours = now.getHours().toString().padStart(2, '0')
  const mins = now.getMinutes().toString().padStart(2, '0')
  return `${month}月${day}日 ${hours}:${mins}`
})

const refreshData = async () => {
  if (isRefreshing.value) return
  isRefreshing.value = true
  await Promise.all([
    store.fetchLatestSentiment(),
    store.fetchDividendCalendar(),
    store.fetchRealtimePrices()
  ])
  isRefreshing.value = false
}

const handleReleaseNotesClose = (remember: boolean) => {
  showReleaseNotes.value = false
  if (remember) {
    localStorage.setItem(releaseNotesStorageKey, 'seen')
  }
}

let priceTimer: any = null

onMounted(async () => {
  if (localStorage.getItem(releaseNotesStorageKey) !== 'seen') {
    showReleaseNotes.value = true
  }

  // 第二阶段：核心数据并行获取，分红日历异步不阻塞首屏
  await Promise.all([
    store.fetchStocks(),
    store.sentimentData.length ? Promise.resolve() : store.fetchLatestSentiment(),
    store.fetchRealtimePrices()
  ])
  // 分红日历耗时较长（需逐只调外部 API），异步加载不阻塞渲染
  store.fetchDividendCalendar().catch(() => {})

  priceTimer = setInterval(() => {
    store.fetchRealtimePrices()
  }, 10000)
})

onUnmounted(() => {
  if (priceTimer) clearInterval(priceTimer)
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
}
</style>

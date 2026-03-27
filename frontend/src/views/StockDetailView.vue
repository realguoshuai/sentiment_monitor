<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 px-6 py-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center mb-6">
      <button 
        @click="goBack"
        class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-100 hover:border-slate-300 transition shadow-sm mr-4"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
        </svg>
        <span class="text-sm font-bold">返回看板</span>
      </button>
      <h1 v-if="stockData" class="text-2xl font-black text-slate-800">
        {{ stockData.stock_name }} <span class="text-lg font-mono text-slate-400 ml-2">({{ stockData.stock_symbol }})</span>
      </h1>
    </div>

    <!-- Loading -->
    <div v-if="!stockData" class="text-center py-20">
      <div class="w-10 h-10 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin mx-auto mb-4"></div>
      <p class="text-slate-500 font-bold">加载中...</p>
    </div>

    <template v-else>
      <!-- Stats & Valuation Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <!-- Sentiment Stats -->
        <div class="bg-white rounded-2xl p-4 text-center border border-slate-200 shadow-sm flex flex-col justify-center">
          <div class="text-2xl font-black mb-1" :class="sentimentColor">{{ stockData.sentiment_label }}</div>
          <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">舆情态势</div>
        </div>
        <div class="bg-white rounded-2xl p-4 text-center border border-slate-200 shadow-sm flex flex-col justify-center">
          <div class="text-2xl font-black text-cyan-600 mb-1">{{ stockData.news_count + stockData.report_count + stockData.announcement_count }}</div>
          <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">今日事件总计</div>
        </div>

        <!-- Valuation Details -->
        <div class="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm col-span-2">
          <div class="grid grid-cols-5 gap-2 h-full items-center">
            <div class="text-center">
              <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">动态 PE</div>
              <div class="text-lg font-black font-mono text-slate-800">{{ rtPrice?.pe > 0 ? rtPrice.pe.toFixed(2) : '--' }}</div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">当前 PB</div>
              <div class="text-lg font-black font-mono text-slate-800">{{ rtPrice?.pb > 0 ? rtPrice.pb.toFixed(2) : '--' }}</div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">隐式 ROE</div>
              <div class="text-lg font-black font-mono text-slate-800">{{ roeText }}</div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1 text-indigo-600">投资 ROI</div>
              <div class="text-lg font-black font-mono text-indigo-600">{{ roiText }}</div>
            </div>
            <div class="text-center">
              <div class="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">市盈分位</div>
              <div class="text-lg font-black font-mono text-slate-400">---</div>
            </div>
          </div>
        </div>
      </div>

      <!-- External Platform Links Section -->
      <div class="bg-white rounded-2xl p-6 mb-8 border border-slate-200 shadow-sm">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-slate-800">
          <svg class="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
          </svg>
          官方及社区深度链接
        </h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <a
            v-for="link in allExtraLinks"
            :key="link.name"
            :href="link.url"
            target="_blank"
            class="flex items-center gap-3 p-3 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 rounded-xl transition-all group shadow-sm"
          >
            <div class="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center text-indigo-600 group-hover:bg-indigo-200 text-lg font-black">
              {{ link.name[0] }}
            </div>
            <div>
              <div class="text-sm font-bold text-slate-700 group-hover:text-indigo-600">{{ link.name }}</div>
              <div class="text-[10px] text-slate-400">外部直达链接</div>
            </div>
          </a>
        </div>
      </div>

      <!-- Plan 2: Target Price Tracker -->
      <div class="mb-8">
        <TargetPriceChart :reports="stockData.reports" :currentPrice="rtPrice?.price" />
      </div>

      <!-- Tabs -->
      <ContentTabs
        v-model="activeTab"
        :tabs="[
          { key: 'news', label: `资讯 (${stockData.news_count})` },
          { key: 'reports', label: `研报 (${stockData.report_count})` },
          { key: 'announcements', label: `公告 (${stockData.announcement_count})` },
        ]"
      />

      <!-- Content List -->
      <div class="mt-6">
        <div v-if="currentItems.length === 0" class="text-center py-12 text-slate-400 bg-white rounded-2xl border border-slate-200">
          暂无数据
        </div>
        
        <div v-else class="space-y-3">
          <NewsItem 
            v-for="(item, index) in currentItems" 
            :key="index"
            :item="item"
            :type="activeTab"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSentimentStore } from '@/stores/sentiment'
import ContentTabs from '@/components/ContentTabs.vue'
import NewsItem from '@/components/NewsItem.vue'
import TargetPriceChart from '@/components/TargetPriceChart.vue'

const route = useRoute()
const router = useRouter()
const store = useSentimentStore()

const symbol = route.params.symbol as string
const activeTab = ref<'news' | 'reports' | 'announcements'>('news')

const stockData = computed(() => store.getStockBySymbol(symbol))

const sentimentColor = computed(() => {
  if (!stockData.value) return ''
  if (stockData.value.sentiment_score > 0.2) return 'text-emerald-600'
  if (stockData.value.sentiment_score < -0.2) return 'text-rose-600'
  return 'text-amber-600'
})

const currentItems = computed(() => {
  if (!stockData.value) return []
  switch (activeTab.value) {
    case 'news': return stockData.value.news
    case 'reports': return stockData.value.reports
    case 'announcements': return stockData.value.announcements
    default: return []
  }
})

const pureCode = computed(() => {
  if (!stockData.value) return ''
  return stockData.value.stock_symbol.substring(2)
})

const allExtraLinks = computed(() => {
  if (!stockData.value) return []
  const base = [
    { name: '主要指标', color: 'purple', url: `https://xueqiu.com/snowman/S/${stockData.value.stock_symbol}/detail#/ZYCWZB` },
    { name: '东财F10', color: 'violet', url: `https://emweb.securities.eastmoney.com/PC_HSF10/OperationsRequired/Index?type=soft&code=${stockData.value.stock_symbol}` },
    { name: '雪球社区', color: 'blue', url: `https://xueqiu.com/S/${stockData.value.stock_symbol}` },
    { name: '东财股吧', color: 'rose', url: `http://guba.eastmoney.com/list,${pureCode.value}.html` },
    { name: '融资融券', color: 'amber', url: `https://data.eastmoney.com/rzrq/detail/${pureCode.value}.html` },
    { name: '全网资讯', color: 'cyan', url: `https://so.eastmoney.com/news/s?keyword=${encodeURIComponent(stockData.value.stock_name)}` },
  ]
  
  if (stockData.value.extra_links) {
    try {
      const extra = JSON.parse(stockData.value.extra_links)
      return [...base, ...extra]
    } catch (e) {
      console.error('Failed to parse extra_links', e)
    }
  }
  return base
})

function goBack() {
  router.push('/')
}

// Valuation variables
const rtPrice = computed(() => store.realtimePrices[symbol])

const roeValue = computed(() => {
  if (!rtPrice.value || rtPrice.value.pe <= 0 || rtPrice.value.pb <= 0) return null
  let roe = rtPrice.value.pb / rtPrice.value.pe
  // 洋河股份 ROE 不足 20% 时按 20% 计算
  const stockSymbol = route.params.symbol as string
  if (stockSymbol === 'SZ002304' && roe < 0.20) {
    roe = 0.20
  }
  return roe
})

const roeText = computed(() => {
  if (roeValue.value === null) return '--'
  return (roeValue.value * 100).toFixed(1) + '%'
})

const roiValue = computed(() => {
  if (roeValue.value === null || !rtPrice.value || rtPrice.value.pb <= 0) return null
  return roeValue.value / rtPrice.value.pb
})

const roiText = computed(() => {
  if (roiValue.value === null) return '--'
  return (roiValue.value * 100).toFixed(1) + '%'
})
</script>

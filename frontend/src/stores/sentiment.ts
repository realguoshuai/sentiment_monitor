import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SentimentData, Stock, RealtimePrice } from '@/api'
import { stockApi } from '@/api'

export const useSentimentStore = defineStore('sentiment', () => {
  // State
  const stocks = ref<Stock[]>([])
  const sentimentData = ref<SentimentData[]>([])
  const sentimentTrend = ref<any[]>([])
  const loading = ref(false)
  const isCollecting = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)
  const realtimePrices = ref<Record<string, RealtimePrice>>({})
  const backendStarting = ref(false)
  
  // 新增：Session 级缓存，切换标的秒开
  const analysisCache = ref<Record<string, any>>({})
  const qualityCache = ref<Record<string, any>>({})
  const backtestCache = ref<Record<string, any>>({})

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

  const isStartupNetworkError = (e: any) => {
    const message = String(e?.message || '').toLowerCase()
    const code = String(e?.code || '').toLowerCase()
    return !e?.response || code === 'econnaborted' || message.includes('network error') || message.includes('timeout')
  }

  async function retryDuringStartup<T>(request: () => Promise<T>, attempts = 45): Promise<T> {
    let lastError: any = null

    for (let i = 0; i < attempts; i += 1) {
      try {
        const result = await request()
        backendStarting.value = false
        return result
      } catch (e) {
        lastError = e
        if (!isStartupNetworkError(e) || i === attempts - 1) {
          backendStarting.value = false
          throw e
        }
        backendStarting.value = true
        await sleep(1000)
      }
    }

    backendStarting.value = false
    throw lastError
  }

  // Getters
  const calculateROI = (symbol: string, pe: number, pb: number, dividend_yield: number = 0) => {
    if (pe <= 0 || pb <= 0) return 0
    let roe = (pb / pe) * 100
    return (roe / pb) + dividend_yield
  }

  const sortedStocks = computed(() => {
    return [...sentimentData.value].sort((a, b) => b.sentiment_score - a.sentiment_score)
  })

  const dashboardStocks = computed(() => {
    const sentimentMap = new Map(sentimentData.value.map((item) => [item.stock_symbol, item]))
    const merged: SentimentData[] = [...sortedStocks.value]

    for (const stock of stocks.value) {
      if (sentimentMap.has(stock.symbol)) continue

      merged.push({
        id: -stock.id,
        stock_name: stock.name,
        stock_symbol: stock.symbol,
        date: '',
        sentiment_score: 0,
        sentiment_label: 'pending',
        hot_score: 0,
        news_count: 0,
        report_count: 0,
        announcement_count: 0,
        discussion_count: 0,
        news: [],
        reports: [],
        announcements: [],
        extra_links: stock.extra_links,
        is_pending: true,
      })
    }

    return merged
  })

  const roiSortedStocks = computed(() => {
    return [...dashboardStocks.value].sort((a, b) => {
      const pA = realtimePrices.value[a.stock_symbol]
      const pB = realtimePrices.value[b.stock_symbol]
      const roiA = pA ? calculateROI(a.stock_symbol, pA.pe, pA.pb, pA.dividend_yield) : 0
      const roiB = pB ? calculateROI(b.stock_symbol, pB.pe, pB.pb, pB.dividend_yield) : 0
      return roiB - roiA
    })
  })

  const totalNews = computed(() => 
    sentimentData.value.reduce((sum, s) => sum + s.news_count, 0)
  )

  const totalReports = computed(() => 
    sentimentData.value.reduce((sum, s) => sum + s.report_count, 0)
  )

  const totalAnnouncements = computed(() => 
    sentimentData.value.reduce((sum, s) => sum + s.announcement_count, 0)
  )

  const avgSentiment = computed(() => {
    if (sentimentData.value.length === 0) return 0
    const sum = sentimentData.value.reduce((acc, s) => acc + s.sentiment_score, 0)
    return sum / sentimentData.value.length
  })

  // Actions
  async function fetchStocks() {
    try {
      const response = await retryDuringStartup(() => stockApi.getStocks())
      stocks.value = response.data
    } catch (e) {
      console.error('Failed to fetch stocks:', e)
      error.value = '本地服务启动中，请稍候刷新'
    }
  }

  async function addStock(data: Partial<Stock>) {
    try {
      await stockApi.createStock(data)
      await fetchStocks()
      return true
    } catch (e) {
      console.error('Failed to add stock:', e)
      return false
    }
  }

  async function updateStock(symbol: string, data: Partial<Stock>) {
    try {
      await stockApi.updateStock(symbol, data)
      await fetchStocks()
      return true
    } catch (e) {
      console.error('Failed to update stock:', e)
      return false
    }
  }

  async function removeStock(symbol: string) {
    try {
      await stockApi.deleteStock(symbol)
      await fetchStocks()
      // If the deleted stock was in sentimentData, remove it
      sentimentData.value = sentimentData.value.filter(s => s.stock_symbol !== symbol)
      return true
    } catch (e) {
      console.error('Failed to delete stock:', e)
      return false
    }
  }

  async function fetchLatestSentiment() {
    loading.value = true
    error.value = null
    
    try {
      // 使用 mini=1 模式，只获取基础统计数据，不获取新闻详情列表，大幅加速首页加载
      const response = await retryDuringStartup(() => stockApi.getLatestSentiment({ mini: '1' }))
      sentimentData.value = response.data
      lastUpdated.value = new Date()
    } catch (e: any) {
      error.value = e.response?.data?.message || '获取数据失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchSentimentTrend() {
    try {
      const response = await stockApi.getOverallSentimentTrend(7)
      sentimentTrend.value = response.data
    } catch (e) {
      console.error('Failed to fetch sentiment trend:', e)
    }
  }

  async function triggerCollection() {
    isCollecting.value = true
    try {
      await stockApi.triggerCollection()
      return true
    } catch (e: any) {
      console.error('Failed to trigger collection:', e)
      return false
    } finally {
      isCollecting.value = false
    }
  }

  async function fetchRealtimePrices() {
    try {
      const response = await retryDuringStartup(() => stockApi.getRealtimePrices(), 10)
      realtimePrices.value = response.data
    } catch (e) {
      console.error('Failed to fetch realtime prices:', e)
    }
  }

  // --- 新增：带缓存的获取方法 ---
  async function getAnalysis(symbol: string, force = false) {
    if (!force && analysisCache.value[symbol]) return analysisCache.value[symbol]
    try {
      const res = await stockApi.getAnalysis(symbol)
      analysisCache.value[symbol] = res.data
      return res.data
    } catch (e) {
      console.error(`Failed to fetch analysis for ${symbol}:`, e)
      throw e
    }
  }

  async function getQuality(symbol: string, force = false) {
    if (!force && qualityCache.value[symbol]) return qualityCache.value[symbol]
    try {
      const res = await stockApi.getQualityAnalysis(symbol)
      qualityCache.value[symbol] = res.data
      return res.data
    } catch (e) {
      console.error(`Failed to fetch quality for ${symbol}:`, e)
      throw e
    }
  }

  async function getBacktest(symbol: string, force = false) {
    if (!force && backtestCache.value[symbol]) return backtestCache.value[symbol]
    try {
      const res = await stockApi.getHistoryBacktest(symbol)
      backtestCache.value[symbol] = res.data
      return res.data
    } catch (e) {
      console.error(`Failed to fetch backtest for ${symbol}:`, e)
      throw e
    }
  }

  function getStockBySymbol(symbol: string) {
    return dashboardStocks.value.find(s => s.stock_symbol === symbol)
  }

  return {
    stocks,
    sentimentData,
    sentimentTrend,
    loading,
    isCollecting,
    error,
    lastUpdated,
    realtimePrices,
    backendStarting,
    calculateROI,
    roiSortedStocks,
    sortedStocks,
    dashboardStocks,
    totalNews,
    totalReports,
    totalAnnouncements,
    avgSentiment,
    fetchStocks,
    addStock,
    updateStock,
    removeStock,
    fetchLatestSentiment,
    fetchSentimentTrend,
    triggerCollection,
    fetchRealtimePrices,
    getStockBySymbol,
    // Caches & New Actions
    analysisCache,
    qualityCache,
    backtestCache,
    getAnalysis,
    getQuality,
    getBacktest,
  }
})

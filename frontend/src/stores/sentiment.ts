import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SentimentData, Stock, RealtimePrice } from '@/api'
import { stockApi } from '@/api'

export const useSentimentStore = defineStore('sentiment', () => {
  // State
  const stocks = ref<Stock[]>([])
  const sentimentData = ref<SentimentData[]>([])
  const loading = ref(false)
  const isCollecting = ref(false)
  const error = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)
  const realtimePrices = ref<Record<string, RealtimePrice>>({})

  // Getters
  const calculateROI = (symbol: string, pe: number, pb: number) => {
    if (pe <= 0 || pb <= 0) return 0
    let roe = (pb / pe) * 100
    // 洋河股份(002304) ROE 不足 20% 时按 20% 计算
    const isYanghe = symbol.includes('002304')
    if (isYanghe && roe < 20) {
      roe = 20
    }
    return roe / pb
  }

  const roiSortedStocks = computed(() => {
    return [...sentimentData.value].sort((a, b) => {
      const pA = realtimePrices.value[a.stock_symbol]
      const pB = realtimePrices.value[b.stock_symbol]
      const roiA = pA ? calculateROI(a.stock_symbol, pA.pe, pA.pb) : 0
      const roiB = pB ? calculateROI(b.stock_symbol, pB.pe, pB.pb) : 0
      return roiB - roiA
    })
  })

  const sortedStocks = computed(() => {
    return [...sentimentData.value].sort((a, b) => b.sentiment_score - a.sentiment_score)
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
      const response = await stockApi.getStocks()
      stocks.value = response.data
    } catch (e) {
      console.error('Failed to fetch stocks:', e)
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
      const response = await stockApi.getLatestSentiment()
      sentimentData.value = response.data
      lastUpdated.value = new Date()
    } catch (e: any) {
      error.value = e.response?.data?.message || '获取数据失败'
      sentimentData.value = []
    } finally {
      loading.value = false
    }
  }

  async function triggerCollection() {
    isCollecting.value = true
    try {
      await stockApi.triggerCollection()
      // 给后台一点启动时间，然后开始轮询或等待
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
      const response = await stockApi.getRealtimePrices()
      realtimePrices.value = response.data
    } catch (e) {
      console.error('Failed to fetch realtime prices:', e)
    }
  }

  function getStockBySymbol(symbol: string) {
    return sentimentData.value.find(s => s.stock_symbol === symbol)
  }

  return {
    stocks,
    sentimentData,
    loading,
    isCollecting,
    error,
    lastUpdated,
    realtimePrices,
    calculateROI,
    roiSortedStocks,
    sortedStocks,
    totalNews,
    totalReports,
    totalAnnouncements,
    avgSentiment,
    fetchStocks,
    addStock,
    updateStock,
    removeStock,
    fetchLatestSentiment,
    triggerCollection,
    fetchRealtimePrices,
    getStockBySymbol,
  }
})

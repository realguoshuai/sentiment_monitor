import axios from 'axios'

/**
 * 动态获取 API 基础路径
 * 优先级: 环境变量 > 自动探测 (本地 vs 远程)
 */
const getBaseURL = () => {
  // 1. 优先使用环境变量 (支持 Vite)
  const envBase = import.meta.env.VITE_API_BASE_URL
  if (envBase) return envBase

  // 2. 自动探测逻辑
  if (typeof window !== 'undefined') {
    const { hostname, protocol } = window.location
    // 如果是开发环境或本地访问，指向开发服务器
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000/api'
    }
    // 生产环境自动指向当前域名的 /api 路径
    return `${protocol}//${hostname}${window.location.port ? ':' + window.location.port : ''}/api`
  }
  return '/api'
}

const api = axios.create({
  baseURL: '/api',
  timeout: 15000, // 深度分析耗时较长，增加超时时间
  headers: {
    'Content-Type': 'application/json',
  },
})

// --- 全局拦截器 ---

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可以在此处添加通用 Auth Header 或全局 Loading 状态
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // 统一处理后端错误响应
    const message = error.response?.data?.message || error.message || '网络请求故障'
    console.error(`[API Error] ${error.config?.url}:`, message)
    
    // 可以在此处集成 UI 通知库 (如 message.error)
    return Promise.reject(error)
  }
)

// Types
export interface Stock {
  id: number
  name: string
  symbol: string
  keywords: string[]
  extra_links: string
}

export interface RealtimePrice {
  price: number
  change_percent: number
  change_amount: number
  pe: number
  pb: number
  dividend_yield: number
  market_cap: number
}

export interface News {
  title: string
  pub_date: string
  source: string
  url: string
}

export interface Report {
  title: string
  pub_date: string
  org: string
  rating: string
  url: string
  target_price?: number
}

export interface Announcement {
  title: string
  pub_date: string
  url: string
}

export interface SentimentData {
  id: number
  stock_name: string
  stock_symbol: string
  date: string
  sentiment_score: number
  sentiment_label: string
  hot_score: number
  news_count: number
  report_count: number
  announcement_count: number
  discussion_count: number
  news: News[]
  reports: Report[]
  announcements: Announcement[]
  extra_links?: string
}

// API functions
export const stockApi = {
  getStocks: () => api.get<Stock[]>('/stocks/'),
  createStock: (data: Partial<Stock>) => api.post<Stock>('/stocks/', data),
  deleteStock: (symbol: string) => api.delete(`/stocks/${symbol}/`),
  getTodaySentiment: () => api.get<SentimentData[]>('/sentiment/today/'),
  getLatestSentiment: () => api.get<SentimentData[]>('/sentiment/latest/'),
  getSentimentBySymbol: (symbol: string) => api.get<SentimentData>(`/sentiment/${symbol}/`),
  triggerCollection: () => api.post<{ status: string, message: string }>('/collect/'),
  getRealtimePrices: () => api.get<Record<string, RealtimePrice>>('/sentiment/realtime_prices/'),
  getComparisonRealtime: (symbols: string[], type: 'last' | 'minute' = 'last') =>
    api.get<Record<string, any>>(`/sentiment/comparison_realtime/?symbols=${symbols.join(',')}&type=${type}`),
  getComparisonHistorical: (symbols: string[], limit: number = 30, period: string = 'day') =>
    api.get<Record<string, any[]>>(`/sentiment/comparison_historical/?symbols=${symbols.join(',')}&limit=${limit}&period=${period}`),
  searchStocks: (q: string) => api.get<any[]>('/sentiment/search/', { params: { q } }),
  getAnalysis: (symbol: string) => api.get<any>(`/sentiment/analysis/?symbol=${symbol}`),
  getHistoryBacktest: (symbol: string) => api.get<any>(`/sentiment/history-backtest/?symbol=${symbol}`),
  getQualityAnalysis: (symbol: string, includeShareholder: boolean = true) =>
    api.get<any>(
      `/sentiment/quality/?symbol=${symbol}&include_shareholder=${includeShareholder ? 1 : 0}`,
      { timeout: 45000 },
    ),
  getQualityShareholderStructure: (symbol: string) =>
    api.get<any>(`/sentiment/quality/shareholder-structure/?symbol=${symbol}`, { timeout: 45000 }),
}

export default api

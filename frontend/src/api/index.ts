import axios from 'axios'

declare global {
  interface Window {
    desktopMeta?: {
      backendUrl?: string
      apiBaseUrl?: string
    }
  }
}

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
    if (window.desktopMeta?.apiBaseUrl) {
      return window.desktopMeta.apiBaseUrl
    }

    const { hostname, protocol, port } = window.location
    if (protocol === 'file:') {
      return 'http://127.0.0.1:8000/api'
    }
    // 如果是开发环境或本地访问，指向开发服务器
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000/api'
    }
    // 生产环境自动指向当前域名的 /api 路径
    return `${protocol}//${hostname}${port ? ':' + port : ''}/api`
  }
  return '/api'
}

const api = axios.create({
  baseURL: getBaseURL(),
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const RETRYABLE_METHODS = new Set(['get', 'head', 'options'])
const RETRYABLE_STATUS = new Set([408, 429, 502, 503, 504])

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

const shouldRetryRequest = (error: any) => {
  const config = error.config
  if (!config) return false

  const method = String(config.method || 'get').toLowerCase()
  if (!RETRYABLE_METHODS.has(method)) return false

  const retryCount = config.__retryCount || 0
  if (retryCount >= 1) return false

  const status = error.response?.status
  if (status && RETRYABLE_STATUS.has(status)) return true

  return !error.response || error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK'
}

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
  async (error) => {
    if (shouldRetryRequest(error)) {
      error.config.__retryCount = (error.config.__retryCount || 0) + 1
      await delay(450)
      return api(error.config)
    }

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
  extra_links: string[]
  industry: string
  peer_symbols: string[]
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
  urls: string[]
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
  extra_links?: string[]
  is_pending?: boolean
}

export interface ScreenerMeta {
  ready: boolean
  snapshot_date: string
  count: number
  industry_count: number
  roe_basis_label: string
}

export interface ScreenerResult {
  symbol: string
  name: string
  industry: string
  price: number
  market_cap: number
  pe: number
  pb: number
  dividend_yield: number
  roe_pct: number
  roi_pct: number
  net_cash_ratio: number
  cfo_yield: number
  fcf_yield: number
  is_monitored: boolean
}

export interface ScreenerQueryResponse {
  meta: ScreenerMeta
  filters: {
    q: string
    industry: string
    include_anomalies: boolean
    sort_by: string
    sort_order: string
  }
  results: ScreenerResult[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
}

export interface QualityHistoryItem {
  year: number
  roe: number
  net_margin: number
  gross_margin: number
  payout_ratio: number
  cfo: number
  fcf: number
  revenue_growth_pct: number
  [key: string]: number
}

export interface QualityAnalysis {
  symbol: string
  quality_history: QualityHistoryItem[]
  cashflow_summary: Record<string, any>
  capital_allocation_summary: Record<string, any>
  stability_summary: Record<string, any>
  balance_sheet_summary: Record<string, any>
  management_quality_summary: Record<string, any>
  shareholder_history: any[]
  shareholder_summary: Record<string, any>
}

// API functions
export const stockApi = {
  getStocks: () => api.get<Stock[]>('/stocks/'),
  createStock: (data: Partial<Stock>) => api.post<Stock>('/stocks/', data),
  updateStock: (symbol: string, data: Partial<Stock>) => api.patch<Stock>(`/stocks/${symbol}/`, data),
  deleteStock: (symbol: string) => api.delete(`/stocks/${symbol}/`),
  getTodaySentiment: () => api.get<SentimentData[]>('/sentiment/today/'),
  getLatestSentiment: (params?: Record<string, any>) => api.get<SentimentData[]>('/sentiment/latest/', { params }),
  getOverallSentimentTrend: (days: number = 7) => api.get<any[]>('/sentiment/overall_trend/', { params: { days } }),
  getSentimentBySymbol: (symbol: string) => api.get<SentimentData>(`/sentiment/${symbol}/`),
  triggerCollection: () => api.post<{ status: string, message: string }>('/collect/'),
  getRealtimePrices: () => api.get<Record<string, RealtimePrice>>('/sentiment/realtime_prices/'),
  getComparisonRealtime: (symbols: string[], type: 'last' | 'minute' = 'last', force: boolean = false) =>
    api.get<Record<string, RealtimePrice>>(
      `/sentiment/comparison_realtime/?symbols=${symbols.join(',')}&type=${type}${force ? '&force=1' : ''}`,
      { timeout: type === 'minute' ? 30000 : 15000 },
    ),
  getComparisonHistorical: (symbols: string[], limit: number = 30, period: string = 'day', force: boolean = false) =>
    api.get<Record<string, any[]>>(
      `/sentiment/comparison_historical/?symbols=${symbols.join(',')}&limit=${limit}&period=${period}${force ? '&skip_cache=1' : ''}`,
      { timeout: 60000 },
    ),
  searchStocks: (q: string) => api.get<any[]>('/sentiment/search/', { params: { q } }),
  getAnalysis: (symbol: string) => api.get<any>('/sentiment/analysis/', { params: { symbol }, timeout: 60000 }),
  getHistoryBacktest: (symbol: string) => api.get<any>(`/sentiment/history-backtest/?symbol=${symbol}`),
  getQualityAnalysis: (symbol: string, includeShareholder: boolean = true) =>
    api.get<QualityAnalysis>(
      `/sentiment/quality/?symbol=${symbol}&include_shareholder=${includeShareholder ? 1 : 0}`,
      { timeout: 45000 },
    ),
  getQualityShareholderStructure: (symbol: string) =>
    api.get<any>(`/sentiment/quality/shareholder-structure/?symbol=${symbol}`, { timeout: 45000 }),
  getScreenerResults: (params: Record<string, any>) =>
    api.get<ScreenerQueryResponse>('/sentiment/screener/', { params, timeout: 30000 }),
  refreshScreenerSnapshot: () =>
    api.post<any>(
      '/sentiment/screener/refresh/',
      {},
      { timeout: 15000 },
    ),
  pollScreenerRefresh: () =>
    api.get<any>('/sentiment/screener/refresh/', { params: { poll: 1 }, timeout: 10000 }),
  getMarketDiary: (symbol: string, force?: boolean) =>
    api.get<any>('/sentiment/market-diary/', { params: { symbol, ...(force ? { force: true } : {}) }, timeout: 30000 }),
  getDividendCalendar: () =>
    api.get<any[]>('/sentiment/dividend-calendar/', { timeout: 30000 }),
  getValuationThermometer: () =>
    api.get<any>('/sentiment/valuation-thermometer/', { timeout: 60000 }),
}

// 告警系统 API
export const alertApi = {
  /** 获取所有告警规则 */
  getRules: () => api.get<any[]>('/alerts/rules/'),

  /** 创建告警规则 */
  createRule: (data: { stock_symbol: string; rule_type: string; threshold: number; is_active?: boolean }) =>
    api.post<any>('/alerts/rules/create/', data),

  /** 删除告警规则 */
  deleteRule: (ruleId: number) => api.delete(`/alerts/rules/${ruleId}/delete/`),

  /** 启用/禁用告警规则 */
  toggleRule: (ruleId: number) => api.put(`/alerts/rules/${ruleId}/toggle/`),

  /** 获取告警日志 */
  getLogs: (limit: number = 50) => api.get<any[]>('/alerts/logs/', { params: { limit } }),

  /** 获取未读告警数量 */
  getUnreadCount: () => api.get<{ count: number }>('/alerts/unread-count/'),

  /** 标记单条告警为已读 */
  markRead: (alertId: number) => api.post(`/alerts/read/${alertId}/`),

  /** 标记所有告警为已读 */
  markAllRead: () => api.post('/alerts/read-all/'),

  /** 手动触发告警检查 */
  checkAlerts: () => api.post<any>('/alerts/check/'),

  /** 获取未读告警通知（供 Electron 轮询） */
  getNotifications: () => api.get<any[]>('/alerts/notifications/'),
}

// 组合持仓 API
export const portfolioApi = {
  /** 获取默认组合 */
  getPortfolio: () => api.get<any>('/portfolio/'),

  /** 保存组合 */
  savePortfolio: (data: { total_capital: number; holdings: any[] }) =>
    api.post<any>('/portfolio/save/', data),
}

export default api

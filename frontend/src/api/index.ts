import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
  triggerCollection: () => api.post<{status: string, message: string}>('/collect/'),
  getRealtimePrices: () => api.get<Record<string, RealtimePrice>>('/sentiment/realtime_prices/'),
  getComparisonRealtime: (symbols: string[], type: 'last' | 'minute' = 'last') => 
    api.get<Record<string, any>>(`/sentiment/comparison_realtime/?symbols=${symbols.join(',')}&type=${type}`),
  getComparisonHistorical: (symbols: string[], limit: number = 30, period: string = 'day') => 
    api.get<Record<string, any[]>>(`/sentiment/comparison_historical/?symbols=${symbols.join(',')}&limit=${limit}&period=${period}`),
  searchStocks: (q: string) => api.get<any[]>('/sentiment/search/', { params: { q } }),
}

export default api

import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue')
    },
    {
      path: '/stock/:symbol',
      name: 'stock-detail',
      component: () => import('@/views/StockDetailView.vue'),
      props: true
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/ComparisonView.vue')
    },
    {
      path: '/screener',
      name: 'screener',
      component: () => import('@/views/ScreenerView.vue')
    },
    {
      path: '/analysis/:symbol',
      name: 'analysis',
      component: () => import('@/views/AnalysisDetailView.vue'),
      props: true
    },
    {
      path: '/analysis/:symbol/history',
      name: 'history-backtest',
      component: () => import('@/views/HistoryBacktestView.vue'),
      props: true
    },
    {
      path: '/quality/:symbol',
      name: 'quality-analysis',
      component: () => import('@/views/QualityView.vue'),
      props: true
    }
  ]
})

export default router

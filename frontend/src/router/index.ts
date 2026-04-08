import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import StockDetailView from '@/views/StockDetailView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView
    },
    {
      path: '/stock/:symbol',
      name: 'stock-detail',
      component: StockDetailView,
      props: true
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/ComparisonView.vue')
    },
    {
      path: '/analysis/:symbol',
      name: 'analysis',
      component: () => import('@/views/AnalysisDetailView.vue'),
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

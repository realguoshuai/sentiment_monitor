<template>
  <section class="section chart-section">
    <div class="chart-layout">
      <div class="chart-main">
        <div class="section-header">
          <div>
            <p class="section-kicker">Relative Positioning</p>
            <h2>{{ getMetricLabel(activeMetric) }} 历史对比</h2>
            <p class="subtitle">10 年期月线叠加，先判断当前位置，再看是否进入安全区。</p>
          </div>

          <div class="chart-tabs">
            <button
              v-for="t in ['pe', 'pb', 'roi', 'dy']"
              :key="t"
              :class="{ active: activeMetric === t }"
              @click="activeMetric = t"
            >
              {{ t.toUpperCase() }}
            </button>
          </div>
        </div>
        <div ref="chartRef" class="analysis-chart"></div>
        <div class="chart-summary" v-if="!isMultiView">
          当前处于历史 <strong>{{ getPercentilePos(activeMetric) }}</strong> 分位
          <span v-if="isUnderValued" class="signal-buy">信号：绝对安全区</span>
        </div>

        <div class="chart-summary multi-summary" v-else>
          正在进行 <strong>{{ compareSymbols.length }}</strong> 家标的叠加对比
          <span v-if="loadingCompare" class="compare-loading-inline">
            <span class="inline-loader"></span>
            正在拉取新矩阵数据
          </span>
        </div>
      </div>

      <aside class="chart-sidebar">
        <article class="sidebar-card">
          <span class="mini-label">当前位置</span>
          <strong>{{ getPercentilePos(activeMetric) }}</strong>
          <p>{{ getMetricLabel(activeMetric) }} 当前值 {{ formatMetric(activePercentile?.current, activeMetric) }}</p>
        </article>

        <article class="sidebar-card" v-if="activePercentile">
          <span class="mini-label">历史坐标</span>
          <div class="metric-rows">
            <div class="metric-row">
              <span>P10</span>
              <strong>{{ formatMetric(activePercentile.p10, activeMetric) }}</strong>
            </div>
            <div class="metric-row">
              <span>P50</span>
              <strong>{{ formatMetric(activePercentile.p50, activeMetric) }}</strong>
            </div>
            <div class="metric-row">
              <span>P90</span>
              <strong>{{ formatMetric(activePercentile.p90, activeMetric) }}</strong>
            </div>
          </div>
        </article>

        <article class="sidebar-card accent-card" v-if="valuationConclusion && expectedReturn">
          <span class="mini-label">决策抓手</span>
          <strong>{{ valuationConclusion.summary }}</strong>
          <div class="metric-rows">
            <div class="metric-row">
              <span>安全边际</span>
              <strong>{{ formatPct(valuationConclusion.margin_of_safety.pct) }}</strong>
            </div>
            <div class="metric-row">
              <span>预期年化</span>
              <strong>{{ formatPct(expectedReturn.total_annual_return_pct) }}</strong>
            </div>
          </div>
        </article>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { echarts, type ECharts } from '@/lib/echarts'
import { useSentimentStore } from '@/stores/sentiment'

const props = defineProps<{
  analysisData: any
  compareSymbols: string[]
  compareDataMap: Record<string, any>
  loadingCompare: boolean
}>()

const sentimentStore = useSentimentStore()
const activeMetric = ref('pe')
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: ECharts | null = null

const mainPercentiles = computed(() => props.analysisData?.percentiles ?? null)
const activePercentile = computed(() => mainPercentiles.value?.[activeMetric.value] ?? null)
const valuationConclusion = computed(() => props.analysisData?.valuation_conclusion ?? null)
const expectedReturn = computed(() => valuationConclusion.value?.expected_return ?? null)
const isMultiView = computed(() => props.compareSymbols.length > 0)

const isUnderValued = computed(() => {
  const p = mainPercentiles.value?.[activeMetric.value]
  if (!p) return false
  if (activeMetric.value === 'dy') return p.current >= p.p90
  return p.current <= p.p10
})

const getMetricLabel = (metric: string) => ({ pe: 'PE', pb: 'PB', roi: 'ROI', dy: '股息率' }[metric] || metric.toUpperCase())

const getPercentilePos = (metric: string) => {
  const p = mainPercentiles.value?.[metric]
  if (!p) return '未知'
  if (metric === 'dy') {
    if (p.current >= p.p90) return '极高 (安全)'
    if (p.current <= p.p10) return '极低 (风险)'
  } else {
    if (p.current <= p.p10) return '极低 (安全)'
    if (p.current >= p.p90) return '极高 (风险)'
  }
  return '中性'
}

const formatMetric = (v?: number, metric = 'pe') => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  const digits = metric === 'dy' || metric === 'roi' ? 1 : 2
  const base = Number(v).toFixed(digits)
  return metric === 'dy' ? `${base}%` : base
}

const formatPct = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  return `${Number(v).toFixed(1)}%`
}

const getSymbolName = (s: string) => sentimentStore.getStockBySymbol(s)?.stock_name || s

const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

const initChart = () => {
  if (!chartRef.value || !props.analysisData) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)

  const metric = activeMetric.value
  const mainP = mainPercentiles.value?.[metric]
  const mainHistory = props.analysisData.history || []

  if (!mainP || mainHistory.length === 0) {
    chartInstance.clear()
    return
  }

  const series: any[] = []
  const mainName = getSymbolName(props.analysisData.symbol)
  const legendData: string[] = [mainName]

  series.push({
    name: mainName,
    type: 'line',
    data: mainHistory.map((h: any) => h[metric] || 0),
    smooth: true,
    showSymbol: false,
    lineStyle: { width: 3, color: colors[0] },
    zIndex: 10,
    markArea: isMultiView.value ? null : {
      silent: true,
      data: [
        [
          { yAxis: 0, itemStyle: { color: activeMetric.value === 'dy' ? 'rgba(248, 113, 113, 0.05)' : 'rgba(52, 211, 153, 0.1)' } },
          { yAxis: mainP.p10 || 0 }
        ],
        [
          { yAxis: mainP.p90 || 100, itemStyle: { color: activeMetric.value === 'dy' ? 'rgba(52, 211, 153, 0.1)' : 'rgba(248, 113, 113, 0.1)' } },
          { yAxis: 1000 }
        ]
      ]
    },
    markLine: isMultiView.value ? null : {
      symbol: 'none',
      data: [
        { yAxis: mainP.p50 || 0, label: { formatter: '50% 中位' }, lineStyle: { color: '#94a3b8', type: 'dashed' } }
      ]
    }
  })

  props.compareSymbols.forEach((s, idx) => {
    const d = props.compareDataMap[s]
    if (d && d.history) {
      const name = getSymbolName(s)
      legendData.push(name)
      series.push({
        name,
        type: 'line',
        data: d.history.map((h: any) => h[metric] || 0),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: colors[idx + 1], type: 'dashed', opacity: 0.8 }
      })
    }
  })

  const dates = mainHistory.map((h: any) => h.date)
  const allValues = series.flatMap(s => s.data)
  const maxY = Math.max(...allValues, mainP.p90) * 1.1

  const option = {
    backgroundColor: 'transparent',
    legend: { show: isMultiView.value, data: legendData, top: 0, right: 10, textStyle: { color: '#64748b' } },
    grid: { top: 50, right: 30, bottom: 40, left: 50 },
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255, 255, 255, 0.9)', borderColor: '#e2e8f0' },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
    yAxis: { type: 'value', max: maxY, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
    series
  }

  chartInstance.setOption(option, true)
}

const handleResize = () => chartInstance?.resize()

watch([() => props.compareDataMap, () => props.analysisData], () => {
  nextTick(initChart)
})

watch(activeMetric, () => {
  nextTick(initChart)
})

onMounted(() => {
  nextTick(initChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.section {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 8px 32px -12px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.03);
  margin-bottom: 24px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}
.section-header h2 {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px;
}
.subtitle {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  margin: 0;
}
.section-kicker, .mini-label {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
  margin: 0;
}
.chart-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(250px, 0.7fr);
  gap: 18px;
}
.chart-main {
  min-width: 0;
}
.chart-tabs {
  display: flex;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 10px;
}
.chart-tabs button {
  padding: 6px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 700;
  color: #64748b;
  transition: all 0.2s;
}
.chart-tabs button.active {
  background: white;
  color: #3b82f6;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.analysis-chart {
  height: 420px;
  margin: 10px 0;
}
.chart-summary {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
  text-align: right;
  font-size: 0.85rem;
  color: #64748b;
}
.multi-summary {
  text-align: center;
  font-weight: 700;
  color: #3b82f6;
}
.signal-buy {
  background: #10b981;
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  margin-left: 12px;
}
.chart-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
}
.sidebar-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 20px;
  padding: 18px;
}
.sidebar-card strong {
  display: block;
  margin-top: 10px;
  color: #0f172a;
  font-size: 1.2rem;
  font-weight: 900;
}
.sidebar-card p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 0.9rem;
  line-height: 1.6;
}
.accent-card {
  background: linear-gradient(180deg, #ecfeff 0%, #f8fafc 100%);
  border-color: #a5f3fc;
}
.metric-rows {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.metric-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.86rem;
  color: #475569;
}
.compare-loading-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: 16px;
  font-size: 0.75rem;
  color: #6366f1;
  font-weight: 700;
  animation: fadeIn 0.3s ease;
}
.inline-loader {
  width: 12px;
  height: 12px;
  border: 2px solid #e0e7ff;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-4px); }
  to { opacity: 1; transform: translateX(0); }
}
@media (max-width: 1180px) {
  .chart-layout {
    grid-template-columns: 1fr;
  }
}
</style>

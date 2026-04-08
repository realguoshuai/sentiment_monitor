<template>
  <div class="quality-view">
    <!-- Header Section -->
    <header class="page-header">
      <div class="stock-info" v-if="latestStats">
        <div class="title-row">
          <h1 class="stock-name">{{ stockName }} 财务溯源</h1>
          <span class="symbol-tag">{{ symbol }}</span>
        </div>
        <div class="badges">
          <div class="badge-item">
            <span class="label">最新 ROE</span>
            <span class="value">{{ latestStats.roe.toFixed(2) }}%</span>
          </div>
          <div class="badge-item">
            <span class="label">净利率</span>
            <span class="value">{{ latestStats.net_margin.toFixed(2) }}%</span>
          </div>
          <div class="badge-item">
            <span class="label">派息率</span>
            <span class="value">{{ latestStats.payout_ratio.toFixed(2) }}%</span>
          </div>
        </div>
      </div>
      <button @click="$router.back()" class="btn-back">返回</button>
    </header>

    <!-- Loading State -->
    <div v-if="loading" class="loading-overlay">
      <div class="loader-box">
        <div class="spinner"></div>
        <p>正在深度挖掘 10 年财务数据...</p>
      </div>
    </div>

    <!-- Main Content -->
    <main v-else class="content-grid">
      <!-- 1. DuPont Analysis -->
      <section class="chart-section dupont-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>杜邦 ROE 归因分析 (归一化趋势)</h2>
              <p class="subtitle">展示盈利质量来源：净利率、周转率与杠杆倍数</p>
            </div>
            <div ref="dupontChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>🤖 AI 分析视角</h3>
            <p><strong>看什么：</strong> ROE 的核心驱动力是什么？它揭示了企业赚钱的底层基因。</p>
            <ul>
              <li><strong>净利率主导：</strong> 卖得贵。产品溢价高，具有强品牌壁垒和定价权。</li>
              <li><strong>周转率主导：</strong> 卖得快。管理效率高，典型的“薄利多销”。</li>
              <li><strong>乘数主导：</strong> 借钱多。财务杠杆高，在行业下行期需警惕流动性风险。</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- 2. Moat Tracking -->
      <section class="chart-section moat-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>核心盈利护城河 (毛花 vs 净花)</h2>
              <p class="subtitle">毛利与净利空间决定了企业的真实价格支配能力</p>
            </div>
            <div ref="moatChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>🤖 AI 分析视角</h3>
            <p><strong>看什么：</strong> 毛利与净利的“剪刀差”稳定度。</p>
            <ul>
              <li><strong>宽且稳定的剪刀差：</strong> 典型的竞争壁垒，企业具备极强的独立定价权，能将成本转嫁给下游。</li>
              <li><strong>剪刀差收窄/剧烈波动：</strong> 面临上游原材料涨价挤压，或下游激烈价格战消耗。</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- 3. Shareholder Yield -->
      <section class="chart-section payout-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>股东回馈矩阵 (EPS vs DPS)</h2>
              <p class="subtitle">利润分配政策：分红连续性与派息健康度</p>
            </div>
            <div ref="payoutChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>🤖 AI 分析视角</h3>
            <p><strong>看什么：</strong> 企业赚的钱分了多少给股东？核心看派息率。</p>
            <ul>
              <li><strong>30%-70% 派息率：</strong> 稳健派息，成熟期成熟企业的健康标配。</li>
              <li><strong>> 100% 派息率：</strong> 透支式分红，可能是大股东套现或特别分红，需查阅资产负债表健康度，通常不可持续。</li>
            </ul>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { stockApi } from '@/api'
import * as echarts from 'echarts'
import { useSentimentStore } from '@/stores/sentiment'

const route = useRoute()
const sentimentStore = useSentimentStore()
const symbol = route.params.symbol as string
const loading = ref(true)
const qualityData = ref<any[]>([])

const dupontChartRef = ref<HTMLElement | null>(null)
const moatChartRef = ref<HTMLElement | null>(null)
const payoutChartRef = ref<HTMLElement | null>(null)

let dupontChart: echarts.ECharts | null = null
let moatChart: echarts.ECharts | null = null
let payoutChart: echarts.ECharts | null = null

const stockName = computed(() => {
  const stock = sentimentStore.sentimentData.find(s => s.stock_symbol === symbol)
  return stock ? stock.stock_name : symbol
})

const latestStats = computed(() => {
  if (qualityData.value.length === 0) return null
  return qualityData.value[qualityData.value.length - 1]
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await stockApi.getQualityAnalysis(symbol)
    qualityData.value = res.data.quality_history || []
    // Wait for DOM
    setTimeout(() => {
      initCharts()
    }, 100)
  } catch (err) {
    console.error('Failed to fetch quality data:', err)
  } finally {
    loading.value = false
  }
}

const initCharts = () => {
  const data = qualityData.value
  const years = data.map(d => d.year)

  // 1. DuPont Analysis Chart (Stacked Area)
  if (dupontChartRef.value) {
    dupontChart = echarts.init(dupontChartRef.value)
    dupontChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { 
        trigger: 'axis',
        valueFormatter: (value: any) => Number(value).toFixed(2)
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 30, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      series: [
        {
          name: '净利率因子',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(d => d.net_margin),
          color: '#3b82f6'
        },
        {
          name: '周转率因子',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(d => d.asset_turnover * 10), // Scale for visual
          color: '#10b981'
        },
        {
          name: '权益乘数因子',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(d => d.equity_multiplier),
          color: '#f59e0b'
        },
        {
          name: 'ROE (实际)',
          type: 'line',
          data: data.map(d => d.roe),
          lineStyle: { width: 4, type: 'dotted' },
          color: '#ef4444'
        }
      ]
    })
  }

  // 2. Moat Chart (Gross vs Net Margin)
  if (moatChartRef.value) {
    moatChart = echarts.init(moatChartRef.value)
    moatChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { 
        trigger: 'axis',
        valueFormatter: (value: any) => Number(value).toFixed(2)
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 30, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
      series: [
        {
          name: '毛利率',
          type: 'line',
          smooth: true,
          data: data.map(d => d.gross_margin),
          lineStyle: { width: 3 },
          color: '#6366f1'
        },
        {
          name: '净利率',
          type: 'line',
          smooth: true,
          data: data.map(d => d.net_margin),
          lineStyle: { width: 3 },
          color: '#10b981'
        }
      ]
    })
  }

  // 3. Payout Chart (EPS/DPS Bar + Ratio Line)
  if (payoutChartRef.value) {
    payoutChart = echarts.init(payoutChartRef.value)
    payoutChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { 
        trigger: 'axis',
        valueFormatter: (value: any) => Number(value).toFixed(2)
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 50, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        { type: 'value', name: '金额', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
        { type: 'value', name: '派息率(%)', axisLabel: { color: '#94a3b8' }, splitLine: { show: false } }
      ],
      series: [
        {
          name: '每股收益 (EPS)',
          type: 'bar',
          data: data.map(d => d.BASIC_EPS),
          color: '#94a3b8'
        },
        {
          name: '每股分红 (DPS)',
          type: 'bar',
          data: data.map(d => d.dps),
          color: '#3b82f6'
        },
        {
          name: '派息比例',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(d => d.payout_ratio),
          lineStyle: { width: 3 },
          color: '#ef4444'
        }
      ]
    })
  }
}

const handleResize = () => {
  dupontChart?.resize()
  moatChart?.resize()
  payoutChart?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.quality-view {
  padding: 24px;
  min-height: 100vh;
  background: #f8fafc;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
}

.title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.stock-name {
  font-size: 2rem;
  font-weight: 800;
  color: #1e293b;
  margin: 0;
}

.symbol-tag {
  font-size: 1.1rem;
  color: #64748b;
  font-family: monospace;
}

.badges {
  display: flex;
  gap: 24px;
}

.badge-item {
  display: flex;
  flex-direction: column;
}

.badge-item .label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-item .value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #3b82f6;
}

.btn-back {
  padding: 8px 20px;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-back:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.loading-overlay {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.loader-box {
  text-align: center;
  color: #64748b;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f1f5f9;
  border-top-color: #3b82f6;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.dupont-section {
  grid-column: span 2;
}

.card {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid #f1f5f9;
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.section-header {
  margin-bottom: 20px;
}

.section-header h2 {
  font-size: 1.25rem;
  font-weight: 800;
  color: #1e293b;
  margin: 0 0 4px 0;
}

.subtitle {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

.chart-container {
  height: 400px;
}

.card-content {
  display: flex;
  gap: 24px;
}

.chart-area {
  flex: 7;
  min-width: 0;
}

.insight-area {
  flex: 3;
  background: #f1f5f9;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.insight-area h3 {
  color: #3b82f6;
  font-size: 1.1rem;
  margin-top: 0;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.insight-area p {
  color: #475569;
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: 12px;
}

.insight-area ul {
  padding-left: 20px;
  margin: 0;
  color: #475569;
  font-size: 0.9rem;
  line-height: 1.6;
}

.insight-area li {
  margin-bottom: 8px;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  .dupont-section {
    grid-column: span 1;
  }
  .card-content {
    flex-direction: column;
  }
}
</style>

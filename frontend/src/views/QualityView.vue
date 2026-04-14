<template>
  <div class="quality-view">
    <header class="page-header">
      <div v-if="latestStats" class="stock-info">
        <div class="title-row">
          <h1 class="stock-name">{{ stockName }} 财务溯源</h1>
          <span class="symbol-tag">{{ symbol }}</span>
        </div>
        <div class="badges">
          <div class="badge-item" @mouseenter="showTooltip($event, 'roe')" @mouseleave="hideTooltip">
            <span class="label">最新 ROE <i class="info-icon">i</i></span>
            <span class="value">{{ latestStats.roe.toFixed(2) }}%</span>
          </div>
          <div class="badge-item" @mouseenter="showTooltip($event, 'net_margin')" @mouseleave="hideTooltip">
            <span class="label">净利率 <i class="info-icon">i</i></span>
            <span class="value">{{ latestStats.net_margin.toFixed(2) }}%</span>
          </div>
          <div class="badge-item" @mouseenter="showTooltip($event, 'payout_ratio')" @mouseleave="hideTooltip">
            <span class="label">派息率 <i class="info-icon">i</i></span>
            <span class="value">{{ latestStats.payout_ratio.toFixed(2) }}%</span>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <div class="refresh-box" :class="{ 'is-refreshing': isRefreshing }" @click="handleRefresh">
          <i class="refresh-icon">↻</i>
          <span>{{ isRefreshing ? '刷新中...' : '强制刷新' }}</span>
        </div>
        <button @click="$router.back()" class="btn-back">返回</button>
      </div>
    </header>

    <div v-if="loading" class="loading-overlay">
      <div class="loader-box">
        <div class="spinner"></div>
        <p>正在深度挖掘 10 年财务数据...</p>
      </div>
    </div>

    <main v-else class="content-grid">
      <section v-if="cashflowSummary" class="summary-strip card">
        <div class="summary-card" @mouseenter="showTooltip($event, 'cfo_to_profit')" @mouseleave="hideTooltip">
          <span class="summary-label">CFO / 净利润 <i class="info-icon-mini">i</i></span>
          <strong>{{ cashflowSummary.latest_cfo_to_profit_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'fcf_to_profit')" @mouseleave="hideTooltip">
          <span class="summary-label">FCF / 净利润 <i class="info-icon-mini">i</i></span>
          <strong>{{ cashflowSummary.latest_fcf_to_profit_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'fcf_yield')" @mouseleave="hideTooltip">
          <span class="summary-label">FCF 收益率 <i class="info-icon-mini">i</i></span>
          <strong>{{ cashflowSummary.latest_fcf_yield_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'capex_intensity')" @mouseleave="hideTooltip">
          <span class="summary-label">资本开支强度 <i class="info-icon-mini">i</i></span>
          <strong>{{ cashflowSummary.latest_capex_intensity_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card">
          <span class="summary-label">现金流质量</span>
          <strong>{{ cashflowSummary.cashflow_quality_label }}</strong>
        </div>
      </section>

      <section v-if="capitalAllocationSummary" class="summary-strip summary-strip-secondary card">
        <div class="summary-card" @mouseenter="showTooltip($event, 'roic_proxy')" @mouseleave="hideTooltip">
          <span class="summary-label">ROIC 代理 <i class="info-icon-mini">i</i></span>
          <strong>{{ capitalAllocationSummary.latest_roic_proxy_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'reinvestment_rate')" @mouseleave="hideTooltip">
          <span class="summary-label">再投资率 <i class="info-icon-mini">i</i></span>
          <strong>{{ capitalAllocationSummary.latest_reinvestment_rate_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'bvps_growth')" @mouseleave="hideTooltip">
          <span class="summary-label">BVPS 增长 <i class="info-icon-mini">i</i></span>
          <strong>{{ capitalAllocationSummary.latest_book_value_per_share_growth_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'share_change')" @mouseleave="hideTooltip">
          <span class="summary-label">股本变动 <i class="info-icon-mini">i</i></span>
          <strong>{{ capitalAllocationSummary.latest_share_change_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card">
          <span class="summary-label">资本配置</span>
          <strong>{{ capitalAllocationSummary.capital_allocation_label }}</strong>
          <span class="summary-meta">{{ capitalAllocationSummary.financing_signal }}</span>
        </div>
      </section>

      <section v-if="stabilitySummary" class="summary-strip summary-strip-tertiary card">
        <div class="summary-card" @mouseenter="showTooltip($event, 'gross_margin_vol')" @mouseleave="hideTooltip">
          <span class="summary-label">毛利率波动 <i class="info-icon-mini">i</i></span>
          <strong>{{ stabilitySummary.gross_margin_volatility_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'roe_vol')" @mouseleave="hideTooltip">
          <span class="summary-label">ROE 波动 <i class="info-icon-mini">i</i></span>
          <strong>{{ stabilitySummary.roe_volatility_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card" @mouseenter="showTooltip($event, 'roic_vol')" @mouseleave="hideTooltip">
          <span class="summary-label">ROIC 波动 <i class="info-icon-mini">i</i></span>
          <strong>{{ stabilitySummary.roic_proxy_volatility_pct.toFixed(1) }}%</strong>
        </div>
        <div class="summary-card">
          <span class="summary-label">周期性</span>
          <strong>{{ stabilitySummary.cyclical_label }}</strong>
        </div>
        <div class="summary-card">
          <span class="summary-label">经营稳定性</span>
          <strong>{{ stabilitySummary.operating_stability_label }}</strong>
          <span class="summary-meta">{{ stabilitySummary.moat_label }}</span>
        </div>
      </section>

      <section class="chart-section dupont-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>杜邦 ROE 归因分析</h2>
              <p class="subtitle">拆开净利率、周转率与杠杆，看到 ROE 的真实驱动因子。</p>
            </div>
            <div ref="dupontChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>AI 视角</h3>
            <p><strong>看什么：</strong> ROE 是靠经营效率、利润空间，还是靠财务杠杆撑起来。</p>
            <ul>
              <li><strong>净利率主导：</strong> 更像品牌力或产品力驱动，定价权通常更强。</li>
              <li><strong>周转率主导：</strong> 更像效率型公司，关键在运营和渠道能力。</li>
              <li><strong>杠杆主导：</strong> 需要留意行业下行期的资产负债表压力。</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="chart-section cashflow-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>现金流质量矩阵</h2>
              <p class="subtitle">用 CFO、FCF 和 Capex 看利润兑现能力，以及扩张是否过重。</p>
            </div>
            <div ref="cashflowChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>Cash Flow Lens</h3>
            <p><strong>看什么：</strong> 利润是否真正转成现金，扣掉资本开支后还剩下多少自由现金流。</p>
            <ul>
              <li><strong>CFO / 净利润长期高于 100%：</strong> 盈利兑现质量更强。</li>
              <li><strong>FCF / 净利润持续为正：</strong> 股东回报更容易持续，不容易靠外部融资续命。</li>
              <li><strong>Capex 强度快速抬升：</strong> 需要区分是高质量扩张还是被动维持。</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="chart-section moat-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>盈利护城河追踪</h2>
              <p class="subtitle">毛利率与净利率的稳定性，决定企业能否长期守住价格权。</p>
            </div>
            <div ref="moatChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>AI 视角</h3>
            <p><strong>看什么：</strong> 毛利率和净利率之间的剪刀差是否稳定。</p>
            <ul>
              <li><strong>宽且稳定：</strong> 通常意味着品牌、渠道或成本优势比较扎实。</li>
              <li><strong>快速收窄：</strong> 往往对应竞争加剧、原料涨价或费用率失控。</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="chart-section stability-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>经营稳定性与周期波动</h2>
              <p class="subtitle">用收入增速、ROE 和 ROIC 代理一起看企业是否具备跨周期稳定性。</p>
            </div>
            <div ref="stabilityChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>Stability Lens</h3>
            <p><strong>看什么：</strong> 如果收入增速大起大落，而回报率也跟着剧烈波动，通常说明公司更接近周期型盈利。</p>
            <ul>
              <li><strong>收入增速稳定：</strong> 需求更平滑，经营节奏和产能配置更容易预测。</li>
              <li><strong>ROE / ROIC 波动收敛：</strong> 资本回报更可复制，管理层执行力更容易验证。</li>
              <li><strong>收入和回报同向剧烈摆动：</strong> 要警惕景气周期、原料价格或库存周期主导。</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="chart-section payout-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>股东回馈矩阵</h2>
              <p class="subtitle">把 EPS、DPS 和派息率放在一起，看管理层如何分配利润。</p>
            </div>
            <div ref="payoutChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>AI 视角</h3>
            <p><strong>看什么：</strong> 企业赚到的钱，是更多留在体内复投，还是更多分给股东。</p>
            <ul>
              <li><strong>30% - 70% 派息率：</strong> 常见于比较稳健的成熟企业。</li>
              <li><strong>超过 100%：</strong> 往往意味着特殊分红、透支分配或周期错配，需要额外核实。</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="chart-section capital-allocation-section card">
        <div class="card-content">
          <div class="chart-area">
            <div class="section-header">
              <h2>资本配置与每股价值跟踪</h2>
              <p class="subtitle">把留存、复投、股本变化和每股净资产放在同一张图里看。</p>
            </div>
            <div ref="capitalAllocationChartRef" class="chart-container"></div>
          </div>
          <div class="insight-area">
            <h3>Capital Allocation</h3>
            <p><strong>看什么：</strong> 管理层把利润留在体内之后，是否真的变成了更高的每股价值。</p>
            <ul>
              <li><strong>ROIC 代理和 BVPS 增长同向上：</strong> 说明留存资本大概率在创造价值。</li>
              <li><strong>股本持续摊薄：</strong> 需要警惕再融资或股权支付吃掉单股收益。</li>
              <li><strong>高留存但低回报：</strong> 说明钱留在公司里了，但未必被高效利用。</li>
            </ul>
          </div>
        </div>
      </section>
    </main>

    <!-- Premium Glassmorphism Tooltip -->
    <transition name="fade">
      <div v-if="tooltip.visible" class="premium-tooltip" :style="tooltip.style">
        <div class="tooltip-header">
          <span class="tooltip-title">{{ tooltip.data.label }}</span>
        </div>
        <div class="tooltip-body">
          <div class="tooltip-row">
            <span class="row-label">计算：</span>
            <span class="row-value">{{ tooltip.data.calc }}</span>
          </div>
          <div class="tooltip-row">
            <span class="row-label">用途：</span>
            <span class="row-value">{{ tooltip.data.use }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useRoute } from 'vue-router'

import { stockApi } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'

const route = useRoute()
const sentimentStore = useSentimentStore()
const symbol = route.params.symbol as string
const loading = ref(true)
const isRefreshing = ref(false)
const qualityData = ref<any[]>([])
const cashflowSummary = ref<any | null>(null)
const capitalAllocationSummary = ref<any | null>(null)
const stabilitySummary = ref<any | null>(null)

const tooltip = ref({
  visible: false,
  style: {} as any,
  data: { label: '', calc: '', use: '' }
})

const metricDefs: Record<string, { label: string, calc: string, use: string }> = {
  roe: { label: 'ROE (净资产收益率)', calc: '归母净利润 / 平均净资产', use: '衡量核心资本效率。反映公司每投入 100 元自有资金能换回多少利润，是价值投资者的第一指标。' },
  net_margin: { label: '销售净利率', calc: '净利润 / 营业收入', use: '反映产品竞争力和成本控制力。高而稳定的净利率通常代表企业在产业链中拥有定价权。' },
  payout_ratio: { label: '分红率 (派息率)', calc: '当年分红总额 / 当年归母净利润', use: '反映赚到的钱有多少分给了股东。持续、高比例的分红通常意味着现金流真实且管理层重视股东回报。' },
  cfo_to_profit: { label: '净利含金量', calc: '经营活动现金流净额 / 净利润', use: '评估利润扣除应收/预收等账面项后的实收现金比例。长期 > 100% 说明利润极为真实。' },
  fcf_to_profit: { label: '自由现金流比率', calc: '自由现金流 (CFO-Capex) / 净利润', use: '衡量企业在维持当前规模后的提现能力。FCF 是股东回报的物理极限。' },
  fcf_yield: { label: 'FCF 收益率', calc: '自由现金流 / 当前总市值', use: '从现金流角度评估当前股价的便宜程度。高于 5-10% 通常意味着估值极具吸引力。' },
  capex_intensity: { label: '资本开支强度', calc: '购建资产劳务支出 / 营业收入', use: '衡量生意的“重度”。低强度（<5%）通常代表轻资产、容易扩张的生意。' },
  roic_proxy: { label: 'ROIC 代理 (投入资本回报)', calc: '净利润 / (净资产 + 有息负债)', use: '衡量包含债权在内的总投入效率。不受财务杠杆调节影响，真实反映经营护城河。' },
  reinvestment_rate: { label: '再投资率', calc: '资本开支 / 经营活动现金流', use: '反映赚来的钱必须拿回去复投的比例。越低代表自由度越高。' },
  bvps_growth: { label: '每股净资产增速', calc: '(本期BVPS / 上期BVPS) - 1', use: '复利成长的底层驱动力。长期增速若高于 Roe，说明有高溢价融资或低价回购。' },
  share_change: { label: '股本变动', calc: '(最新股本 / 初始股本) - 1', use: '由于增发或股权激励导致的股权摊薄。负值代表回购注销，对老股东有利。' },
  gross_margin_vol: { label: '毛利稳定性', calc: '过去10年毛利率的标准差', use: '波动越小，说明行业格局稳定或产品护城河深。大起大落往往对应深周期性。' },
  roe_vol: { label: '盈利连贯性', calc: '过去10年 ROE 的标准差', use: '衡量核心获利能力的波动。低波动意味着业绩可预测性强，更容易给高估值。' },
  roic_vol: { label: '回报稳定性', calc: '过去10年 ROIC 的标准差', use: '衡量投入资本整体回报的稳定性。核心看护城河是否能跨越行业周期。' }
}

const showTooltip = (event: MouseEvent, key: string) => {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const info = metricDefs[key]
  if (!info) return

  tooltip.value.data = info
  tooltip.value.style = {
    top: `${rect.bottom + window.scrollY + 10}px`,
    left: `${rect.left + window.scrollX}px`,
  }
  tooltip.value.visible = true
}

const hideTooltip = () => {
  tooltip.value.visible = false
}

const dupontChartRef = ref<HTMLElement | null>(null)
const cashflowChartRef = ref<HTMLElement | null>(null)
const moatChartRef = ref<HTMLElement | null>(null)
const stabilityChartRef = ref<HTMLElement | null>(null)
const payoutChartRef = ref<HTMLElement | null>(null)
const capitalAllocationChartRef = ref<HTMLElement | null>(null)

let dupontChart: echarts.ECharts | null = null
let cashflowChart: echarts.ECharts | null = null
let moatChart: echarts.ECharts | null = null
let stabilityChart: echarts.ECharts | null = null
let payoutChart: echarts.ECharts | null = null
let capitalAllocationChart: echarts.ECharts | null = null

const stockName = computed(() => {
  const stock = sentimentStore.sentimentData.find(item => item.stock_symbol === symbol)
  return stock ? stock.stock_name : symbol
})

const latestStats = computed(() => {
  if (qualityData.value.length === 0) return null
  return qualityData.value[qualityData.value.length - 1]
})

const disposeCharts = () => {
  dupontChart?.dispose()
  cashflowChart?.dispose()
  moatChart?.dispose()
  stabilityChart?.dispose()
  payoutChart?.dispose()
  capitalAllocationChart?.dispose()
  dupontChart = null
  cashflowChart = null
  moatChart = null
  stabilityChart = null
  payoutChart = null
  capitalAllocationChart = null
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await stockApi.getQualityAnalysis(symbol)
    qualityData.value = res.data.quality_history || []
    cashflowSummary.value = res.data.cashflow_summary || null
    capitalAllocationSummary.value = res.data.capital_allocation_summary || null
    stabilitySummary.value = res.data.stability_summary || null
    setTimeout(() => {
      initCharts()
    }, 100)
  } catch (err) {
    console.error('Failed to fetch quality data:', err)
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  if (isRefreshing.value) return
  
  if (!confirm('强制刷新将清理该股票的所有离线快照并重新爬取原始财报数据，可能耗时 5-10 秒。确定继续？')) {
    return
  }

  isRefreshing.value = true
  try {
    // 1. 调用后端清理接口
    await stockApi.refreshQualityAnalysis(symbol)
    
    // 2. 重新拉取数据 (触发全量冷启动抓取)
    await fetchData()
    
    // 提示成功 (如果有全局 message 组件可以调用)
    console.log('Cache purged and data re-fetched.')
  } catch (err) {
    console.error('Refresh failed:', err)
    alert('刷新失败，请检查网络或后端日志')
  } finally {
    isRefreshing.value = false
  }
}

const initCharts = () => {
  const data = qualityData.value
  const years = data.map(item => item.year)
  if (!years.length) return

  disposeCharts()

  if (dupontChartRef.value) {
    dupontChart = echarts.init(dupontChartRef.value)
    dupontChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 30, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
      },
      series: [
        {
          name: 'Net Margin',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(item => item.net_margin),
          color: '#3b82f6',
        },
        {
          name: 'Asset Turnover x10',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(item => item.asset_turnover * 10),
          color: '#10b981',
        },
        {
          name: 'Equity Multiplier',
          type: 'line',
          stack: 'Total',
          areaStyle: { opacity: 0.3 },
          emphasis: { focus: 'series' },
          data: data.map(item => item.equity_multiplier),
          color: '#f59e0b',
        },
        {
          name: 'ROE',
          type: 'line',
          data: data.map(item => item.roe),
          lineStyle: { width: 4, type: 'dotted' },
          color: '#ef4444',
        },
      ],
    })
  }

  if (cashflowChartRef.value) {
    cashflowChart = echarts.init(cashflowChartRef.value)
    cashflowChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 50, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        {
          type: 'value',
          name: 'Amount',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
        },
        {
          type: 'value',
          name: 'Ratio (%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'CFO',
          type: 'bar',
          data: data.map(item => item.cfo),
          color: '#0f766e',
        },
        {
          name: 'FCF',
          type: 'bar',
          data: data.map(item => item.fcf),
          color: '#2563eb',
        },
        {
          name: 'CFO / Profit',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.cfo_to_profit_pct),
          lineStyle: { width: 3 },
          color: '#f59e0b',
        },
        {
          name: 'FCF / Profit',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.fcf_to_profit_pct),
          lineStyle: { width: 3 },
          color: '#ef4444',
        },
        {
          name: 'Capex Intensity',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.capex_intensity_pct),
          lineStyle: { width: 2, type: 'dashed' },
          color: '#8b5cf6',
        },
      ],
    })
  }

  if (moatChartRef.value) {
    moatChart = echarts.init(moatChartRef.value)
    moatChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 30, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
      },
      series: [
        {
          name: 'Gross Margin',
          type: 'line',
          smooth: true,
          data: data.map(item => item.gross_margin),
          lineStyle: { width: 3 },
          color: '#6366f1',
        },
        {
          name: 'Net Margin',
          type: 'line',
          smooth: true,
          data: data.map(item => item.net_margin),
          lineStyle: { width: 3 },
          color: '#10b981',
        },
      ],
    })
  }

  if (stabilityChartRef.value) {
    stabilityChart = echarts.init(stabilityChartRef.value)
    stabilityChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 50, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        {
          type: 'value',
          name: 'Growth (%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
        },
        {
          type: 'value',
          name: 'Return (%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'Revenue Growth',
          type: 'bar',
          data: data.map(item => item.revenue_growth_pct),
          color: '#94a3b8',
        },
        {
          name: 'ROE',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.roe),
          lineStyle: { width: 3 },
          color: '#2563eb',
        },
        {
          name: 'ROIC Proxy',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.roic_proxy_pct),
          lineStyle: { width: 3 },
          color: '#f59e0b',
        },
      ],
    })
  }

  if (payoutChartRef.value) {
    payoutChart = echarts.init(payoutChartRef.value)
    payoutChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 50, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        {
          type: 'value',
          name: 'Per Share',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
        },
        {
          type: 'value',
          name: 'Payout (%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'EPS',
          type: 'bar',
          data: data.map(item => item.BASIC_EPS),
          color: '#94a3b8',
        },
        {
          name: 'DPS',
          type: 'bar',
          data: data.map(item => item.dps),
          color: '#3b82f6',
        },
        {
          name: 'Payout Ratio',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.payout_ratio),
          lineStyle: { width: 3 },
          color: '#ef4444',
        },
      ],
    })
  }

  if (capitalAllocationChartRef.value) {
    capitalAllocationChart = echarts.init(capitalAllocationChartRef.value)
    capitalAllocationChart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: number) => Number(value).toFixed(2),
      },
      legend: { bottom: 0, textStyle: { color: '#64748b' } },
      grid: { top: 40, left: 50, right: 50, bottom: 60 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        {
          type: 'value',
          name: 'BVPS',
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
        },
        {
          type: 'value',
          name: 'Ratio (%)',
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: 'BVPS',
          type: 'bar',
          data: data.map(item => item.book_value_per_share),
          color: '#0f766e',
        },
        {
          name: 'ROIC Proxy',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.roic_proxy_pct),
          lineStyle: { width: 3 },
          color: '#2563eb',
        },
        {
          name: 'Reinvestment Rate',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.reinvestment_rate_pct),
          lineStyle: { width: 3 },
          color: '#f59e0b',
        },
        {
          name: 'Retention Rate',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.retention_ratio_pct),
          lineStyle: { width: 2, type: 'dashed' },
          color: '#8b5cf6',
        },
        {
          name: 'Share Change',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.share_change_pct),
          lineStyle: { width: 2 },
          color: '#ef4444',
        },
      ],
    })
  }
}

const handleResize = () => {
  dupontChart?.resize()
  cashflowChart?.resize()
  moatChart?.resize()
  stabilityChart?.resize()
  payoutChart?.resize()
  capitalAllocationChart?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  disposeCharts()
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
  to {
    transform: rotate(360deg);
  }
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}

.summary-strip {
  grid-column: span 2;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border: 1px solid #dbeafe;
  border-radius: 18px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-label {
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}

.summary-card strong {
  font-size: 1.35rem;
  color: #0f172a;
  font-family: 'Monaco', monospace;
}

.summary-meta {
  font-size: 0.82rem;
  color: #64748b;
  font-weight: 600;
}

.dupont-section,
.cashflow-section,
.stability-section,
.capital-allocation-section {
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

  .summary-strip,
  .dupont-section,
  .cashflow-section,
  .stability-section,
  .capital-allocation-section {
    grid-column: span 1;
  }

  .summary-strip {
    grid-template-columns: 1fr;
  }

  .card-content {
    flex-direction: column;
  }
}

/* Tooltip Styles */
.info-icon, .info-icon-mini {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  border-radius: 50%;
  font-size: 10px;
  font-style: italic;
  font-weight: 800;
  margin-left: 6px;
  cursor: help;
  border: 1px solid rgba(59, 130, 246, 0.3);
  vertical-align: middle;
  transition: all 0.2s;
}

.info-icon:hover, .info-icon-mini:hover {
  background: #3b82f6;
  color: #fff;
}

.premium-tooltip {
  position: absolute;
  z-index: 1000;
  width: 280px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  pointer-events: none;
}

.tooltip-title {
  display: block;
  font-weight: 800;
  color: #1e293b;
  font-size: 0.95rem;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.tooltip-row {
  margin-bottom: 10px;
}

.tooltip-row:last-child {
  margin-bottom: 0;
}

.row-label {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 2px;
  font-weight: 600;
}

.row-value {
  display: block;
  font-size: 0.85rem;
  color: #334155;
  line-height: 1.5;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}

/* Refresh Button Styles */
.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.refresh-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.9rem;
  color: #64748b;
  font-weight: 500;
}

.refresh-box:hover {
  background: #fff;
  color: #3b82f6;
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.refresh-icon {
  font-size: 1.2rem;
  font-style: normal;
  display: inline-block;
  transition: transform 0.3s;
}

.is-refreshing {
  pointer-events: none;
  opacity: 0.7;
  color: #3b82f6;
}

.is-refreshing .refresh-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.btn-back {
  padding: 8px 24px;
  background: #1e293b;
  color: #fff;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-back:hover {
  background: #334155;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>

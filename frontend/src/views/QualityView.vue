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
        <button @click="$router.back()" class="btn-back">返回</button>
      </div>
    </header>

    <div v-if="loading" class="loading-overlay">
      <div class="loader-box">
        <div class="spinner"></div>
        <p>正在深度挖掘 10 年财务数据...</p>
        <div class="loading-quote">
          <p>“{{ loadingQuote.text }}”</p>
          <span>{{ loadingQuote.author }}</span>
        </div>
      </div>
    </div>

    <main v-else class="content-grid quality-layout">
      <section class="chart-section shareholder-section card chart-card feature-card wide-card">
        <div class="section-header feature-header">
          <div>
            <p class="section-kicker">Holder Structure</p>
            <h2>股价与股东人数对比</h2>
            <p class="subtitle">优先展示近 10 年窗口；图中仅保留股东户数与统计日股价。</p>
          </div>
          <div v-if="shareholderSummary?.holder_trend_label" class="feature-pill">{{ shareholderSummary.holder_trend_label }}</div>
          <div v-else-if="shareholderLoading" class="feature-pill feature-pill-muted">对齐中</div>
          <div v-else-if="shareholderError" class="feature-pill feature-pill-warning">加载失败</div>
          <div v-else class="feature-pill feature-pill-muted">暂无数据</div>
        </div>
        <div v-if="shareholderLoading && !shareholderHistory.length" class="deferred-card">
          <div class="deferred-spinner"></div>
          <p>正在同步股东人数统计口径…</p>
          <div class="deferred-quote">
            <p>“{{ loadingQuote.text }}”</p>
            <strong>{{ loadingQuote.author }}</strong>
          </div>
          <span>核心财务图表已优先加载，这块会随后补齐。</span>
        </div>
        <div v-else-if="!shareholderHistory.length" class="deferred-card deferred-card-empty">
          <p>{{ shareholderError || '暂未取到可用的股东人数历史，可能是源数据缺失或当前窗口没有可对齐记录。' }}</p>
          <span>下面的现金流、资本配置和稳定性分析已正常加载，不受影响。</span>
        </div>
        <template v-else>
          <div ref="shareholderChartRef" class="chart-container chart-container-feature"></div>
          <div class="insight-strip">
          <div class="insight-chip">
            <span>最后统计日</span>
            <strong>{{ latestShareholderDate }}</strong>
          </div>
          <div class="insight-chip">
            <span>统计日股价</span>
            <strong>{{ formatPrice(shareholderSummary?.latest_price) }}</strong>
          </div>
          <div class="insight-chip">
            <span>股东户数</span>
            <strong>{{ formatCount(shareholderSummary?.latest_holder_count) }}</strong>
          </div>
          <div class="insight-chip">
            <span>区间变化</span>
            <strong>{{ formatPct(shareholderSummary?.holder_count_change_pct) }}</strong>
          </div>
          </div>
        </template>
      </section>

      <section class="chart-section cashflow-section card feature-card">
        <div class="section-header feature-header">
          <div>
            <p class="section-kicker">Cash Flow</p>
            <h2>现金流质量矩阵</h2>
            <p class="subtitle">用 CFO、FCF 和 Capex 看利润有没有兑现成现金，以及扩张是否过重。</p>
          </div>
          <div v-if="cashflowSummary" class="feature-pill">{{ cashflowSummary.cashflow_quality_label }}</div>
        </div>
        <div ref="cashflowChartRef" class="chart-container chart-container-feature"></div>
        <div v-if="cashflowSummary" class="insight-strip">
          <div class="insight-chip" @mouseenter="showTooltip($event, 'cfo_to_profit')" @mouseleave="hideTooltip">
            <span>CFO / 净利润</span>
            <strong>{{ cashflowSummary.latest_cfo_to_profit_pct.toFixed(1) }}%</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'fcf_to_profit')" @mouseleave="hideTooltip">
            <span>FCF / 净利润</span>
            <strong>{{ cashflowSummary.latest_fcf_to_profit_pct.toFixed(1) }}%</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'fcf_yield')" @mouseleave="hideTooltip">
            <span>FCF 收益率</span>
            <strong>{{ cashflowSummary.latest_fcf_yield_pct.toFixed(1) }}%</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'capex_intensity')" @mouseleave="hideTooltip">
            <span>资本开支强度</span>
            <strong>{{ cashflowSummary.latest_capex_intensity_pct.toFixed(1) }}%</strong>
          </div>
        </div>
      </section>

      <aside class="signal-panel card">
        <section v-if="capitalAllocationSummary" class="signal-block">
          <div class="signal-block-head">
            <span class="section-kicker">Capital Allocation</span>
            <strong>{{ capitalAllocationSummary.capital_allocation_label }}</strong>
          </div>
          <div class="signal-grid">
            <div class="signal-card" @mouseenter="showTooltip($event, 'roic_proxy')" @mouseleave="hideTooltip">
              <span>ROIC 代理</span>
              <strong>{{ capitalAllocationSummary.latest_roic_proxy_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'reinvestment_rate')" @mouseleave="hideTooltip">
              <span>再投资率</span>
              <strong>{{ capitalAllocationSummary.latest_reinvestment_rate_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'bvps_growth')" @mouseleave="hideTooltip">
              <span>BVPS 增长</span>
              <strong>{{ capitalAllocationSummary.latest_book_value_per_share_growth_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'share_change')" @mouseleave="hideTooltip">
              <span>股本变动</span>
              <strong>{{ capitalAllocationSummary.latest_share_change_pct.toFixed(1) }}%</strong>
            </div>
          </div>
          <p class="signal-meta">{{ capitalAllocationSummary.financing_signal }}</p>
        </section>

        <section v-if="stabilitySummary" class="signal-block">
          <div class="signal-block-head">
            <span class="section-kicker">Operating Stability</span>
            <strong>{{ stabilitySummary.operating_stability_label }}</strong>
          </div>
          <div class="signal-grid">
            <div class="signal-card" @mouseenter="showTooltip($event, 'gross_margin_vol')" @mouseleave="hideTooltip">
              <span>毛利率波动</span>
              <strong>{{ stabilitySummary.gross_margin_volatility_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'roe_vol')" @mouseleave="hideTooltip">
              <span>ROE 波动</span>
              <strong>{{ stabilitySummary.roe_volatility_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'roic_vol')" @mouseleave="hideTooltip">
              <span>ROIC 波动</span>
              <strong>{{ stabilitySummary.roic_proxy_volatility_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card">
              <span>周期性</span>
              <strong>{{ stabilitySummary.cyclical_label }}</strong>
            </div>
          </div>
          <p class="signal-meta">{{ stabilitySummary.moat_label }}</p>
        </section>

        <section v-if="balanceSheetSummary" class="signal-block">
          <div class="signal-block-head">
            <span class="section-kicker">Balance Sheet</span>
            <strong>{{ balanceSheetSummary.balance_sheet_label }}</strong>
          </div>
          <div class="signal-grid">
            <div class="signal-card" @mouseenter="showTooltip($event, 'debt_to_equity')" @mouseleave="hideTooltip">
              <span>有息负债 / 净资产</span>
              <strong>{{ balanceSheetSummary.latest_debt_to_equity_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'short_debt_coverage')" @mouseleave="hideTooltip">
              <span>短债覆盖</span>
              <strong>{{ formatCoverage(balanceSheetSummary.latest_short_debt_coverage_pct, balanceSheetSummary.latest_short_debt) }}</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'asset_quality_ratio')" @mouseleave="hideTooltip">
              <span>营运资产 / 收入</span>
              <strong>{{ balanceSheetSummary.latest_receivable_inventory_prepay_to_revenue_pct.toFixed(1) }}%</strong>
            </div>
            <div class="signal-card" @mouseenter="showTooltip($event, 'goodwill_to_equity')" @mouseleave="hideTooltip">
              <span>商誉 / 净资产</span>
              <strong>{{ balanceSheetSummary.latest_goodwill_to_equity_pct.toFixed(1) }}%</strong>
            </div>
          </div>
          <p class="signal-meta">
            {{ balanceSheetSummary.liquidity_label }} / {{ balanceSheetSummary.asset_quality_label }} · {{ (balanceSheetSummary.risk_flags || []).join(' · ') }}
          </p>
        </section>

        <section v-if="shareholderSummary" class="signal-block">
          <div class="signal-block-head">
            <span class="section-kicker">Holder Snapshot</span>
            <strong>{{ shareholderSummary.holder_trend_label }}</strong>
          </div>
          <div class="signal-grid">
            <div class="signal-card">
              <span>股东户数</span>
              <strong>{{ formatCount(shareholderSummary.latest_holder_count) }}</strong>
            </div>
            <div class="signal-card">
              <span>区间变化</span>
              <strong>{{ formatPct(shareholderSummary.holder_count_change_pct) }}</strong>
            </div>
            <div class="signal-card">
              <span>户均持股</span>
              <strong>{{ formatCount(shareholderSummary.latest_avg_shares_per_holder) }}</strong>
            </div>
            <div class="signal-card">
              <span>观察窗口</span>
              <strong>{{ shareholderSummary.window_years }} 年</strong>
            </div>
          </div>
          <p class="signal-meta">
            {{ shareholderSummary.alignment_note }}
          </p>
        </section>
      </aside>

      <section class="chart-section dupont-section card chart-card">
        <div class="section-header">
          <div>
            <h2>杜邦 ROE 归因分析</h2>
            <p class="subtitle">拆开净利率、周转率与杠杆，先看 ROE 的来源，再判断质量。</p>
          </div>
        </div>
        <div ref="dupontChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>净利率主导</span><strong>更像定价权</strong></div>
          <div class="insight-chip"><span>周转率主导</span><strong>更像效率型</strong></div>
          <div class="insight-chip"><span>杠杆主导</span><strong>关注资产负债表</strong></div>
        </div>
      </section>

      <section class="chart-section moat-section card chart-card">
        <div class="section-header">
          <div>
            <h2>盈利护城河追踪</h2>
            <p class="subtitle">毛利率和净利率放在同一屏，直接看价格权是否稳定。</p>
          </div>
        </div>
        <div ref="moatChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>宽且稳定</span><strong>品牌或成本优势更扎实</strong></div>
          <div class="insight-chip"><span>快速收窄</span><strong>警惕竞争或费用失控</strong></div>
        </div>
      </section>

      <section class="chart-section stability-section card chart-card">
        <div class="section-header">
          <div>
            <h2>经营稳定性与周期波动</h2>
            <p class="subtitle">收入增速、ROE、ROIC 代理同屏，看是否具备跨周期稳定性。</p>
          </div>
        </div>
        <div ref="stabilityChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>收入稳定</span><strong>需求更平滑</strong></div>
          <div class="insight-chip"><span>回报收敛</span><strong>执行力更容易验证</strong></div>
          <div class="insight-chip"><span>同向大波动</span><strong>警惕周期主导</strong></div>
        </div>
      </section>

      <section class="chart-section payout-section card chart-card">
        <div class="section-header">
          <div>
            <h2>股东回馈矩阵</h2>
            <p class="subtitle">EPS、DPS 和派息率一起看，判断管理层是分红型还是复投型。</p>
          </div>
        </div>
        <div ref="payoutChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>30% - 70%</span><strong>常见于成熟企业</strong></div>
          <div class="insight-chip"><span>超过 100%</span><strong>需要核实分配可持续性</strong></div>
        </div>
      </section>

      <section class="chart-section balance-sheet-section card chart-card wide-card">
        <div class="section-header">
          <div>
            <h2>资产负债表风险透视</h2>
            <p class="subtitle">现金、负债和营运资产同屏看，先判断偿债缓冲，再看资产质量有没有拖累估值。</p>
          </div>
          <div v-if="balanceSheetSummary" class="feature-pill">{{ balanceSheetSummary.balance_sheet_label }}</div>
        </div>
        <div ref="balanceRiskChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>现金高于有息负债</span><strong>估值底通常更厚</strong></div>
          <div class="insight-chip"><span>短债覆盖低于 100%</span><strong>要盯融资续接能力</strong></div>
          <div class="insight-chip"><span>营运资产占收入抬升</span><strong>警惕回款和库存压力</strong></div>
        </div>
      </section>

      <section class="chart-section capital-allocation-section card chart-card wide-card">
        <div class="section-header">
          <div>
            <h2>资本配置与每股价值跟踪</h2>
            <p class="subtitle">留存、复投、股本变化和每股净资产合在一起，看单股价值是否真正提升。</p>
          </div>
        </div>
        <div ref="capitalAllocationChartRef" class="chart-container"></div>
        <div class="insight-strip">
          <div class="insight-chip"><span>ROIC 与 BVPS 同升</span><strong>留存资本更可能创造价值</strong></div>
          <div class="insight-chip"><span>股本持续摊薄</span><strong>注意融资或股权支付</strong></div>
          <div class="insight-chip"><span>高留存低回报</span><strong>钱留在公司但效率不高</strong></div>
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
import { echarts, type ECharts } from '@/lib/echarts'
import { useRoute } from 'vue-router'

import { stockApi } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'
import { useInvestorLoadingQuotes } from '@/composables/useInvestorLoadingQuotes'

const route = useRoute()
const sentimentStore = useSentimentStore()
const symbol = route.params.symbol as string
const loading = ref(true)
const shareholderLoading = ref(true)
const qualityData = ref<any[]>([])
const cashflowSummary = ref<any | null>(null)
const capitalAllocationSummary = ref<any | null>(null)
const stabilitySummary = ref<any | null>(null)
const balanceSheetSummary = ref<any | null>(null)
const shareholderHistory = ref<any[]>([])
const shareholderSummary = ref<any | null>(null)
const shareholderError = ref('')
const quoteLoadingActive = computed(() => loading.value || shareholderLoading.value)
const { loadingQuote } = useInvestorLoadingQuotes(quoteLoadingActive)

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
  debt_to_equity: { label: '有息负债 / 净资产', calc: '有息负债 / 归母净资产', use: '看财务杠杆是否已经抬高到需要警惕的水平。过高意味着景气回落时净资产回报会被债务成本吞噬。' },
  short_debt_coverage: { label: '短债覆盖率', calc: '货币资金 / 短期有息负债', use: '衡量短期偿债缓冲。低于 100% 时，企业更依赖滚动融资或经营现金流来覆盖到期债务。' },
  net_cash_to_equity: { label: '净现金 / 净资产', calc: '(货币资金 - 有息负债) / 归母净资产', use: '看企业是净现金体质还是净负债体质。净现金越高，估值下行时的底越厚。' },
  asset_quality_ratio: { label: '营运资产 / 收入', calc: '(应收 + 存货 + 预付款) / 营业收入', use: '看收入里有多少被压在应收、库存和预付款里。比例持续走高，通常意味着回款变慢、压货或经营弹性变差。' },
  goodwill_to_equity: { label: '商誉 / 净资产', calc: '商誉 / 归母净资产', use: '看并购形成的商誉是否已经高到足以影响净资产安全垫。商誉高企时，要警惕减值和并购质量。' },
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
const balanceRiskChartRef = ref<HTMLElement | null>(null)
const shareholderChartRef = ref<HTMLElement | null>(null)

let dupontChart: ECharts | null = null
let cashflowChart: ECharts | null = null
let moatChart: ECharts | null = null
let stabilityChart: ECharts | null = null
let payoutChart: ECharts | null = null
let capitalAllocationChart: ECharts | null = null
let balanceRiskChart: ECharts | null = null
let shareholderChart: ECharts | null = null

const stockName = computed(() => {
  const stock = sentimentStore.sentimentData.find(item => item.stock_symbol === symbol)
  return stock ? stock.stock_name : symbol
})

const latestStats = computed(() => {
  if (qualityData.value.length === 0) return null
  return qualityData.value[qualityData.value.length - 1]
})

const latestShareholderDate = computed(() => {
  if (!shareholderHistory.value.length) return '--'
  return shareholderHistory.value[shareholderHistory.value.length - 1]?.date || '--'
})

const formatPct = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  return `${Number(value).toFixed(1)}%`
}

const formatPrice = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(2)
}

const formatCount = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const formatAmount = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  const numeric = Number(value)
  const absValue = Math.abs(numeric)
  if (absValue >= 1e8) return `${(numeric / 1e8).toFixed(2)}亿`
  if (absValue >= 1e4) return `${(numeric / 1e4).toFixed(1)}万`
  return numeric.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const formatCompactNumber = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  const numeric = Number(value)
  const absValue = Math.abs(numeric)
  if (absValue >= 1e8) return `${(numeric / 1e8).toFixed(1)}亿`
  if (absValue >= 1e4) return `${(numeric / 1e4).toFixed(0)}万`
  if (absValue >= 1e3) return `${(numeric / 1e3).toFixed(0)}k`
  return `${Math.round(numeric)}`
}

const formatCoverage = (coverage?: number | null, shortDebt?: number | null) => {
  if ((shortDebt ?? 0) <= 0) return '无短债'
  return formatPct(coverage)
}

const toFiniteOrNull = (value: unknown) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const disposeCharts = () => {
  dupontChart?.dispose()
  cashflowChart?.dispose()
  moatChart?.dispose()
  stabilityChart?.dispose()
  payoutChart?.dispose()
  capitalAllocationChart?.dispose()
  balanceRiskChart?.dispose()
  shareholderChart?.dispose()
  dupontChart = null
  cashflowChart = null
  moatChart = null
  stabilityChart = null
  payoutChart = null
  capitalAllocationChart = null
  balanceRiskChart = null
  shareholderChart = null
}

const applyShareholderPayload = (payload: any) => {
  shareholderHistory.value = payload?.shareholder_history || []
  shareholderSummary.value = payload?.shareholder_summary || null
  setTimeout(() => {
    initCharts()
  }, 100)
}

const fetchData = async () => {
  loading.value = true
  shareholderLoading.value = true
  shareholderError.value = ''
  let coreLoaded = false
  try {
    const res = await stockApi.getQualityAnalysis(symbol, false)
    qualityData.value = res.data.quality_history || []
    cashflowSummary.value = res.data.cashflow_summary || null
    capitalAllocationSummary.value = res.data.capital_allocation_summary || null
    stabilitySummary.value = res.data.stability_summary || null
    balanceSheetSummary.value = res.data.balance_sheet_summary || null
    coreLoaded = true
    setTimeout(() => {
      initCharts()
    }, 100)
  } catch (err) {
    console.error('Failed to fetch quality data:', err)
  } finally {
    loading.value = false
  }

  if (coreLoaded) {
    void fetchShareholderStructure()
  } else {
    shareholderLoading.value = false
  }
}

const fetchShareholderStructure = async () => {
  shareholderLoading.value = true
  shareholderError.value = ''
  try {
    const res = await stockApi.getQualityShareholderStructure(symbol)
    applyShareholderPayload(res.data)
  } catch (err) {
    console.error('Failed to fetch shareholder structure endpoint, falling back to full quality payload:', err)
    try {
      const fallback = await stockApi.getQualityAnalysis(symbol, true)
      applyShareholderPayload(fallback.data)
      if (!shareholderHistory.value.length) {
        shareholderError.value = '股东结构数据暂无可用记录。'
      }
    } catch (fallbackErr) {
      shareholderHistory.value = []
      shareholderSummary.value = null
      shareholderError.value = '股东结构数据拉取失败，已保留核心财务视图。'
      console.error('Failed to fetch shareholder structure fallback payload:', fallbackErr)
    }
  } finally {
    shareholderLoading.value = false
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

  if (balanceRiskChartRef.value) {
    balanceRiskChart = echarts.init(balanceRiskChartRef.value)
    balanceRiskChart.setOption({
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
          name: 'Cash',
          type: 'bar',
          data: data.map(item => item.cash_balance),
          color: '#10b981',
        },
        {
          name: 'Interest Debt',
          type: 'bar',
          data: data.map(item => item.interest_bearing_debt),
          color: '#ef4444',
        },
        {
          name: 'Debt / Equity',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.debt_to_equity_pct),
          lineStyle: { width: 3 },
          color: '#2563eb',
        },
        {
          name: 'Short Debt Coverage',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.short_debt > 0 ? item.short_debt_coverage_pct : null),
          lineStyle: { width: 3 },
          color: '#f59e0b',
        },
        {
          name: 'Working Asset / Revenue',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.receivable_inventory_prepay_to_revenue_pct),
          lineStyle: { width: 2, type: 'dashed' },
          color: '#8b5cf6',
        },
        {
          name: 'Goodwill / Equity',
          type: 'line',
          yAxisIndex: 1,
          data: data.map(item => item.goodwill_to_equity_pct),
          lineStyle: { width: 2, type: 'dotted' },
          color: '#64748b',
        },
      ],
    })
  }

  if (shareholderChartRef.value && shareholderHistory.value.length) {
    const dates = shareholderHistory.value.map(item => item.date)
    const priceSeries = shareholderHistory.value.map(item => toFiniteOrNull(item.price))
    const holderSeries = shareholderHistory.value.map(item => toFiniteOrNull(item.holder_count))
    const tooltipFormatter = (params: any[]) => {
      const dataIndex = params?.[0]?.dataIndex ?? 0
      const point = shareholderHistory.value[dataIndex] || {}
      const lines = [
        `<div style="font-weight:800;margin-bottom:8px;">${point.date || '--'}</div>`,
        `<div style="color:#94a3b8;margin-bottom:8px;">股东统计日 ${point.date || '--'}</div>`,
      ]
      if (point.notice_date) {
        lines.push(`<div style="color:#94a3b8;margin-bottom:8px;">公告日 ${point.notice_date}</div>`)
      } else {
        lines.push('<div style="margin-bottom:8px;"></div>')
      }

      params.forEach((item: any) => {
        const value = item.value
        let formatted = '--'
        if (item.seriesName === '股价') formatted = formatPrice(value)
        if (item.seriesName === '股东户数') formatted = formatCount(value)
        lines.push(
          `<div style="display:flex;justify-content:space-between;gap:20px;margin:4px 0;">
            <span>${item.marker}${item.seriesName}</span>
            <strong>${formatted}</strong>
          </div>`
        )
      })

      return `<div style="min-width:220px;">${lines.join('')}</div>`
    }

    shareholderChart = echarts.init(shareholderChartRef.value)
    shareholderChart.setOption(
      {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          formatter: tooltipFormatter,
        },
        legend: { bottom: 0, textStyle: { color: '#64748b' } },
        grid: { top: 40, left: 50, right: 60, bottom: 60 },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { color: '#94a3b8' },
        },
        yAxis: [
          {
            type: 'value',
            name: '股价',
            axisLabel: { color: '#94a3b8' },
            splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
          },
          {
            type: 'value',
            name: '股东户数',
            axisLabel: { color: '#94a3b8', formatter: (value: number) => formatCompactNumber(value) },
            splitLine: { show: false },
          },
        ],
        series: [
          {
            name: '股价',
            type: 'line',
            smooth: true,
            data: priceSeries,
            lineStyle: { width: 3 },
            color: '#2563eb',
          },
          {
            name: '股东户数',
            type: 'line',
            yAxisIndex: 1,
            smooth: true,
            data: holderSeries,
            lineStyle: { width: 3 },
            color: '#f59e0b',
          },
        ],
      }
    )
  }
}

const handleResize = () => {
  dupontChart?.resize()
  cashflowChart?.resize()
  moatChart?.resize()
  stabilityChart?.resize()
  payoutChart?.resize()
  capitalAllocationChart?.resize()
  balanceRiskChart?.resize()
  shareholderChart?.resize()
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

.loading-quote {
  max-width: 420px;
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.22);
  text-align: center;
}

.loading-quote p {
  margin: 0;
  color: #0f172a;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.7;
}

.loading-quote span {
  display: block;
  margin-top: 8px;
  color: #0f766e;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 800;
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

.header-actions {
  display: flex;
  align-items: center;
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

.quality-view {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 24%),
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 20%),
    linear-gradient(180deg, #f8fbff 0%, #f1f5f9 100%);
}

.quality-layout {
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
  align-items: start;
}

.section-kicker {
  margin: 0 0 10px;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}

.feature-card,
.signal-panel,
.chart-card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 20px 40px -34px rgba(15, 23, 42, 0.3);
}

.feature-card {
  grid-column: span 1;
}

.feature-header {
  align-items: flex-start;
}

.feature-pill {
  padding: 8px 12px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #166534;
  font-size: 0.82rem;
  font-weight: 800;
  white-space: nowrap;
}

.feature-pill-muted {
  background: #e2e8f0;
  color: #475569;
}

.feature-pill-warning {
  background: #fff7ed;
  color: #c2410c;
}

.chart-container-feature {
  height: 500px;
}

.deferred-card {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px dashed #cbd5e1;
  color: #475569;
  text-align: center;
}

.deferred-card p {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 700;
  color: #0f172a;
}

.deferred-card span {
  font-size: 0.88rem;
  color: #64748b;
}

.deferred-quote {
  max-width: 480px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(240, 249, 255, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.deferred-quote p {
  margin: 0;
  color: #0f172a;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.7;
}

.deferred-quote strong {
  display: block;
  margin-top: 8px;
  color: #0f766e;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.deferred-card-empty {
  gap: 12px;
}

.deferred-card-empty p,
.deferred-card-empty span {
  max-width: 560px;
}

.deferred-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #dbeafe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.signal-panel {
  position: sticky;
  top: 24px;
  display: grid;
  gap: 14px;
}

.signal-block {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
}

.signal-block-head strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 1.05rem;
}

.signal-grid,
.insight-strip {
  display: grid;
  gap: 12px;
}

.signal-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.signal-card,
.insight-chip {
  padding: 14px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.signal-card span,
.insight-chip span {
  display: block;
  font-size: 0.76rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
}

.signal-card strong,
.insight-chip strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 1rem;
  font-weight: 900;
}

.signal-meta {
  margin: 12px 0 0;
  color: #64748b;
  font-size: 0.88rem;
  line-height: 1.6;
}

.chart-card {
  display: grid;
  gap: 16px;
}

.wide-card {
  grid-column: span 2;
}

.insight-strip {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

@media (max-width: 1180px) {
  .quality-layout {
    grid-template-columns: 1fr;
  }

  .signal-panel {
    position: static;
  }

  .wide-card {
    grid-column: span 1;
  }
}

@media (max-width: 720px) {
  .signal-grid,
  .insight-strip {
    grid-template-columns: 1fr;
  }

  .chart-container,
  .chart-container-feature {
    height: 340px;
  }
}
</style>

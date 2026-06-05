<template>
  <div class="light-page quality-view">
    <header class="light-hero-card">
      <div v-if="latestStats" class="stock-info">
        <p class="light-hero-kicker">Financial Tracing</p>
        <div class="hero-title-row">
          <h1 class="light-hero-title">{{ stockName }} 财务溯源</h1>
          <span class="light-symbol-chip">{{ symbol }}</span>
        </div>
        <p class="light-hero-subtitle">
          追溯 10 年核心财务指标，拆解盈利质量、现金流、资本配置与资产负债表风险。
        </p>
        <div class="badges">
          <InfoTooltip placement="bottom">
            <div class="badge-item">
              <span class="label">最新 ROE</span>
              <span class="value">{{ formatPct(latestStats.roe) }}</span>
            </div>
            <template #content>
              <strong>净资产收益率 (ROE)</strong><br/>
              <div class="formula">ROE = 归母净利润 ÷ 归母股东权益 × 100%</div>
              股东每投入 100 元能获得的利润<br/>
              <span class="threshold threshold-green">≥15%：优秀</span>
              <span class="threshold threshold-yellow">10~15%：良好</span>
              <span class="threshold threshold-red"><10%：一般</span>
            </template>
          </InfoTooltip>
          <InfoTooltip placement="bottom">
            <div class="badge-item">
              <span class="label">净利率</span>
              <span class="value">{{ formatPct(latestStats.net_margin) }}</span>
            </div>
            <template #content>
              <strong>净利率</strong><br/>
              <div class="formula">净利率 = 归母净利润 ÷ 营业总收入 × 100%</div>
              每 1 元收入能转化为多少净利润<br/>
              <span class="threshold threshold-green">≥20%：高毛利</span>
              <span class="threshold threshold-yellow">10~20%：中等</span>
              <span class="threshold threshold-red"><10%：低毛利</span>
            </template>
          </InfoTooltip>
          <InfoTooltip placement="bottom">
            <div class="badge-item">
              <span class="label">派息率</span>
              <span class="value">{{ formatPct(latestStats.payout_ratio) }}</span>
            </div>
            <template #content>
              <strong>派息率</strong><br/>
              <div class="formula">派息率 = 每股分红 ÷ 每股收益 × 100%</div>
              利润中有多少分给了股东<br/>
              <span class="threshold threshold-green">≥60%：高分红</span>
              <span class="threshold threshold-yellow">30~60%：中等</span>
              <span class="threshold threshold-red"><30%：低分红</span>
            </template>
          </InfoTooltip>
        </div>
      </div>
      <div class="header-actions">
        <button @click="$router.back()" class="light-btn-back">返回</button>
      </div>
    </header>

    <AlgorithmExplainer title="财务溯源算法说明" :defaultOpen="false">
      <h4>现金流质量标签</h4>
      <p>基于利润含金量和自由现金流判断：</p>
      <div class="formula">
        CFO/净利润 = 经营现金流 ÷ 归母净利润 × 100%<br/>
        FCF/净利润 = (经营现金流 - 资本开支) ÷ 归母净利润 × 100%
      </div>
      <div class="thresholds">
        <span class="threshold threshold-green">强：CFO≥100% 且 FCF≥60%</span>
        <span class="threshold threshold-yellow">中：CFO≥80% 且 FCF≥30%</span>
        <span class="threshold threshold-red">弱：低于上述标准</span>
      </div>

      <h4>ROIC 代理</h4>
      <p>衡量总投入资本的回报效率（简化版本，未剔除利息和税收）：</p>
      <div class="formula">
        投入资本 = 股东权益 + 有息负债 - 货币资金<br/>
        ROIC代理 = 归母净利润 ÷ 平均投入资本 × 100%
      </div>

      <h4>资本配置标签</h4>
      <ul>
        <li><strong>高质量复投</strong>：ROIC≥12% 且 BVPS 增速≥8% 且 股本变动≤1%</li>
        <li><strong>摊薄扩张</strong>：股本变动≥3% 且 BVPS 增速≤5%</li>
        <li><strong>分红兑现</strong>：派息率≥60% 且 BVPS 增速<8%</li>
        <li><strong>均衡配置</strong>：不满足以上任一条件</li>
      </ul>

      <h4>护城河强度</h4>
      <p>综合毛利率水平、波动率、ROIC-WACC 价差判断：</p>
      <div class="thresholds">
        <span class="threshold threshold-green">宽护城河：高毛利率+低波动+ROIC持续高于资本成本</span>
        <span class="threshold threshold-yellow">中等护城河：中等毛利率+可控波动</span>
        <span class="threshold threshold-gray">待验证：低于上述标准</span>
      </div>

      <h4>周期性标签</h4>
      <p>基于 4 项指标评分（各 1 分）：</p>
      <ul>
        <li>收入波动≥15% → +1 分</li>
        <li>负增长年份≥2 → +1 分</li>
        <li>ROE 波动≥8% → +1 分</li>
        <li>增速极差≥10% → +1 分</li>
      </ul>
      <div class="thresholds">
        <span class="threshold threshold-red">强周期：≥3 分</span>
        <span class="threshold threshold-yellow">中周期：2 分</span>
        <span class="threshold threshold-green">弱周期：≤1 分</span>
      </div>

      <h4>资产负债表风险</h4>
      <p>综合 4 项指标判断：</p>
      <div class="formula">
        有息负债/净资产 = (短期借款+长期借款+债券) ÷ 净资产<br/>
        短债覆盖率 = 货币资金 ÷ 短期有息负债<br/>
        营运资产占比 = (应收+存货+预付) ÷ 营业收入<br/>
        商誉占比 = 商誉 ÷ 净资产
      </div>
      <div class="thresholds">
        <span class="threshold threshold-green">低风险：负债率≤30% 且 覆盖率≥130% 且 营运≤35% 且 商誉≤10%</span>
        <span class="threshold threshold-yellow">中风险：负债率≤80% 且 覆盖率≥90% 且 营运≤55% 且 商誉≤25%</span>
        <span class="threshold threshold-red">高风险：超过上述任一阈值</span>
      </div>

      <h4>股东趋势</h4>
      <div class="thresholds">
        <span class="threshold threshold-green">筹码集中：近 10 年股东减少≥10%</span>
        <span class="threshold threshold-gray">基本稳定：变化 <10%</span>
        <span class="threshold threshold-red">筹码分散：近 10 年股东增加≥10%</span>
      </div>
    </AlgorithmExplainer>

    <div v-if="loading" class="loading-overlay">
      <div class="loader-box">
        <div class="spinner"></div>
        <p>正在追根溯源 10 年财务数据...</p>
        <div class="loading-quote">
          <p>"{{ loadingQuote.text }}"</p>
          <span>{{ loadingQuote.author }}</span>
        </div>
      </div>
    </div>

    <main v-else class="quality-main">
      <!-- 信号摘要横排 -->
      <div class="signal-strip">
        <div v-if="capitalAllocationSummary" class="signal-group">
          <div class="signal-group-head">
            <span>资本配置</span>
            <strong>{{ capitalAllocationSummary.capital_allocation_label }}</strong>
          </div>
          <div class="signal-items">
            <div class="signal-item" @mouseenter="showTooltip($event, 'roic_proxy')" @mouseleave="hideTooltip">
              <span>ROIC 代理</span><strong>{{ formatPct(capitalAllocationSummary.latest_roic_proxy_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'reinvestment_rate')" @mouseleave="hideTooltip">
              <span>再投资率</span><strong>{{ formatPct(capitalAllocationSummary.latest_reinvestment_rate_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'bvps_growth')" @mouseleave="hideTooltip">
              <span>BVPS 增长</span><strong>{{ formatPct(capitalAllocationSummary.latest_book_value_per_share_growth_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'share_change')" @mouseleave="hideTooltip">
              <span>股本变动</span><strong>{{ formatPct(capitalAllocationSummary.latest_share_change_pct) }}</strong>
            </div>
          </div>
        </div>

        <div v-if="stabilitySummary" class="signal-group">
          <div class="signal-group-head">
            <span>经营稳定性</span>
            <strong>{{ stabilitySummary.operating_stability_label }}</strong>
          </div>
          <div class="signal-items">
            <div class="signal-item" @mouseenter="showTooltip($event, 'gross_margin_vol')" @mouseleave="hideTooltip">
              <span>毛利率波动</span><strong>{{ formatPct(stabilitySummary.gross_margin_volatility_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'roe_vol')" @mouseleave="hideTooltip">
              <span>ROE 波动</span><strong>{{ formatPct(stabilitySummary.roe_volatility_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'roic_vol')" @mouseleave="hideTooltip">
              <span>ROIC 波动</span><strong>{{ formatPct(stabilitySummary.roic_proxy_volatility_pct) }}</strong>
            </div>
            <div class="signal-item">
              <span>周期性</span><strong>{{ stabilitySummary.cyclical_label }}</strong>
            </div>
          </div>
        </div>

        <div v-if="balanceSheetSummary" class="signal-group">
          <div class="signal-group-head">
            <span>资产负债表</span>
            <strong>{{ balanceSheetSummary.balance_sheet_label }}</strong>
          </div>
          <div class="signal-items">
            <div class="signal-item" @mouseenter="showTooltip($event, 'debt_to_equity')" @mouseleave="hideTooltip">
              <span>有息负债/净资产</span><strong>{{ formatPct(balanceSheetSummary.latest_debt_to_equity_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'short_debt_coverage')" @mouseleave="hideTooltip">
              <span>短债覆盖</span><strong>{{ formatCoverage(balanceSheetSummary.latest_short_debt_coverage_pct, balanceSheetSummary.latest_short_debt) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'asset_quality_ratio')" @mouseleave="hideTooltip">
              <span>营运资产/收入</span><strong>{{ formatPct(balanceSheetSummary.latest_receivable_inventory_prepay_to_revenue_pct) }}</strong>
            </div>
            <div class="signal-item" @mouseenter="showTooltip($event, 'goodwill_to_equity')" @mouseleave="hideTooltip">
              <span>商誉/净资产</span><strong>{{ formatPct(balanceSheetSummary.latest_goodwill_to_equity_pct) }}</strong>
            </div>
          </div>
        </div>

        <div v-if="shareholderSummary" class="signal-group">
          <div class="signal-group-head">
            <span>股东趋势</span>
            <strong>{{ shareholderSummary.holder_trend_label }}</strong>
          </div>
          <div class="signal-items">
            <div class="signal-item">
              <span>股东户数</span><strong>{{ formatCount(shareholderSummary.latest_holder_count) }}</strong>
            </div>
            <div class="signal-item">
              <span>区间变化</span><strong>{{ formatPct(shareholderSummary.holder_count_change_pct) }}</strong>
            </div>
            <div class="signal-item">
              <span>户均持股</span><strong>{{ formatCount(shareholderSummary.latest_avg_shares_per_holder) }}</strong>
            </div>
          </div>
        </div>

        <div v-if="managementQualitySummary" class="signal-group">
          <div class="signal-group-head">
            <span>管理层质量</span>
            <strong>{{ managementQualitySummary.capital_efficiency_label }}</strong>
          </div>
          <div class="signal-items">
            <div class="signal-item">
              <span>股本稀释</span><strong>{{ managementQualitySummary.share_dilution_trend }}</strong>
            </div>
            <div class="signal-item">
              <span>资本效率</span><strong>{{ managementQualitySummary.capital_efficiency_label }}</strong>
            </div>
            <div class="signal-item">
              <span>留存质量</span><strong>{{ managementQualitySummary.earnings_retention_quality }}</strong>
            </div>
          </div>
        </div>
      </div>

      <!-- 图表纵排 -->
      <section class="chart-section">
        <div class="section-header">
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
          <span>核心财务图表已优先加载，这块会随后补齐。</span>
        </div>
        <div v-else-if="!shareholderHistory.length" class="deferred-card deferred-card-empty">
          <p>{{ shareholderError || '暂未取到可用的股东人数历史。' }}</p>
        </div>
        <template v-else>
          <QualityShareholderChart :shareholderHistory="shareholderHistory" :stockName="stockName" />
          <div class="insight-strip">
            <div class="insight-chip"><span>最后统计日</span><strong>{{ latestShareholderDate }}</strong></div>
            <div class="insight-chip"><span>统计日股价</span><strong>{{ formatPrice(shareholderSummary?.latest_price) }}</strong></div>
            <div class="insight-chip"><span>股东户数</span><strong>{{ formatCount(shareholderSummary?.latest_holder_count) }}</strong></div>
            <div class="insight-chip"><span>区间变化</span><strong>{{ formatPct(shareholderSummary?.holder_count_change_pct) }}</strong></div>
          </div>
        </template>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <p class="section-kicker">Cash Flow</p>
            <h2>现金流质量矩阵</h2>
            <p class="subtitle">用 CFO、FCF 和 Capex 看利润有没有兑现成现金，以及扩张是否过重。</p>
          </div>
          <div v-if="cashflowSummary" class="feature-pill">{{ cashflowSummary.cashflow_quality_label }}</div>
        </div>
        <QualityCashflowChart :data="qualityData" />
        <div v-if="cashflowSummary" class="insight-strip">
          <div class="insight-chip" @mouseenter="showTooltip($event, 'cfo_to_profit')" @mouseleave="hideTooltip">
            <span>CFO / 净利润</span><strong>{{ formatPct(cashflowSummary.latest_cfo_to_profit_pct) }}</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'fcf_to_profit')" @mouseleave="hideTooltip">
            <span>FCF / 净利润</span><strong>{{ formatPct(cashflowSummary.latest_fcf_to_profit_pct) }}</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'fcf_yield')" @mouseleave="hideTooltip">
            <span>FCF 收益率</span><strong>{{ formatPct(cashflowSummary.latest_fcf_yield_pct) }}</strong>
          </div>
          <div class="insight-chip" @mouseenter="showTooltip($event, 'capex_intensity')" @mouseleave="hideTooltip">
            <span>资本开支强度</span><strong>{{ formatPct(cashflowSummary.latest_capex_intensity_pct) }}</strong>
          </div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>杜邦 ROE 归因分析</h2>
            <p class="subtitle">拆开净利率、周转率与杠杆，先看 ROE 的来源，再判断质量。</p>
          </div>
        </div>
        <QualityDupontChart :data="qualityData" />
        <div class="insight-strip">
          <div class="insight-chip"><span>净利率主导</span><strong>更像定价权</strong></div>
          <div class="insight-chip"><span>周转率主导</span><strong>更像效率型</strong></div>
          <div class="insight-chip"><span>杠杆主导</span><strong>关注资产负债表</strong></div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>盈利护城河追踪</h2>
            <p class="subtitle">毛利率和净利率放在同一屏，直接看价格权是否稳定。</p>
          </div>
        </div>
        <QualityMoatChart :data="qualityData" />
        <div class="insight-strip">
          <div class="insight-chip"><span>宽且稳定</span><strong>品牌或成本优势更扎实</strong></div>
          <div class="insight-chip"><span>快速收窄</span><strong>警惕竞争或费用失控</strong></div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>经营稳定性与周期波动</h2>
            <p class="subtitle">收入增速、ROE、ROIC 代理同屏，看是否具备跨周期稳定性。</p>
          </div>
        </div>
        <QualityStabilityChart :data="qualityData" />
        <div class="insight-strip">
          <div class="insight-chip"><span>收入稳定</span><strong>需求更平滑</strong></div>
          <div class="insight-chip"><span>回报收敛</span><strong>执行力更容易验证</strong></div>
          <div class="insight-chip"><span>同向大波动</span><strong>警惕周期主导</strong></div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>股东回馈矩阵</h2>
            <p class="subtitle">EPS、DPS 和派息率一起看，判断管理层是分红型还是复投型。</p>
          </div>
        </div>
        <QualityPayoutChart :data="qualityData" />
        <div class="insight-strip">
          <div class="insight-chip"><span>30% - 70%</span><strong>常见于成熟企业</strong></div>
          <div class="insight-chip"><span>超过 100%</span><strong>需要核实分配可持续性</strong></div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>资产负债表风险透视</h2>
            <p class="subtitle">现金、负债和营运资产同屏看，先判断偿债缓冲，再看资产质量有没有拖累估值。</p>
          </div>
          <div v-if="balanceSheetSummary" class="feature-pill">{{ balanceSheetSummary.balance_sheet_label }}</div>
        </div>
        <QualityBalanceRiskChart :data="qualityData" />
        <div class="insight-strip">
          <div class="insight-chip"><span>现金高于有息负债</span><strong>估值底通常更厚</strong></div>
          <div class="insight-chip"><span>短债覆盖低于 100%</span><strong>要盯融资续接能力</strong></div>
          <div class="insight-chip"><span>营运资产占收入抬升</span><strong>警惕回款和库存压力</strong></div>
        </div>
      </section>

      <section class="chart-section">
        <div class="section-header">
          <div>
            <h2>资本配置与每股价值跟踪</h2>
            <p class="subtitle">留存、复投、股本变化和每股净资产合在一起，看单股价值是否真正提升。</p>
          </div>
        </div>
        <QualityCapitalAllocationChart :data="qualityData" />
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
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { stockApi } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'
import { useInvestorLoadingQuotes } from '@/composables/useInvestorLoadingQuotes'
import { metricDefs } from '@/lib/metricDefs'

import QualityBalanceRiskChart from '@/components/QualityBalanceRiskChart.vue'
import QualityCapitalAllocationChart from '@/components/QualityCapitalAllocationChart.vue'
import QualityCashflowChart from '@/components/QualityCashflowChart.vue'
import QualityDupontChart from '@/components/QualityDupontChart.vue'
import QualityMoatChart from '@/components/QualityMoatChart.vue'
import QualityPayoutChart from '@/components/QualityPayoutChart.vue'
import QualityShareholderChart from '@/components/QualityShareholderChart.vue'
import QualityStabilityChart from '@/components/QualityStabilityChart.vue'
import AlgorithmExplainer from '@/components/AlgorithmExplainer.vue'

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
const managementQualitySummary = ref<any | null>(null)
const shareholderError = ref('')
const quoteLoadingActive = computed(() => loading.value || shareholderLoading.value)
const { loadingQuote } = useInvestorLoadingQuotes(quoteLoadingActive)

const tooltip = ref({
  visible: false,
  style: {} as any,
  data: { label: '', calc: '', use: '' }
})

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

const stockName = computed(() => {
  return sentimentStore.getStockBySymbol(symbol)?.stock_name || symbol
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

const formatCoverage = (coverage?: number | null, shortDebt?: number | null) => {
  if ((shortDebt ?? 0) <= 0) return '无短债'
  return formatPct(coverage)
}

const applyShareholderPayload = (payload: any) => {
  shareholderHistory.value = payload?.shareholder_history || []
  shareholderSummary.value = payload?.shareholder_summary || null
}

const fetchData = async () => {
  loading.value = true
  shareholderLoading.value = true
  shareholderError.value = ''
  try {
    const data = await sentimentStore.getQuality(symbol)
    applyQualityPayload(data)
    if (data.cache_status === 'stale') {
      void sentimentStore.getQuality(symbol, true).then(res => applyQualityPayload(res))
    }
  } catch (err) {
    console.error('Failed to fetch quality data:', err)
  } finally {
    loading.value = false
  }
  void fetchShareholderStructure()
}

const applyQualityPayload = (data: any) => {
  qualityData.value = data.quality_history || []
  cashflowSummary.value = data.cashflow_summary || null
  capitalAllocationSummary.value = data.capital_allocation_summary || null
  stabilitySummary.value = data.stability_summary || null
  balanceSheetSummary.value = data.balance_sheet_summary || null
  managementQualitySummary.value = data.management_quality_summary || null
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

onMounted(async () => {
  if (!sentimentStore.stocks.length) {
    await sentimentStore.fetchStocks()
  }
  fetchData()
})
</script>

<style scoped>
.hero-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
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
  background: #f8fafc;
  border: 2px solid #e2e8f0;
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

.card {
  background: #ffffff;
  border: 2px solid #e2e8f0;
  padding: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}

.section-header h2 {
  font-size: 1.15rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px 0;
}

.subtitle {
  font-size: 0.82rem;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .dupont-section,
  .cashflow-section,
  .stability-section,
  .capital-allocation-section {
    grid-column: span 1;
  }
}

.premium-tooltip {
  position: absolute;
  z-index: 1000;
  width: 280px;
  background: #fff;
  border: 2px solid #0f172a;
  padding: 16px;
  pointer-events: none;
}

.tooltip-title {
  display: block;
  font-weight: 800;
  color: #0f172a;
  font-size: 0.95rem;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #0f172a;
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
  transition: opacity 0.15s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* 单栏布局 */
.quality-main {
  display: grid;
  gap: 16px;
}

.section-kicker {
  margin: 0 0 10px;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}

/* 信号摘要横排 */
.signal-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.signal-group {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-top: 3px solid #cbd5e1;
  padding: 14px 16px;
}

.signal-group:nth-child(1) { border-top-color: #6366f1; }
.signal-group:nth-child(2) { border-top-color: #14b8a6; }
.signal-group:nth-child(3) { border-top-color: #f59e0b; }
.signal-group:nth-child(4) { border-top-color: #8b5cf6; }

.signal-group-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.signal-group-head span {
  font-size: 0.68rem;
  font-weight: 800;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.signal-group-head strong {
  font-size: 0.92rem;
  font-weight: 800;
  color: #0f172a;
}

.signal-items {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.signal-item {
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  cursor: default;
}

.signal-item span {
  display: block;
  font-size: 0.66rem;
  color: #94a3b8;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.signal-item strong {
  display: block;
  margin-top: 3px;
  font-size: 0.88rem;
  font-weight: 900;
  color: #0f172a;
}

/* 图表区块 */
.chart-section {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #0f766e;
  padding: 20px 24px;
  display: grid;
  gap: 16px;
}

.feature-pill {
  padding: 4px 10px;
  background: #ecfdf5;
  color: #047857;
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
  border: 1px solid #a7f3d0;
  flex-shrink: 0;
}

.feature-pill-muted {
  background: #f1f5f9;
  color: #475569;
  border-color: #cbd5e1;
}

.feature-pill-warning {
  background: #fff7ed;
  color: #c2410c;
  border-color: #fed7aa;
}

.insight-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
}

.insight-chip {
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 2px solid #cbd5e1;
}

.insight-chip span {
  display: block;
  font-size: 0.72rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 700;
}

.insight-chip strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 0.92rem;
  font-weight: 900;
}

.deferred-card {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  color: #475569;
  text-align: center;
}

.deferred-card p {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
  color: #0f172a;
}

.deferred-card span {
  font-size: 0.82rem;
  color: #64748b;
}

.deferred-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #dbeafe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@media (max-width: 1180px) {
  .signal-strip {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 720px) {
  .signal-strip {
    grid-template-columns: 1fr;
  }

  .signal-items {
    grid-template-columns: 1fr;
  }

  .insight-strip {
    grid-template-columns: 1fr;
  }
}
</style>

<template>
  <div class="analysis-detail">
    <header class="page-header hero-card">
      <div class="stock-info hero-copy" v-if="stockData">
        <p class="hero-kicker">Deep Analysis</p>
        <div class="hero-title-row">
          <h1 class="stock-name">{{ getSymbolName(stockData.symbol) }} 深度分析矩阵</h1>
          <span class="symbol-chip">{{ stockData.symbol }}</span>
        </div>
        <p class="hero-subtitle">
          先看 10 年分位与公允区间，再看安全性和投资 Thesis，避免来回切换模块。
        </p>
        <div class="badges hero-badges">
          <span class="badge color-pe">PE {{ formatMetric(mainPercentiles?.pe?.current, 'pe') }}</span>
          <span class="badge color-pb">PB {{ formatMetric(mainPercentiles?.pb?.current, 'pb') }}</span>
          <span class="badge color-dy">DY {{ formatMetric(mainPercentiles?.dy?.current, 'dy') }}</span>
          <span class="badge" :class="getScoreClass(analysisData?.f_score.score || 0)">
            F-Score {{ analysisData?.f_score.score }}/10
          </span>
        </div>
      </div>
      <div class="header-actions hero-tools">
        <div class="compare-selector" v-if="sentimentStore.sentimentData.length > 1">
          <div class="glass-header compare-header">
            <div>
              <span class="label compare-title">叠加对比</span>
              <p class="compare-subtitle">最多 4 家，统一按 10 年月线对齐。</p>
            </div>
            <span class="count compare-count">{{ compareSymbols.length }}/4</span>
          </div>
          <div class="compare-grid">
            <label
              v-for="s in availableStocks"
              :key="s.stock_symbol"
              class="glass-pill compare-pill"
              :class="{ active: compareSymbols.includes(s.stock_symbol) }"
            >
              <input
                type="checkbox"
                :value="s.stock_symbol"
                v-model="compareSymbols"
                :disabled="compareSymbols.length >= 4 && !compareSymbols.includes(s.stock_symbol)"
              />
              <span class="pill-name">{{ s.stock_name }}</span>
            </label>
          </div>
        </div>
        <button @click="$router.push('/')" class="btn-back">返回列表</button>
      </div>
    </header>

    <div class="main-content" v-if="loading && !analysisData">
      <div class="loading-overlay">
        <div class="loading-box">
          <div class="loader-circle"></div>
          <div class="loading-steps">
            <div v-for="(step, index) in steps" :key="index" 
                 class="step-item" :class="{ active: currentStep === index, done: currentStep > index }">
              <span class="step-icon">{{ currentStep > index ? '✓' : (currentStep === index ? '●' : '○') }}</span>
              <span class="step-text">{{ step }}</span>
            </div>
          </div>
          <div class="engine-tag">QUANT ENGINE V4.0</div>
        </div>
      </div>
    </div>

    <div class="main-content" v-else>
      <!-- 1. 深度对比鍥捐〃 -->
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

      <div class="grid-layout">
        <!-- 2. F-Score 安全鎬х煩闃?-->
        <section class="section safety-section">
          <div class="section-header compact-header">
            <div>
              <p class="section-kicker">Safety Screen</p>
              <h2>F-Score 排雷</h2>
              <p class="subtitle">把九项财务信号压缩到一屏，快速剔除价值陷阱。</p>
            </div>
            <div class="score-pill" :class="getScoreClass(analysisData.f_score.score)">
              {{ analysisData.f_score.score }}/10
            </div>
          </div>
          <div class="f-score-matrix">
            <div v-for="item in analysisData.f_score.details" :key="item.name" class="matrix-item">
              <div class="matrix-copy">
                <span class="matrix-name">{{ item.name }}</span>
                <span class="matrix-val">{{ item.val }}</span>
              </div>
              <span class="matrix-status" :class="{ passed: item.passed, failed: !item.passed }">
                {{ item.passed ? '通过' : '警惕' }}
              </span>
            </div>
          </div>
          <p class="section-footer">7 分以上通常代表财务结构扎实，3 分以下需要高度警惕“便宜但不安全”。</p>
        </section>


        <!-- 3. 浼板€肩粨璁哄眰 -->
                <section class="section fair-value-section" v-if="valuationConclusion && valuationRange && expectedReturn">
          <div class="valuation-header">
            <div>
              <h2>估值结论层</h2>
              <p class="section-footer section-footer-tight">综合 ROE-PB、盈利能力与股东自由现金流三种口径，给出加权估值区间。</p>
            </div>
            <div class="valuation-summary" :class="valuationSummaryClass">
              <span class="summary-label">综合判断</span>
              <strong>{{ valuationConclusion.summary }}</strong>
            </div>
          </div>
          <div class="valuation-grid">
            <div class="valuation-card valuation-card-primary">
              <span class="valuation-card-title">综合合理价值区间</span>
              <div class="valuation-main">{{ formatPrice(valuationRange.price_low) }} - {{ formatPrice(valuationRange.price_high) }}</div>
              <div class="valuation-sub">基准价 {{ formatPrice(valuationRange.price_base) }}</div>
              <div class="valuation-note">
                {{ valuationModelCount }} 个模型加权 | 模型分歧 {{ formatPct(valuationBlend?.spread_pct) }}
              </div>
            </div>
            <div class="valuation-card">
              <span class="valuation-card-title">折价 / 溢价</span>
              <div class="valuation-main">{{ valuationConclusion.discount_premium.label }}</div>
              <div class="valuation-sub">{{ formatPct(valuationConclusion.discount_premium.pct) }}</div>
              <div class="valuation-note">相对综合基准价值</div>
            </div>
            <div class="valuation-card">
              <span class="valuation-card-title">安全边际</span>
              <div class="valuation-main">{{ valuationConclusion.margin_of_safety.label }}</div>
              <div class="valuation-sub">{{ formatPct(valuationConclusion.margin_of_safety.pct) }}</div>
              <div class="valuation-note">保守估值线 {{ formatPrice(valuationConclusion.margin_of_safety.floor_price) }}</div>
            </div>
            <div class="valuation-card">
              <span class="valuation-card-title">预期年化回报</span>
              <div class="valuation-main">{{ formatPct(expectedReturn.total_annual_return_pct) }}</div>
              <div class="valuation-sub">{{ expectedReturn.holding_years }} 年视角</div>
              <div class="valuation-note">经营回报 + 股息 + 估值回归</div>
            </div>
          </div>
          <div class="valuation-grid valuation-grid-secondary">
            <div class="valuation-card">
              <span class="valuation-card-title">预期收益拆解</span>
              <div class="valuation-row">
                <span>经营回报</span>
                <strong>{{ formatPct(expectedReturn.business_return_pct) }}</strong>
              </div>
              <div class="valuation-row">
                <span>股息收益</span>
                <strong>{{ formatPct(expectedReturn.dividend_yield_pct) }}</strong>
              </div>
              <div class="valuation-row">
                <span>估值回归</span>
                <strong>{{ formatPct(expectedReturn.re_rating_annual_pct) }}</strong>
              </div>
            </div>
            <div class="valuation-card">
              <span class="valuation-card-title">信号与假设</span>
              <div class="valuation-row">
                <span>PB 分位</span>
                <strong>{{ valuationConclusion.signals.pb_percentile_zone }}</strong>
              </div>
              <div class="valuation-row">
                <span>股息率分位</span>
                <strong>{{ valuationConclusion.signals.dy_percentile_zone }}</strong>
              </div>
              <div class="valuation-row">
                <span>前瞻 ROE</span>
                <strong>{{ formatPct(valuationConclusion.assumptions.expected_roe) }}</strong>
              </div>
              <div class="valuation-row">
                <span>模型一致性</span>
                <strong>{{ valuationConclusion.signals.model_alignment_label }}</strong>
              </div>
            </div>
            <div class="valuation-card">
              <span class="valuation-card-title">敏感度演算</span>
              <div class="calculator">
                <div class="input-group">
                  <label>预期 ROE (%)</label>
                  <input type="number" v-model="calcParams.expectedRoe" step="0.5" />
                </div>
                <div class="input-group">
                  <label>要求回报率 (%)</label>
                  <input type="number" v-model="calcParams.requiredReturn" step="1" />
                </div>
                <div class="result-box compact-result">
                  <div class="res-item">
                    <span class="res-label">公允 PB</span>
                    <span class="res-val">{{ manualFairPb.toFixed(2) }}</span>
                  </div>
                  <div class="res-item">
                    <span class="res-label">公允价格</span>
                    <span class="res-val">{{ formatPrice(manualFairPrice) }}</span>
                  </div>
                  <div class="res-item main-res">
                    <span class="res-label">结论</span>
                    <span class="res-val">{{ manualValuationLabel }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="model-grid" v-if="valuationModels.length">
            <article
              v-for="model in valuationModels"
              :key="model.key"
              class="model-card"
              :class="{ 'model-card-muted': model.status !== 'available' }"
            >
              <div class="model-card-head">
                <div>
                  <span class="valuation-card-title">{{ model.label }}</span>
                  <p class="model-desc">{{ model.description || model.reason }}</p>
                </div>
                <span class="model-badge" :class="model.status === 'available' ? 'badge-ready' : 'badge-muted'">
                  {{ model.status === 'available' ? Number(model.effective_weight_pct || 0).toFixed(0) + '% 权重' : '待补数' }}
                </span>
              </div>
              <template v-if="model.status === 'available'">
                <div class="valuation-main">{{ formatPrice(model.fair_value_range.price_base) }}</div>
                <div class="valuation-sub">区间 {{ formatPrice(model.fair_value_range.price_low) }} - {{ formatPrice(model.fair_value_range.price_high) }}</div>
                <div class="valuation-row">
                  <span>模型结论</span>
                  <strong>{{ model.summary }}</strong>
                </div>
                <div class="valuation-row">
                  <span>折价 / 溢价</span>
                  <strong>{{ model.discount_premium.label }} {{ formatPct(model.discount_premium.pct) }}</strong>
                </div>
                <div class="valuation-row">
                  <span>经营回报</span>
                  <strong>{{ formatPct(model.business_return_pct) }}</strong>
                </div>
                <div class="model-highlight-list">
                  <span v-for="item in model.highlights" :key="item" class="model-highlight">{{ item }}</span>
                </div>
              </template>
<div v-else class="model-state">{{ model.reason }}</div>
            </article>
          </div>
        </section>
      </div>

      <section class="section thesis-section" v-if="investmentThesis">
        <div class="thesis-header">
          <div>
            <p class="section-kicker">Investment Thesis</p>
            <h2>投资 Thesis 跟踪</h2>
            <p class="thesis-headline">{{ investmentThesis.headline }}</p>
          </div>
          <div class="valuation-summary thesis-stance" :class="`summary-${investmentThesis.stance_color}`">
            <span class="summary-label">{{ investmentThesis.stance }}</span>
            <strong>{{ investmentThesis.confidence_score }}/100</strong>
            <span class="thesis-meta">综合置信度</span>
          </div>
        </div>

        <div class="thesis-scoreboard">
          <article class="thesis-score-card">
            <span class="mini-label">估值</span>
            <strong>{{ investmentThesis.scorecard.valuation }}</strong>
          </article>
          <article class="thesis-score-card">
            <span class="mini-label">质量</span>
            <strong>{{ investmentThesis.scorecard.quality }}</strong>
          </article>
          <article class="thesis-score-card">
            <span class="mini-label">现金流</span>
            <strong>{{ investmentThesis.scorecard.cashflow }}</strong>
          </article>
          <article class="thesis-score-card">
            <span class="mini-label">稳定性</span>
            <strong>{{ investmentThesis.scorecard.stability }}</strong>
          </article>
        </div>

        <div class="thesis-grid">
          <article class="thesis-column">
            <div class="column-header">
              <span class="mini-label">Why Now</span>
              <h3>买入理由</h3>
            </div>
            <div class="thesis-stack">
              <div v-for="item in investmentThesis.buy_case" :key="item" class="thesis-item">
                <p>{{ item }}</p>
              </div>
            </div>
          </article>

          <article class="thesis-column">
            <div class="column-header">
              <span class="mini-label">Assumptions</span>
              <h3>核心假设</h3>
            </div>
            <div class="thesis-stack">
              <div v-for="item in investmentThesis.key_assumptions" :key="item.label" class="thesis-item">
                <div class="thesis-item-head">
                  <strong>{{ item.label }}</strong>
                  <span class="thesis-badge" :class="item.status">{{ item.status_label }}</span>
                </div>
                <p>{{ item.detail }}</p>
              </div>
            </div>
          </article>

          <article class="thesis-column">
            <div class="column-header">
              <span class="mini-label">Risk Check</span>
              <h3>风险清单</h3>
            </div>
            <div class="thesis-stack">
              <div v-for="item in investmentThesis.risk_checklist" :key="item.label" class="thesis-item">
                <div class="thesis-item-head">
                  <strong>{{ item.label }}</strong>
                  <span class="thesis-badge" :class="item.level">{{ item.level_label }}风险</span>
                </div>
                <p>{{ item.detail }}</p>
              </div>
            </div>
          </article>
        </div>

        <div class="trigger-panel">
          <div class="column-header">
            <span class="mini-label">Review Triggers</span>
            <h3>财报后复核项</h3>
          </div>
          <div class="trigger-grid">
            <div v-for="item in investmentThesis.review_triggers" :key="item" class="trigger-chip">
              {{ item }}
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import * as echarts from 'echarts';
import { stockApi } from '@/api';
import { useSentimentStore } from '@/stores/sentiment';

interface PercentileMetric {
  current: number;
  p10: number;
  p50: number;
  p90: number;
}

interface InvestmentThesis {
  stance: string;
  stance_color: string;
  confidence_score: number;
  headline: string;
  scorecard: {
    valuation: string;
    quality: string;
    cashflow: string;
    stability: string;
  };
  buy_case: string[];
  key_assumptions: Array<{
    label: string;
    detail: string;
    status: string;
    status_label: string;
  }>;
  risk_checklist: Array<{
    label: string;
    detail: string;
    level: string;
    level_label: string;
  }>;
  review_triggers: string[];
}

interface AnalysisPayload {
  symbol: string;
  percentiles: Record<string, PercentileMetric>;
  forward: {
    expected_roe: number;
  };
  f_score: {
    score: number;
    details: Array<{ name: string; val: string; passed: boolean }>;
  };
  history: Array<Record<string, any>>;
  valuation_conclusion?: {
    summary: string;
    summary_color: string;
    current: {
      price: number;
      pb: number;
      pe: number;
      dividend_yield: number;
      roi: number;
    };
    fair_value_range: {
      price_low: number;
      price_base: number;
      price_high: number;
      pb_low: number;
      pb_base: number;
      pb_high: number;
    };
    discount_premium: {
      label: string;
      pct: number;
      vs: string;
    };
    margin_of_safety: {
      pct: number;
      label: string;
      floor_price: number;
    };
    expected_return: {
      holding_years: number;
      business_return_pct: number;
      dividend_yield_pct: number;
      re_rating_annual_pct: number;
      total_annual_return_pct: number;
    };
    assumptions: {
      expected_roe: number;
      required_return_low: number;
      required_return_base: number;
      required_return_high: number;
      owner_growth_low?: number;
      owner_growth_base?: number;
      owner_growth_high?: number;
    };
    signals: {
      pb_percentile_zone: string;
      dy_percentile_zone: string;
      model_alignment_label: string;
    };
    multi_model_valuation?: {
      approach: string;
      available_model_count: number;
      model_alignment_label: string;
      blended_range: {
        price_low: number;
        price_base: number;
        price_high: number;
        spread_pct: number;
        model_count: number;
      };
      models: Array<{
        key: string;
        label: string;
        status: string;
        reason: string;
        weight: number;
        effective_weight_pct: number;
        summary: string;
        business_return_pct: number;
        fair_value_range: {
          price_low: number;
          price_base: number;
          price_high: number;
          pb_low: number;
          pb_base: number;
          pb_high: number;
        };
        discount_premium: {
          label: string;
          pct: number;
          vs: string;
        };
        description: string;
        highlights: string[];
      }>;
    };
  };
  investment_thesis?: InvestmentThesis;
}

const route = useRoute();
const sentimentStore = useSentimentStore();
const symbol = route.params.symbol as string;

const loading = ref(true);
const loadingCompare = ref(false);
const analysisData = ref<AnalysisPayload | null>(null);
const historicalCache = ref<Record<string, AnalysisPayload>>({});
const compareDataMap = ref<Record<string, AnalysisPayload>>({});
const stockData = ref<{ symbol: string } | null>(null);
const activeMetric = ref('pe');
const compareSymbols = ref<string[]>([]);
const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const calcParams = ref({
  expectedRoe: 15,
  requiredReturn: 10
});

const currentStep = ref(0);
const steps = [
  '正在启动金融矩阵引擎...',
  '同步 10 年期历史分位数据...',
  '执行 F-Score 安全性排雷...',
  '计算公允价值锚点...',
  '渲染深度分析矩阵...'
];

// 计算属性
const availableStocks = computed(() => {
  return sentimentStore.sentimentData.filter(s => s.stock_symbol !== symbol);
});

const isMultiView = computed(() => compareSymbols.value.length > 0);
const mainPercentiles = computed(() => analysisData.value?.percentiles ?? null);
const activePercentile = computed(() => mainPercentiles.value?.[activeMetric.value] ?? null);
const valuationConclusion = computed(() => analysisData.value?.valuation_conclusion ?? null);
const valuationRange = computed(() => valuationConclusion.value?.fair_value_range ?? null);
const expectedReturn = computed(() => valuationConclusion.value?.expected_return ?? null);
const multiModelValuation = computed(() => valuationConclusion.value?.multi_model_valuation ?? null);
const valuationBlend = computed(() => multiModelValuation.value?.blended_range ?? null);
const valuationModels = computed(() => multiModelValuation.value?.models ?? []);
const valuationModelCount = computed(() => multiModelValuation.value?.available_model_count ?? 0);
const investmentThesis = computed(() => analysisData.value?.investment_thesis ?? null);
const valuationSummaryClass = computed(() => `summary-${valuationConclusion.value?.summary_color || 'slate'}`);
const manualFairPb = computed(() => {
  const expectedRoe = Number(calcParams.value.expectedRoe || 0);
  const requiredReturn = Number(calcParams.value.requiredReturn || 0);
  if (expectedRoe <= 0 || requiredReturn <= 0) return 0;
  return expectedRoe / requiredReturn;
});
const manualFairPrice = computed(() => {
  const current = valuationConclusion.value?.current;
  if (!current || current.pb <= 0) return 0;
  return (current.price / current.pb) * manualFairPb.value;
});
const manualValuationLabel = computed(() => {
  const currentPrice = valuationConclusion.value?.current.price || 0;
  if (currentPrice <= 0 || manualFairPrice.value <= 0) return '数据不足';
  const ratio = manualFairPrice.value / currentPrice;
  if (ratio >= 1.2) return '偏低估';
  if (ratio <= 0.85) return '偏贵';
  return '合理';
});

onMounted(async () => {
  if (sentimentStore.sentimentData.length === 0) {
    await sentimentStore.fetchLatestSentiment();
  }
  await fetchMainData();
  initChart();
  window.addEventListener('resize', handleResize);
});

const fetchMainData = async () => {
  loading.value = true;
  currentStep.value = 0;
  try {
    currentStep.value = 1;
    const res = await stockApi.getAnalysis(symbol);
    analysisData.value = res.data;
    calcParams.value.expectedRoe = res.data.valuation_conclusion?.assumptions?.expected_roe ?? res.data.forward.expected_roe;
    stockData.value = { symbol: res.data.symbol };
    historicalCache.value[symbol] = res.data;

    currentStep.value = 2;
    currentStep.value = 3;
    currentStep.value = 4;
  } catch (error) {
    console.error('Failed to fetch analysis:', error);
  } finally {
    loading.value = false;
    await nextTick();
  }
};

const fetchComparisonData = async () => {
  const symbols = compareSymbols.value;
  if (symbols.length === 0) {
    compareDataMap.value = {};
    await nextTick();
    initChart();
    return;
  }

  // 鎵惧嚭缂撳瓨涓病鏈夌殑鏍囩殑
  const missingSymbols = symbols.filter(s => !historicalCache.value[s]);
  
  if (missingSymbols.length > 0) {
    loadingCompare.value = true;
    try {
      const requests = missingSymbols.map(s => 
        stockApi.getAnalysis(s)
      );
      const results = await Promise.all(requests);
      results.forEach((r, idx) => {
        historicalCache.value[missingSymbols[idx]] = r.data;
      });
    } catch (error) {
      console.error('Fetch comparison error:', error);
    } finally {
      loadingCompare.value = false;
    }
  }

  // 浠庣紦瀛樹腑同步当前鍕鹃€夌殑对比鏁版嵁
  const newMap: Record<string, AnalysisPayload> = {};
  symbols.forEach(s => {
    if (historicalCache.value[s]) {
      newMap[s] = historicalCache.value[s];
    }
  });
  compareDataMap.value = newMap;
  await nextTick();
  initChart();
};

const handleResize = () => {
  chartInstance?.resize();
};

watch(compareSymbols, () => {
  fetchComparisonData();
}, { deep: true });

const isUnderValued = computed(() => {
  const p = mainPercentiles.value?.[activeMetric.value];
  if (!p) return false;
  // 股息率越高越安全，其余估值指标越低越安全。
  if (activeMetric.value === 'dy') return p.current >= p.p90;
  return p.current <= p.p10;
});

const getPercentilePos = (metric: string) => {
  const p = mainPercentiles.value?.[metric];
  if (!p) return '未知';
  if (metric === 'dy') {
    if (p.current >= p.p90) return '极高 (安全)';
    if (p.current <= p.p10) return '极低 (风险)';
  } else {
    if (p.current <= p.p10) return '极低 (安全)';
    if (p.current >= p.p90) return '极高 (风险)';
  }
  return '中性';
};


const getScoreClass = (score: number) => {
  if (score >= 7) return 'score-high';
  if (score <= 3) return 'score-low';
  return 'score-mid';
};

const getMetricLabel = (metric: string) => {
  return {
    pe: 'PE',
    pb: 'PB',
    roi: 'ROI',
    dy: '股息率',
  }[metric] || metric.toUpperCase();
};

const getSymbolName = (s: string) => {
  return sentimentStore.sentimentData.find(item => item.stock_symbol === s)?.stock_name || s;
};

const formatPct = (value?: number) => {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  return `${Number(value).toFixed(1)}%`;
};

const formatPrice = (value?: number) => {
  if (value === undefined || value === null || Number.isNaN(value) || value <= 0) return '--';
  return Number(value).toFixed(2);
};

const formatMetric = (value?: number, metric = 'pe') => {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  const digits = metric === 'dy' || metric === 'roi' ? 1 : 2;
  const base = Number(value).toFixed(digits);
  return metric === 'dy' ? `${base}%` : base;
};

const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const initChart = () => {
  if (!chartRef.value || !analysisData.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);
  
  const metric = activeMetric.value;
  const mainP = mainPercentiles.value ? mainPercentiles.value[metric] : null;
  const mainHistory = analysisData.value.history || [];
  
  if (!mainP || mainHistory.length === 0) {
    chartInstance.clear();
    return;
  }

  const series: any[] = [];
  const mainName = getSymbolName(symbol);
  const legendData: string[] = [mainName];

  // 1. 主线数据 (采用公司名)
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
  });

  // 2. 对比绾挎暟鎹?(采用公司名?
  compareSymbols.value.forEach((s, idx) => {
    const d = compareDataMap.value[s];
    if (d && d.history) {
      const name = getSymbolName(s);
      legendData.push(name);
      series.push({
        name: name,
        type: 'line',
        data: d.history.map((h: any) => h[metric] || 0),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: colors[idx + 1], type: 'dashed', opacity: 0.8 }
      });
    }
  });

  const dates = mainHistory.map((h: any) => h.date);
  const allValues = series.flatMap(s => s.data);
  const maxY = Math.max(...allValues, mainP.p90) * 1.1;

  const option = {
    backgroundColor: 'transparent',
    legend: { show: isMultiView.value, data: legendData, top: 0, right: 10, textStyle: { color: '#64748b' } },
    grid: { top: 50, right: 30, bottom: 40, left: 50 },
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255, 255, 255, 0.9)', borderColor: '#e2e8f0' },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#64748b' }, splitLine: { show: false } },
    yAxis: { type: 'value', max: maxY, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } } },
    series: series
  };
  
  chartInstance.setOption(option, true);
};

// 监听器
watch([activeMetric, compareDataMap], () => {
  initChart();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chartInstance?.dispose();
  chartInstance = null;
});
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  gap: 20px;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  flex: 1;
}

.compare-selector {
  background: rgba(255, 255, 255, 0.9); /* 提高不透明度?*/
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid #cbd5e1; /* 明显鐨勮竟妗?*/
  padding: 16px;
  border-radius: 20px;
  width: 100%;
  max-width: 550px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
}

.glass-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 8px;
}

.glass-header .label {
  font-size: 0.8rem;
  font-weight: 800;
  color: #1e293b; /* 加深文字颜色 */
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.glass-header .count {
  font-size: 0.7rem;
  font-weight: 800;
  background: #3b82f6;
  color: white;
  padding: 2px 10px;
  border-radius: 20px;
}

.compare-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

.glass-pill {
  position: relative;
  font-size: 0.75rem;
  padding: 8px 14px;
  background: #f1f5f9; /* 明显鐨勫簳鑹?*/
  border: 1px solid #e2e8f0;
  color: #475569;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  font-weight: 600;
}

.glass-pill input {
  display: none;
}

.glass-pill:hover {
  background: #f8fafc;
  border-color: #3b82f6;
  color: #3b82f6;
  transform: translateY(-2px);
}

.glass-pill.active {
  background: #3b82f6;
  color: white;
  border-color: #2563eb;
  font-weight: 800;
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.4);
}

.stock-name {
  font-size: 1.8rem;
  font-weight: 900;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #0f172a 0%, #3b82f6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.badges {
  display: flex;
  gap: 10px;
}

.badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 700;
  font-family: 'Monaco', monospace;
}

.color-pe { background: #dbeafe; color: #1e40af; }
.color-pb { background: #fef3c7; color: #92400e; }
.color-dy { background: #dcfce7; color: #166534; }
.score-high { background: #d1fae5; color: #065f46; }
.score-mid { background: #f1f5f9; color: #475569; }
.score-low { background: #fee2e2; color: #991b1b; }

.btn-back {
  padding: 8px 20px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  background: white;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-back:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.section {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  border: 1px solid #f1f5f9;
  margin-bottom: 24px;
}

.title-group h2 {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
}

.title-group .subtitle {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
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

.grid-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.valuation-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.valuation-summary {
  min-width: 140px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: right;
}

.summary-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
}

.summary-emerald {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #065f46;
}

.summary-amber {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}

.summary-rose {
  background: #fff1f2;
  border-color: #fecdd3;
  color: #9f1239;
}

.summary-slate {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #334155;
}

.valuation-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.valuation-grid-secondary {
  margin-top: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.valuation-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.valuation-card-primary {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border-color: #bfdbfe;
}

.valuation-card-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  font-weight: 700;
}

.valuation-main {
  font-size: 1.5rem;
  line-height: 1.1;
  font-weight: 900;
  color: #0f172a;
  font-family: 'Monaco', monospace;
}

.valuation-sub {
  font-size: 0.95rem;
  font-weight: 700;
  color: #2563eb;
}

.valuation-note {
  font-size: 0.78rem;
  color: #64748b;
}

.valuation-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.88rem;
  color: #334155;
}

.section-footer-tight {
  margin-top: 6px;
}

.model-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.model-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.model-card-muted {
  opacity: 0.72;
}

.model-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.model-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
}

.badge-ready {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge-muted {
  background: #e2e8f0;
  color: #475569;
}

.model-desc {
  margin: 6px 0 0;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #64748b;
}

.model-state {
  font-size: 0.86rem;
  color: #64748b;
}

.model-highlight-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}

.model-highlight {
  padding: 6px 10px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 0.72rem;
  font-weight: 700;
}

.f-score-matrix {
  display: grid;
  gap: 10px;
}

.matrix-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 0.85rem;
}

.matrix-name { font-weight: 600; color: #475569; }
.matrix-val { font-family: 'Monaco', monospace; font-weight: 700; color: #1e293b; }
.matrix-status.passed { color: #10b981; font-weight: 800; }

.calculator {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.input-group label { font-size: 0.9rem; font-weight: 600; color: #475569; }

.input-group input {
  width: 100px;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 700;
  color: #3b82f6;
  background: #f8fafc;
  text-align: center;
}

.result-box {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.compact-result {
  padding: 16px;
}

.res-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.res-label { font-size: 0.85rem; color: #64748b; font-weight: 600; }
.res-val { font-weight: 800; font-family: 'Monaco', monospace; }

.main-res {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #cbd5e1;
  font-size: 1.2rem;
}

.main-res .res-val { color: #3b82f6; }

.section-footer {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 16px;
  font-style: italic;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.loading-box {
  background: white;
  padding: 40px;
  border-radius: 24px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.1);
  border: 1px solid #f1f5f9;
  width: 100%;
  max-width: 400px;
  text-align: center;
}

.loader-circle {
  width: 48px;
  height: 48px;
  border: 4px solid #f1f5f9;
  border-top-color: #3b82f6;
  border-radius: 50%;
  margin: 0 auto 24px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-steps {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #94a3b8;
  font-size: 0.9rem;
  transition: all 0.3s;
}

.step-item.active {
  color: #3b82f6;
  font-weight: 700;
  transform: translateX(4px);
}

.step-item.done {
  color: #10b981;
}

.step-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: monospace;
}

.engine-tag {
  margin-top: 32px;
  font-size: 0.7rem;
  font-weight: 800;
  color: #cbd5e1;
  letter-spacing: 0.2em;
}

@media (max-width: 1024px) {
  .grid-layout {
    grid-template-columns: 1fr;
  }
  .valuation-grid,
  .valuation-grid-secondary,
  .model-grid {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .header-actions {
    width: 100%;
    align-items: flex-start;
  }
  .compare-selector {
    max-width: none;
  }
  .valuation-header {
    flex-direction: column;
    align-items: stretch;
  }
  .valuation-summary {
    text-align: left;
  }
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

.analysis-detail {
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 28%),
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
}

.hero-card {
  padding: 28px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 20px 48px -36px rgba(15, 23, 42, 0.45);
}

.hero-kicker,
.section-kicker,
.compare-title,
.mini-label {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}

.hero-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
}

.hero-subtitle {
  margin: 0 0 18px;
  max-width: 720px;
  color: #475569;
  font-size: 0.96rem;
  line-height: 1.7;
}

.hero-badges {
  flex-wrap: wrap;
}

.symbol-chip {
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'Monaco', monospace;
}

.compare-subtitle {
  margin: 6px 0 0;
  font-size: 0.84rem;
  line-height: 1.5;
  color: #64748b;
}

.compare-count {
  min-width: 44px;
  text-align: center;
}

.btn-back {
  align-self: flex-end;
  background: #0f172a;
  color: #fff;
  border: none;
}

.btn-back:hover {
  background: #1e293b;
}

.chart-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(250px, 0.7fr);
  gap: 18px;
}

.chart-main {
  min-width: 0;
}

.chart-sidebar {
  display: grid;
  gap: 14px;
  align-content: start;
}

.sidebar-card,
.thesis-score-card,
.thesis-column,
.trigger-panel {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 20px;
}

.sidebar-card {
  padding: 18px;
}

.sidebar-card strong,
.thesis-score-card strong {
  display: block;
  margin-top: 10px;
  color: #0f172a;
  font-size: 1.2rem;
  font-weight: 900;
}

.sidebar-card p,
.thesis-headline,
.thesis-item p,
.thesis-meta {
  color: #64748b;
  line-height: 1.6;
}

.sidebar-card p {
  margin: 8px 0 0;
  font-size: 0.9rem;
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

.grid-layout {
  grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.22fr);
}

.compact-header {
  margin-bottom: 18px;
}

.score-pill {
  min-width: 78px;
  text-align: center;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 800;
  font-family: 'Monaco', monospace;
}

.matrix-copy {
  display: grid;
  gap: 4px;
}

.matrix-item {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
}

.matrix-status {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
}

.matrix-status.failed {
  background: #fee2e2;
  color: #b91c1c;
  font-weight: 800;
}

.thesis-section {
  display: grid;
  gap: 18px;
}

.thesis-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.thesis-scoreboard {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.thesis-score-card {
  padding: 16px;
}

.thesis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.thesis-column,
.trigger-panel {
  padding: 18px;
}

.column-header h3 {
  margin: 6px 0 0;
  color: #0f172a;
}

.thesis-stack {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.thesis-item {
  padding: 14px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.thesis-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 800;
}

.thesis-badge.on_track,
.thesis-badge.low {
  background: #dcfce7;
  color: #166534;
}

.thesis-badge.watch,
.thesis-badge.medium {
  background: #fef3c7;
  color: #92400e;
}

.thesis-badge.at_risk,
.thesis-badge.high {
  background: #fee2e2;
  color: #b91c1c;
}

.trigger-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.trigger-chip {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .chart-layout,
  .thesis-grid,
  .thesis-scoreboard,
  .trigger-grid {
    grid-template-columns: 1fr;
  }

  .btn-back {
    align-self: flex-start;
  }
}
</style>


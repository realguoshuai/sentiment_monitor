<template>
  <div class="analysis-detail">
    <header class="page-header hero-card">
      <div class="stock-info hero-copy" v-if="stockData">
        <p class="hero-kicker">Deep Analysis</p>
        <div class="hero-title-row">
          <h1 class="stock-name">{{ getSymbolName(stockData.symbol) }} 估值分析矩阵</h1>
          <span class="symbol-chip">{{ stockData.symbol }}</span>
        </div>
        <p class="hero-subtitle">
          深度观测 10 年分位与公允价值区间，结合 F-Score 排雷，构建完整的价值投资决策矩阵。
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
        <div class="compare-selector" v-if="sentimentStore.dashboardStocks.length > 1">
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
          <div class="loading-quote">
            <p>"{{ loadingQuote.text }}"</p>
            <span>{{ loadingQuote.author }}</span>
          </div>
          <button type="button" class="loading-back-btn" @click="goDashboard">
            返回首页
          </button>
          <div class="engine-tag">QUANT ENGINE V4.0</div>
        </div>
      </div>
    </div>

    <div class="main-content" v-else>
      <section v-if="analysisCacheNotice" class="analysis-cache-banner">
        <div class="analysis-cache-copy">
          <span class="analysis-cache-badge">
            {{ analysisData?.background_refreshing ? '缓存优先' : '缓存结果' }}
          </span>
          <strong>{{ analysisCacheNotice }}</strong>
        </div>
        <span v-if="analysisCacheAtText" class="analysis-cache-time">{{ analysisCacheAtText }}</span>
      </section>

      <ValuationChart
        :analysisData="analysisData"
        :compareSymbols="compareSymbols"
        :compareDataMap="compareDataMap"
        :loadingCompare="loadingCompare"
      />

      <div class="grid-layout">
        <FScoreMatrix
          :score="analysisData?.f_score?.score ?? 0"
          :details="analysisData?.f_score?.details ?? []"
        />


        <ValuationConclusionPanel
          :valuationConclusion="valuationConclusion"
          :valuationRange="valuationRange"
          :expectedReturn="expectedReturn"
          :valuationModels="valuationModels"
          :valuationModelCount="valuationModelCount"
          :valuationBlend="valuationBlend"
          :normalizedEarnings="normalizedEarnings"
          :valuationSummaryClass="valuationSummaryClass"
        />
      </div>

      <PeerComparison :peerComparison="peerComparison" />

      <InvestmentThesisPanel :investmentThesis="investmentThesis" />
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { stockApi } from '@/api';
import { useSentimentStore } from '@/stores/sentiment';
import { useInvestorLoadingQuotes } from '@/composables/useInvestorLoadingQuotes';

import FScoreMatrix from '@/components/FScoreMatrix.vue'
import ValuationChart from '@/components/ValuationChart.vue'
import ValuationConclusionPanel from '@/components/ValuationConclusionPanel.vue'
import PeerComparison from '@/components/PeerComparison.vue'
import InvestmentThesisPanel from '@/components/InvestmentThesisPanel.vue'

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

interface PeerComparisonRow {
  symbol: string;
  name: string;
  industry: string;
  is_target: boolean;
  price: number;
  market_cap: number;
  pe: number;
  pb: number;
  dividend_yield: number;
  expected_roe: number;
}

interface AnalysisPayload {
  symbol: string;
  cache_status?: 'fresh' | 'stale';
  background_refreshing?: boolean;
  cached_at?: string | null;
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
    normalized_earnings?: {
      enabled: boolean;
      selected_basis: string;
      basis_label: string;
      window_years: number;
      cycle_position_label: string;
      current_eps: number;
      normalized_eps: number;
      eps_deviation_pct: number;
      current_fcf_per_share: number;
      normalized_fcf_per_share: number;
      fcf_deviation_pct: number;
      current_net_margin_pct: number;
      normalized_net_margin_pct: number;
      margin_deviation_pct: number;
      explanation: string;
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
        basis_label?: string;
        highlights: string[];
      }>;
    };
  };
  peer_comparison?: {
    enabled: boolean;
    industry: string;
    peer_count: number;
    source_label: string;
    reason: string;
    summary: string;
    medians: {
      price: number;
      pe: number;
      pb: number;
      dividend_yield: number;
      expected_roe: number;
    };
    relative_view: {
      pe_vs_peer_median_pct: number;
      pb_vs_peer_median_pct: number;
      dividend_yield_vs_peer_median_pct: number;
      expected_roe_vs_peer_median_pct: number;
    };
    rows: PeerComparisonRow[];
  };
  investment_thesis?: InvestmentThesis;
}



const route = useRoute();
const router = useRouter();
const symbol = route.params.symbol as string;
const sentimentStore = useSentimentStore();

const stockData = ref<{ symbol: string } | null>(null);
const analysisData = ref<AnalysisPayload | null>(null);
const loading = ref(true);
const compareSymbols = ref<string[]>([]);
const compareDataMap = ref<Record<string, AnalysisPayload>>({});
const loadingCompare = ref(false);
const historicalCache = ref<Record<string, AnalysisPayload>>({});
let analysisRetryTimer: number | null = null;
let analysisRetryCount = 0;

const { loadingQuote } = useInvestorLoadingQuotes(loading);

const currentStep = ref(0);
const steps = [
  '正在启动金融矩阵引擎...',
  '同步 10 年期历史分位数据...',
  '执行 F-Score 安全性排雷...',
  '计算公允价值锚点...',
  '渲染估值分析矩阵...'
];

// 计算属性
const availableStocks = computed(() => {
  return sentimentStore.dashboardStocks.filter(s => s.stock_symbol !== symbol);
});

const mainPercentiles = computed(() => analysisData.value?.percentiles ?? null);
const valuationConclusion = computed(() => analysisData.value?.valuation_conclusion ?? null);
const valuationRange = computed(() => valuationConclusion.value?.fair_value_range ?? null);
const expectedReturn = computed(() => valuationConclusion.value?.expected_return ?? null);
const multiModelValuation = computed(() => valuationConclusion.value?.multi_model_valuation ?? null);
const valuationBlend = computed(() => multiModelValuation.value?.blended_range ?? null);
const valuationModels = computed(() => multiModelValuation.value?.models ?? []);
const valuationModelCount = computed(() => multiModelValuation.value?.available_model_count ?? 0);
const normalizedEarnings = computed(() => valuationConclusion.value?.normalized_earnings ?? null);
const peerComparison = computed(() => analysisData.value?.peer_comparison ?? null);
const investmentThesis = computed(() => analysisData.value?.investment_thesis ?? null);
const valuationSummaryClass = computed(() => `summary-${valuationConclusion.value?.summary_color || 'slate'}`);
const analysisCacheAtText = computed(() => formatCacheTimestamp(analysisData.value?.cached_at));
const analysisCacheNotice = computed(() => {
  if (!analysisData.value || analysisData.value.cache_status !== 'stale') return '';

  const prefix = analysisCacheAtText.value
    ? `当前先展示 ${analysisCacheAtText.value} 的分析结果`
    : '当前先展示上次缓存结果';

  return analysisData.value.background_refreshing
    ? `${prefix}，后台正在刷新最新分析。`
    : `${prefix}。`;
});

const goDashboard = () => {
  clearAnalysisRefreshRetry();
  loading.value = false;
  router.push('/');
};

onMounted(async () => {
  if (sentimentStore.stocks.length === 0) {
    await sentimentStore.fetchStocks();
  }
  if (sentimentStore.sentimentData.length === 0) {
    await sentimentStore.fetchLatestSentiment();
  }
  await fetchMainData();
});

const fetchMainData = async () => {
  if (sentimentStore.analysisCache[symbol]) {
    const cached = sentimentStore.analysisCache[symbol];
    applyAnalysisPayload(cached);
    syncAnalysisRefreshState(cached);
    loading.value = false;
    currentStep.value = 4;
    // 如果是陈旧缓存，依然在后台触发同步
    if (cached.cache_status === 'stale') {
       void sentimentStore.getAnalysis(symbol, true).then(data => {
         applyAnalysisPayload(data);
         syncAnalysisRefreshState(data);
       });
    }
    return;
  }

  loading.value = true;
  currentStep.value = 0;
  clearAnalysisRefreshRetry();
  try {
    currentStep.value = 1;
    const data = await sentimentStore.getAnalysis(symbol);
    applyAnalysisPayload(data);
    syncAnalysisRefreshState(data);

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
    return;
  }

  // 找出缓存中没有的标的
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

  // 从缓存中同步当前勾选的对比数据
  const newMap: Record<string, AnalysisPayload> = {};
  symbols.forEach(s => {
    if (historicalCache.value[s]) {
      newMap[s] = historicalCache.value[s];
    }
  });
  compareDataMap.value = newMap;
};


watch(compareSymbols, () => {
  fetchComparisonData();
}, { deep: true });



const getScoreClass = (score: number) => {
  if (score >= 7) return 'score-high';
  if (score <= 3) return 'score-low';
  return 'score-mid';
};


const getSymbolName = (s: string) => {
  return sentimentStore.getStockBySymbol(s)?.stock_name || s;
};

const formatCacheTimestamp = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `上次更新 ${date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })}`;
};


const formatMetric = (value?: number, metric = 'pe') => {
  if (value === undefined || value === null || Number.isNaN(value)) return '--';
  const digits = metric === 'dy' || metric === 'roi' ? 1 : 2;
  const base = Number(value).toFixed(digits);
  return metric === 'dy' ? `${base}%` : base;
};


const clearAnalysisRefreshRetry = () => {
  if (analysisRetryTimer !== null) {
    window.clearTimeout(analysisRetryTimer);
    analysisRetryTimer = null;
  }
  analysisRetryCount = 0;
};

const applyAnalysisPayload = (payload: AnalysisPayload) => {
  analysisData.value = payload;
  stockData.value = { symbol: payload.symbol };
  historicalCache.value[payload.symbol] = payload;
};

const MAX_ANALYSIS_REFRESH_RETRIES = 3;

const queueAnalysisRefreshRetry = () => {
  if (analysisRetryTimer !== null || analysisRetryCount >= MAX_ANALYSIS_REFRESH_RETRIES) return;

  const delay = analysisRetryCount === 0 ? 4000 : 7000;
  analysisRetryTimer = window.setTimeout(async () => {
    analysisRetryTimer = null;
    analysisRetryCount += 1;

    try {
      const res = await stockApi.getAnalysis(symbol);
      applyAnalysisPayload(res.data);
      syncAnalysisRefreshState(res.data);
    } catch (error) {
      console.error('Failed to refresh analysis cache:', error);
      if (analysisRetryCount < MAX_ANALYSIS_REFRESH_RETRIES) {
        queueAnalysisRefreshRetry();
      }
    }
  }, delay);
};

const syncAnalysisRefreshState = (payload: AnalysisPayload) => {
  if (payload.cache_status === 'stale' && payload.background_refreshing) {
    queueAnalysisRefreshRetry();
    return;
  }

  clearAnalysisRefreshRetry();
};


onUnmounted(() => {
  clearAnalysisRefreshRetry();
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
  border: 1px solid #cbd5e1; /* 明显的边框 */
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
  background: #f1f5f9; /* 明显的底色?*/
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


.grid-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.22fr);
  gap: 24px;
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

.loading-quote {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96) 0%, rgba(248, 250, 252, 0.98) 100%);
  border: 1px solid rgba(59, 130, 246, 0.18);
  text-align: center;
}

.loading-quote p {
  margin: 0;
  color: #0f172a;
  font-size: 0.94rem;
  font-weight: 700;
  line-height: 1.7;
}

.loading-quote span {
  display: block;
  margin-top: 8px;
  color: #2563eb;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 800;
}

.loading-back-btn {
  margin-top: 18px;
  width: 100%;
  border: 1px solid #cbd5e1;
  background: #0f172a;
  color: #ffffff;
  border-radius: 14px;
  padding: 12px 16px;
  font-size: 0.9rem;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
}

.loading-back-btn:hover {
  background: #1e293b;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.16);
  transform: translateY(-1px);
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
}

.analysis-detail {
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 28%),
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 24%),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
}

.analysis-cache-banner {
  margin-bottom: 18px;
  padding: 14px 18px;
  border-radius: 18px;
  border: 1px solid #fed7aa;
  background: linear-gradient(135deg, rgba(255, 247, 237, 0.98) 0%, rgba(255, 255, 255, 0.94) 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  color: #9a3412;
  box-shadow: 0 16px 32px -28px rgba(154, 52, 18, 0.55);
}

.analysis-cache-copy {
  display: grid;
  gap: 6px;
}

.analysis-cache-copy strong {
  font-size: 0.92rem;
  line-height: 1.6;
}

.analysis-cache-badge {
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 237, 213, 0.95);
  color: #c2410c;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.analysis-cache-time {
  white-space: nowrap;
  font-size: 0.8rem;
  font-weight: 700;
  color: #c2410c;
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



@media (max-width: 1180px) {
  .btn-back {
    align-self: flex-start;
  }
  .analysis-cache-banner {
    display: grid;
  }
  .analysis-cache-time {
    white-space: normal;
  }
}
</style>


<template>
  <div class="light-page analysis-detail">
    <header class="light-hero-card">
      <div class="stock-info" v-if="stockData">
        <p class="light-hero-kicker">Deep Analysis</p>
        <div class="hero-title-row">
          <h1 class="light-hero-title">{{ getSymbolName(stockData.symbol) }} 估值分析矩阵</h1>
          <span class="light-symbol-chip">{{ stockData.symbol }}</span>
        </div>
        <p class="light-hero-subtitle">
          深度观测 10 年分位与公允价值区间，结合 F-Score 排雷，构建完整的价值投资决策矩阵。
        </p>
        <div class="badges">
          <span class="light-badge light-badge-pe">PE {{ formatMetric(mainPercentiles?.pe?.current, 'pe') }}</span>
          <span class="light-badge light-badge-pb">PB {{ formatMetric(mainPercentiles?.pb?.current, 'pb') }}</span>
          <span class="light-badge light-badge-dy">DY {{ formatMetric(mainPercentiles?.dy?.current, 'dy') }}</span>
          <span class="light-badge" :class="getScoreClass(analysisData?.f_score.score || 0)">
            F-Score {{ analysisData?.f_score.score }}/10
          </span>
        </div>
      </div>
      <div class="header-actions">
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
        <button @click="$router.push('/')" class="light-btn-back">返回列表</button>
      </div>
    </header>

    <AlgorithmExplainer title="估值分析算法说明" :defaultOpen="false">
      <h4>公允价值计算</h4>
      <p>采用三模型加权估值，综合不同视角给出合理价格区间：</p>
      <div class="formula">
        公允价值 = ROE-PB锚点 × 45% + 盈利能力估值 × 30% + 股东现金流估值 × 25%
      </div>

      <h4>模型 1：ROE-PB 锚点（权重 45%）</h4>
      <p>用预期 ROE 和要求回报率反推合理 PB：</p>
      <div class="formula">
        合理PB = 预期ROE ÷ 要求回报率（基准 10%）<br/>
        合理价 = 每股净资产 × 合理PB
      </div>
      <p class="note">预期ROE 取自 TTM 利润/净资产，或近 5 年均值。</p>

      <h4>模型 2：盈利能力估值（权重 30%）</h4>
      <p>把 EPS 资本化，用要求回报率反推合理 PE：</p>
      <div class="formula">
        合理PE = 1 ÷ 要求回报率（基准 10%）= 10 倍<br/>
        合理价 = 归一化EPS × 合理PE
      </div>
      <p class="note">归一化 EPS = 近 5 年年报 EPS 中位数，剔除周期波动影响。</p>

      <h4>模型 3：股东自由现金流估值（权重 25%）</h4>
      <p>基于戈登增长模型变体：</p>
      <div class="formula">
        合理价 = 每股FCF × (1 + 增长率) ÷ (折现率 - 增长率)<br/>
        增长率 = min(ROE × 留存率 × 60%, 6%)，限制在 1.5%~6%
      </div>

      <h4>F-Score 安全性评分（0~10 分）</h4>
      <p>检查 5 项财务健康指标，按通过比例折算为 10 分制：</p>
      <ul>
        <li>ROA > 0（盈利能力）</li>
        <li>净利润 > 0（盈利能力）</li>
        <li>经营性现金流 > 0（现金流质量）</li>
        <li>现金流 > 净利润（利润含金量）</li>
        <li>ROA 同比提升（增长趋势）</li>
      </ul>
      <div class="thresholds">
        <span class="threshold threshold-green">≥ 7 分：健康</span>
        <span class="threshold threshold-yellow">4~6 分：关注</span>
        <span class="threshold threshold-red">≤ 3 分：风险</span>
      </div>

      <h4>安全边际</h4>
      <div class="formula">
        安全边际 = (保守估值 - 当前价) ÷ 保守估值 × 100%
      </div>
      <div class="thresholds">
        <span class="threshold threshold-green">≥ 30%：高安全边际</span>
        <span class="threshold threshold-yellow">15%~30%：中等</span>
        <span class="threshold threshold-red">< 15%：低/无</span>
      </div>

      <h4>预期年化回报（3 年视角）</h4>
      <div class="formula">
        总回报 = 经营回报率 + 股息率 + 估值回归年化<br/>
        经营回报率 = 预期ROE ÷ 当前PB<br/>
        估值回归 = (基准公允价 ÷ 当前价)^(1/3) - 1
      </div>
    </AlgorithmExplainer>

    <div class="main-content" v-if="fetchError && !analysisData">
      <div class="loading-overlay">
        <div class="loading-box" style="text-align:center;">
          <div style="font-size:2rem;margin-bottom:12px;">⚠️</div>
          <div style="font-size:14px;color:#94a3b8;margin-bottom:16px;">{{ fetchError }}</div>
          <button type="button" class="loading-back-btn" @click="fetchMainData()">重试</button>
          <button type="button" class="loading-back-btn" @click="goDashboard" style="margin-top:8px;">返回首页</button>
        </div>
      </div>
    </div>

    <div class="main-content" v-else-if="loading && !analysisData">
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
import AlgorithmExplainer from '@/components/AlgorithmExplainer.vue'
import type { AnalysisPayload } from '@/types/analysis'



const route = useRoute();
const router = useRouter();
const symbol = route.params.symbol as string;
const sentimentStore = useSentimentStore();

const stockData = ref<{ symbol: string } | null>(null);
const analysisData = ref<AnalysisPayload | null>(null);
const loading = ref(true);
const fetchError = ref<string | null>(null);
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
  await Promise.all([
    sentimentStore.stocks.length === 0 ? sentimentStore.fetchStocks() : Promise.resolve(),
    sentimentStore.sentimentData.length === 0 ? sentimentStore.fetchLatestSentiment() : Promise.resolve(),
    fetchMainData(),
  ]);
});

const fetchMainData = async () => {
  const cachedData = sentimentStore.analysisCache[symbol]?.data as AnalysisPayload | undefined;
  if (cachedData) {
    applyAnalysisPayload(cachedData);
    syncAnalysisRefreshState(cachedData);
    loading.value = false;
    currentStep.value = 4;
    // 如果是陈旧缓存，依然在后台触发同步
    if (cachedData.cache_status === 'stale') {
       void sentimentStore.getAnalysis(symbol, true).then(data => {
         applyAnalysisPayload(data);
         syncAnalysisRefreshState(data);
       });
    }
    return;
  }

  loading.value = true;
  fetchError.value = null;
  currentStep.value = 0;
  clearAnalysisRefreshRetry();
  try {
    currentStep.value = 1;
    const data = await sentimentStore.getAnalysis(symbol);
    applyAnalysisPayload(data);
    syncAnalysisRefreshState(data);

    currentStep.value = 4;
  } catch (error: any) {
    console.error('Failed to fetch analysis:', error);
    fetchError.value = error?.message || '加载分析数据失败';
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
  if (score >= 7) return 'light-badge-high';
  if (score <= 3) return 'light-badge-low';
  return 'light-badge-mid';
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
.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  flex: 1;
}

.hero-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
}

/* Editorial: 统一为浅色圆角卡片 */
.compare-selector {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 18px;
  padding: 18px;
  width: 100%;
  max-width: 550px;
  box-shadow: 0 6px 24px -8px rgba(15, 23, 42, 0.06), 0 2px 6px rgba(15, 23, 42, 0.03);
}

.glass-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  border-bottom: 2px solid #0f172a;
  padding-bottom: 8px;
}

.glass-header .label {
  font-size: 0.8rem;
  font-weight: 800;
  color: #0f172a;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.glass-header .count {
  font-size: 0.7rem;
  font-weight: 800;
  background: #0f172a;
  color: white;
  padding: 2px 10px;
}

.compare-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.glass-pill {
  position: relative;
  font-size: 0.75rem;
  padding: 6px 14px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  font-weight: 600;
}

.glass-pill input {
  display: none;
}

.glass-pill:hover {
  border-color: #0f172a;
  color: #0f172a;
}

.glass-pill.active {
  background: #0f172a;
  color: white;
  border-color: #0f172a;
  font-weight: 800;
}

.badges {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.grid-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.78fr) minmax(0, 1.22fr);
  gap: 0;
  border-top: 1px solid #e5e7eb;
}

/* Editorial: 全屏加载用纯白底，无模糊 */
.loading-overlay {
  position: fixed;
  inset: 0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.loading-box {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 40px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 20px;
  width: 100%;
  max-width: 400px;
  text-align: center;
  box-shadow: 0 10px 40px -12px rgba(15, 23, 42, 0.12);
}

.loader-circle {
  width: 48px;
  height: 48px;
  border: 3px solid #e5e7eb;
  border-top-color: #0f172a;
  border-radius: 50%;
  margin: 0 auto 24px;
  animation: spin 1s linear infinite;
}

.loading-quote {
  margin-top: 18px;
  padding: 14px 16px;
  border-left: 3px solid #0f172a;
  background: #f9fafb;
  text-align: left;
}

.loading-quote p {
  margin: 0;
  color: #0f172a;
  font-size: 0.94rem;
  font-weight: 700;
  line-height: 1.7;
  font-style: italic;
}

.loading-quote span {
  display: block;
  margin-top: 8px;
  color: #6b7280;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 800;
}

.loading-back-btn {
  margin-top: 18px;
  width: 100%;
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 12px;
  color: #0f172a;
  padding: 12px 16px;
  font-size: 0.9rem;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s;
}

.loading-back-btn:hover {
  background: #f9fafb;
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
  color: #9ca3af;
  font-size: 0.9rem;
  transition: color 0.2s;
}

.step-item.active {
  color: #0f172a;
  font-weight: 700;
}

.step-item.done {
  color: #059669;
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
  color: #d1d5db;
  letter-spacing: 0.2em;
}

@media (max-width: 1024px) {
  .grid-layout {
    grid-template-columns: 1fr;
  }
  .header-actions {
    width: 100%;
    align-items: flex-start;
  }
  .compare-selector {
    max-width: none;
  }
}

/* Editorial: 缓存提示用左侧色条，无渐变无阴影 */
.analysis-cache-banner {
  margin-bottom: 18px;
  padding: 12px 18px;
  border-left: 3px solid #d97706;
  background: #fffbeb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  color: #92400e;
}

.analysis-cache-copy {
  display: grid;
  gap: 4px;
}

.analysis-cache-copy strong {
  font-size: 0.88rem;
  line-height: 1.6;
}

.analysis-cache-badge {
  width: fit-content;
  padding: 4px 10px;
  background: #fef3c7;
  color: #92400e;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid #fcd34d;
}

.analysis-cache-time {
  white-space: nowrap;
  font-size: 0.78rem;
  font-weight: 700;
  color: #b45309;
}

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

.compare-subtitle {
  margin: 6px 0 0;
  font-size: 0.84rem;
  line-height: 1.5;
  color: #6b7280;
}

.compare-count {
  min-width: 44px;
  text-align: center;
}

@media (max-width: 1180px) {
  .analysis-cache-banner {
    display: grid;
  }
  .analysis-cache-time {
    white-space: normal;
  }
}
</style>


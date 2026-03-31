<template>
  <div class="analysis-detail">
    <header class="page-header">
      <div class="stock-info" v-if="stockData">
        <h1 class="stock-name">{{ getSymbolName(stockData.symbol) }} 深度分析矩阵</h1>
        <div class="badges">
          <span class="badge color-pe">PE: {{ mainPercentiles?.pe.current }}</span>
          <span class="badge color-pb">PB: {{ mainPercentiles?.pb.current }}</span>
          <span class="badge color-dy">DY: {{ mainPercentiles?.dy?.current }}%</span>
          <span class="badge" :class="getScoreClass(analysisData?.f_score.score)">
            F-Score: {{ analysisData?.f_score.score }}/10
          </span>
        </div>
      </div>
      <div class="header-actions">
        <!-- 股票对比多选 (Glassmorphism UI) -->
        <div class="compare-selector" v-if="sentimentStore.sentimentData.length > 1">
          <div class="glass-header">
            <span class="label">叠加对比矩阵 (Max 4)</span>
            <span class="count">{{ compareSymbols.length }}/4</span>
          </div>
          <div class="compare-grid">
            <label 
              v-for="s in availableStocks" 
              :key="s.stock_symbol"
              class="glass-pill"
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
      <!-- 1. 深度对比图表 -->
      <section class="section chart-section">
        <div class="section-header">
          <div class="title-group">
            <h2>{{ activeMetric.toUpperCase() }} 多维叠加对比 (10年期)</h2>
            <p class="subtitle">同步月线对齐 | 最高支持 4 家</p>
          </div>
          <div class="chart-tabs">
            <button v-for="t in ['pe', 'pb', 'roi', 'dy']" :key="t" 
                    :class="{ active: activeMetric === t }"
                    @click="activeMetric = t">
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
        </div>
      </section>

      <div class="grid-layout">
        <!-- 2. F-Score 安全性矩阵 -->
        <section class="section safety-section">
          <h2>安全性排雷矩阵 (F-Score)</h2>
          <div class="f-score-matrix">
            <div v-for="item in analysisData.f_score.details" :key="item.name" class="matrix-item">
              <span class="matrix-name">{{ item.name }}</span>
              <span class="matrix-val">{{ item.val }}</span>
              <span class="matrix-status" :class="{ passed: item.passed }">
                {{ item.passed ? '✅' : '❌' }}
              </span>
            </div>
          </div>
          <p class="section-footer">得分为 7-9 代表极度安全，0-3 可能存在价值陷阱。</p>
        </section>

        <!-- 3. 内在价值锚点测算 -->
        <section class="section fair-value-section">
          <h2>内在价值锚点测算</h2>
          <div class="calculator">
            <div class="input-group">
              <label>预期 ROE (%)</label>
              <input type="number" v-model="calcParams.expectedRoe" step="0.5" />
            </div>
            <div class="input-group">
              <label>要求回报率 (%)</label>
              <input type="number" v-model="calcParams.requiredReturn" step="1" />
            </div>
            <div class="result-box">
              <div class="res-item">
                <span class="res-label">公允 PB 锚点:</span>
                <span class="res-val">{{ fairPb }}</span>
              </div>
              <div class="res-item main-res">
                <span class="res-label">内在估值建议:</span>
                <span class="res-val">{{ fairValuation }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import * as echarts from 'echarts';
import axios from 'axios';
import { useSentimentStore } from '@/stores/sentiment';

const route = useRoute();
const sentimentStore = useSentimentStore();
const symbol = route.params.symbol as string;

const loading = ref(true);
const analysisData = ref<any>(null);
const compareDataMap = ref<Record<string, any>>({});
const stockData = ref<any>(null);
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

const mainPercentiles = computed(() => analysisData.value?.percentiles);

onMounted(async () => {
  if (sentimentStore.sentimentData.length === 0) {
    await sentimentStore.fetchLatestSentiment();
  }
  await fetchData();
  initChart();
});

const fetchData = async () => {
  loading.value = true;
  currentStep.value = 0;
  try {
    // Step 0: Start
    await new Promise(r => setTimeout(r, 600));
    
    // Step 1: Fetch main data
    currentStep.value = 1;
    const res = await axios.get(`http://localhost:8000/api/sentiment/analysis/?symbol=${symbol}`);
    analysisData.value = res.data;
    calcParams.value.expectedRoe = res.data.forward.expected_roe;
    stockData.value = { symbol: res.data.symbol };

    // Step 2: F-Score & Details
    currentStep.value = 2;
    await new Promise(r => setTimeout(r, 400));

    // Step 3: Fair Value
    currentStep.value = 3;
    if (compareSymbols.value.length > 0) {
      const requests = compareSymbols.value.map(s => 
        axios.get(`http://localhost:8000/api/sentiment/analysis/?symbol=${s}`)
      );
      const results = await Promise.all(requests);
      const newMap: Record<string, any> = {};
      results.forEach((r, idx) => {
        newMap[compareSymbols.value[idx]] = r.data;
      });
      compareDataMap.value = newMap;
    } else {
      compareDataMap.value = {};
    }

    // Step 4: Finalizing
    currentStep.value = 4;
    await new Promise(r => setTimeout(r, 500));
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const fairPb = computed(() => {
  return (calcParams.value.expectedRoe / calcParams.value.requiredReturn).toFixed(2);
});

const fairValuation = computed(() => {
  const currentPb = mainPercentiles.value?.pb.current || 1;
  const ratio = parseFloat(fairPb.value) / currentPb;
  if (ratio > 1.2) return '深度低估 (推荐)';
  if (ratio < 0.8) return '估值虚高 (回避)';
  return '估值合理';
});

const isUnderValued = computed(() => {
  const p = mainPercentiles.value?.[activeMetric.value];
  if (!p) return false;
  // DY 指标是越大越安全，其他是越小越安全
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

const getSymbolName = (s: string) => {
  return sentimentStore.sentimentData.find(item => item.stock_symbol === s)?.stock_name || s;
};

const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

const initChart = () => {
  if (!chartRef.value || !analysisData.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);
  
  const metric = activeMetric.value;
  const mainP = mainPercentiles.value[metric];
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

  // 2. 对比线数据 (采用公司名)
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

watch(compareSymbols, () => {
  fetchData();
}, { deep: true });
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
  background: rgba(255, 255, 255, 0.9); /* 提高不透明度 */
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
  background: #f1f5f9; /* 明显的底色 */
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
</style>

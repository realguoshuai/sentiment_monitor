<template>
  <div class="terminal-page">
    <div class="history-container">
      <header class="terminal-hero">
        <div>
          <p class="light-hero-kicker">回测复盘</p>
          <div class="hero-title-row">
            <h1 class="light-hero-title">{{ stockName }} 回测复盘</h1>
            <span class="light-symbol-chip">{{ symbol }}</span>
          </div>
          <p class="light-hero-subtitle">
            展示低估区买入后的 1/3/5 年收益、PB 分位与未来收益关系、高股息 / 高 ROI / 低 PB 组合表现，以及"情绪极弱 + 估值低"联合信号统计。
          </p>
          <div class="hero-nav">
            <button
              @click="router.push(`/analysis/${symbol}`)"
              class="light-btn-back"
            >
              返回估值分析
            </button>
            <button
              @click="router.push('/')"
              class="light-btn-back light-btn-outline"
            >
              返回首页
            </button>
          </div>
        </div>
        <div v-if="data?.sample_summary" class="hero-stats">
          <div class="terminal-stat">
            <div class="terminal-stat-label">月度样本</div>
            <div class="terminal-stat-value">{{ data.sample_summary.monthly_points }}</div>
          </div>
          <div class="terminal-stat">
            <div class="terminal-stat-label">日度样本</div>
            <div class="terminal-stat-value">{{ data.sample_summary.daily_points }}</div>
          </div>
        </div>
      </header>

      <!-- 当前估值定位 -->
      <div v-if="data?.current_status" class="current-status-card" :class="valuationZoneClass">
        <div class="status-header">
          <div class="zone-badge" :class="valuationZoneClass">{{ valuationZoneLabel }}</div>
          <div>
            <h3 class="status-title">{{ stockName }} 当前估值：{{ valuationZoneLabel }}</h3>
            <p class="status-desc">{{ valuationInterpretation }}</p>
          </div>
        </div>
        <div class="percentile-grid">
          <div class="percentile-item" :class="{ 'signal-active': currentPct.pb_pct <= 20 }">
            <span class="percentile-label">PB 分位</span>
            <span class="percentile-value">{{ formatPercentile(currentPct.pb_pct) }}</span>
            <span class="percentile-hint">{{ zoneHint(currentPct.pb_pct, 'pb') }}</span>
          </div>
          <div class="percentile-item" :class="{ 'signal-active': currentPct.pe_pct <= 20 }">
            <span class="percentile-label">PE 分位</span>
            <span class="percentile-value">{{ formatPercentile(currentPct.pe_pct) }}</span>
            <span class="percentile-hint">{{ zoneHint(currentPct.pe_pct, 'pe') }}</span>
          </div>
          <div class="percentile-item" :class="{ 'signal-active': currentPct.dividend_yield_pct >= 80 }">
            <span class="percentile-label">股息率分位</span>
            <span class="percentile-value">{{ formatPercentile(currentPct.dividend_yield_pct) }}</span>
            <span class="percentile-hint">{{ zoneHint(currentPct.dividend_yield_pct, 'dy') }}</span>
          </div>
          <div class="percentile-item" :class="{ 'signal-active': currentPct.roi_pct >= 80 }">
            <span class="percentile-label">ROI 分位</span>
            <span class="percentile-value">{{ formatPercentile(currentPct.roi_pct) }}</span>
            <span class="percentile-hint">{{ zoneHint(currentPct.roi_pct, 'roi') }}</span>
          </div>
        </div>
        <div v-if="data.current_status.signals.length" class="signal-tags">
          <span v-for="s in data.current_status.signals" :key="s" class="signal-tag">{{ s }}</span>
        </div>
      </div>

      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p class="loading-text">正在复盘历史回测数据...</p>
        <div class="loading-quote">
          <p>"{{ loadingQuote.text }}"</p>
          <span>{{ loadingQuote.author }}</span>
        </div>
      </div>

      <div v-else-if="error" class="terminal-card error-card">
        {{ error }}
      </div>

      <div v-else-if="data" class="content-stack">
        <AlgorithmExplainer title="回测复盘算法说明" :defaultOpen="false">
          <h4>滚动分位数</h4>
          <p>每个时间点的分位数是"截止当日的历史百分位"，不是全局固定值：</p>
          <div class="formula">
            PB分位 = (历史中 ≤ 当前PB的天数) ÷ 总天数 × 100%
          </div>
          <p class="note">例如 PB分位=15 表示当前 PB 处于历史最低 15% 的位置。</p>

          <h4>低估区触发条件（满足任一即可）</h4>
          <ul>
            <li>PB 分位 ≤ 20（历史最低 20%）</li>
            <li>PE 分位 ≤ 20（历史最低 20%）</li>
            <li>股息率分位 ≥ 80（历史最高 20%）</li>
            <li>ROI 分位 ≥ 80（历史最高 20%）</li>
          </ul>

          <h4>优质组合触发条件（同时满足）</h4>
          <ul>
            <li>股息率分位 ≥ 80（高股息）</li>
            <li>ROI 分位 ≥ 80（高资本回报）</li>
            <li>PB 分位 ≤ 20（低估值）</li>
          </ul>

          <h4>情绪极弱 + 估值低触发条件（同时满足）</h4>
          <div class="formula">
            情绪分 ≤ -0.2（情绪极弱）<br/>
            且 满足上述低估区任一条件
          </div>

          <h4>未来收益计算</h4>
          <ul>
            <li>月度数据：1Y = 持有 12 期，3Y = 36 期，5Y = 60 期</li>
            <li>日度数据：5D = 持有 5 期，20D = 20 期</li>
            <li>收益率 = (未来价格 ÷ 当前价格 - 1) × 100%</li>
          </ul>

          <h4>统计指标</h4>
          <ul>
            <li><strong>平均收益</strong>：所有有效样本的算术平均收益率</li>
            <li><strong>中位数收益</strong>：所有有效样本的中位数收益率（更抗极端值）</li>
            <li><strong>胜率</strong>：收益为正的样本占比</li>
          </ul>
        </AlgorithmExplainer>

        <section v-if="data.low_valuation_returns" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div
            v-for="item in lowValuationCards"
            :key="item.key"
            class="terminal-card"
          >
            <div class="inner-label">{{ item.label }}</div>
            <div class="mt-4 text-4xl font-black" :class="valueColor(item.avg_return)">
              {{ formatPct(item.avg_return) }}
            </div>
            <div class="mt-3 text-sm text-slate-500">低估区买入后平均收益</div>
            <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div class="terminal-inner">
                <div class="inner-label">中位数</div>
                <div class="font-bold text-slate-700">{{ formatPct(item.median_return) }}</div>
              </div>
              <div class="terminal-inner">
                <div class="inner-label">胜率</div>
                <div class="font-bold text-slate-700">{{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-4 text-xs text-slate-400">有效样本 {{ item.count }}</div>
          </div>
        </section>

        <section v-if="data.percentile_future_returns" class="terminal-card compact-section">
          <div class="flex items-center justify-between mb-1">
            <div>
              <h2 class="section-title">分位数与未来收益关系</h2>
            </div>
          </div>
          <div ref="bucketChartRef" class="bucket-chart"></div>
          <div class="overflow-x-auto mt-3">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-slate-400 border-b border-slate-100">
                  <th class="py-3">PB 分位区间</th>
                  <th class="py-3">样本数</th>
                  <th class="py-3">1Y</th>
                  <th class="py-3">3Y</th>
                  <th class="py-3">5Y</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="bucket in percentileBuckets" :key="bucket.bucket" class="border-b border-slate-50">
                  <td class="py-3 font-bold text-slate-700">{{ bucket.bucket }}</td>
                  <td class="py-3 text-slate-500">{{ bucket.sample_count }}</td>
                  <td class="py-3" :class="valueColor(bucket['1y'])">{{ formatPct(bucket['1y']) }}</td>
                  <td class="py-3" :class="valueColor(bucket['3y'])">{{ formatPct(bucket['3y']) }}</td>
                  <td class="py-3" :class="valueColor(bucket['5y'])">{{ formatPct(bucket['5y']) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <details class="mt-4 terminal-detail">
            <summary class="detail-summary">
              <span>样本明细</span>
              <span class="detail-hint">{{ percentileSampleCount }} 条</span>
            </summary>
            <div v-if="percentileSamples.length" class="mt-4 overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="text-left text-slate-400 border-b border-slate-200">
                    <th class="py-2">日期</th>
                    <th class="py-2">分桶</th>
                    <th class="py-2">PB 分位</th>
                    <th class="py-2">1Y</th>
                    <th class="py-2">3Y</th>
                    <th class="py-2">5Y</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in percentileSamples" :key="`${item.date}-${item.bucket}`" class="border-b border-slate-100">
                    <td class="py-2 text-slate-600">{{ item.date }}</td>
                    <td class="py-2 font-bold text-slate-700">{{ item.bucket }}</td>
                    <td class="py-2 text-slate-500">{{ formatNumber(item.pb_pct) }}</td>
                    <td class="py-2" :class="valueColor(item.future_return_1y)">{{ formatPct(item.future_return_1y) }}</td>
                    <td class="py-2" :class="valueColor(item.future_return_3y)">{{ formatPct(item.future_return_3y) }}</td>
                    <td class="py-2" :class="valueColor(item.future_return_5y)">{{ formatPct(item.future_return_5y) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="mt-3 text-sm text-slate-500">暂无样本。</p>
          </details>
        </section>

        <section class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div v-if="data.quality_combo_performance" class="terminal-card">
            <h2 class="section-title">高股息 / 高 ROI / 低 PB 组合表现</h2>
            <p class="section-desc">{{ data.quality_combo_performance.definition }}</p>
            <div class="mt-5 grid grid-cols-3 gap-3">
              <div v-for="item in qualityCards" :key="item.key" class="terminal-inner">
                <div class="inner-label">{{ item.label }}</div>
                <div class="mt-3 text-2xl font-black" :class="valueColor(item.avg_return)">{{ formatPct(item.avg_return) }}</div>
                <div class="mt-2 text-xs text-slate-500">胜率 {{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-5 text-sm text-slate-500">信号样本 {{ data.quality_combo_performance.signal_count }}</div>
            <details class="mt-5 terminal-detail">
              <summary class="detail-summary">
                <span>样本明细</span>
                <span class="detail-hint">{{ qualitySamples.length }} 条</span>
              </summary>
              <div v-if="qualitySamples.length" class="mt-4 overflow-x-auto">
                <table class="w-full text-xs">
                  <thead>
                    <tr class="text-left text-slate-400 border-b border-slate-200">
                      <th class="py-2">日期</th>
                      <th class="py-2">价格</th>
                      <th class="py-2">股息率分位</th>
                      <th class="py-2">ROI 分位</th>
                      <th class="py-2">PB 分位</th>
                      <th class="py-2">1Y</th>
                      <th class="py-2">3Y</th>
                      <th class="py-2">5Y</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in qualitySamples" :key="item.date" class="border-b border-slate-100">
                      <td class="py-2 text-slate-600">{{ item.date }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.price) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.dividend_yield_pct) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.roi_pct) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.pb_pct) }}</td>
                      <td class="py-2" :class="valueColor(item.future_return_1y)">{{ formatPct(item.future_return_1y) }}</td>
                      <td class="py-2" :class="valueColor(item.future_return_3y)">{{ formatPct(item.future_return_3y) }}</td>
                      <td class="py-2" :class="valueColor(item.future_return_5y)">{{ formatPct(item.future_return_5y) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="mt-3 text-sm text-slate-500">暂无样本。</p>
            </details>
          </div>

          <div v-if="data.sentiment_value_signal" class="terminal-card">
            <h2 class="section-title">"情绪极弱 + 估值低" 联合信号统计</h2>
            <p class="section-desc">{{ data.sentiment_value_signal.definition }}</p>
            <div class="mt-5 grid grid-cols-2 gap-4">
              <div v-for="item in sentimentCards" :key="item.key" class="terminal-inner">
                <div class="inner-label">{{ item.label }}</div>
                <div class="mt-3 text-2xl font-black" :class="valueColor(item.avg_return)">{{ formatPct(item.avg_return) }}</div>
                <div class="mt-2 text-xs text-slate-500">胜率 {{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-5 text-sm text-slate-500">
              信号样本 {{ data.sentiment_value_signal.sample_count }}
              <span v-if="data.sentiment_value_signal.latest_signal_date">，最近一次触发 {{ data.sentiment_value_signal.latest_signal_date }}</span>
            </div>
            <details class="mt-5 terminal-detail">
              <summary class="detail-summary">
                <span>样本明细</span>
                <span class="detail-hint">{{ sentimentSamples.length }} 条</span>
              </summary>
              <div v-if="sentimentSamples.length" class="mt-4 overflow-x-auto">
                <table class="w-full text-xs">
                  <thead>
                    <tr class="text-left text-slate-400 border-b border-slate-200">
                      <th class="py-2">日期</th>
                      <th class="py-2">情绪分</th>
                      <th class="py-2">标签</th>
                      <th class="py-2">PB 分位</th>
                      <th class="py-2">PE 分位</th>
                      <th class="py-2">股息率分位</th>
                      <th class="py-2">ROI 分位</th>
                      <th class="py-2">5D</th>
                      <th class="py-2">20D</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in sentimentSamples" :key="item.date" class="border-b border-slate-100">
                      <td class="py-2 text-slate-600">{{ item.date }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.sentiment_score, 3) }}</td>
                      <td class="py-2 text-slate-500">{{ item.sentiment_label }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.pb_pct) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.pe_pct) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.dividend_yield_pct) }}</td>
                      <td class="py-2 text-slate-500">{{ formatNumber(item.roi_pct) }}</td>
                      <td class="py-2" :class="valueColor(item.future_return_5d)">{{ formatPct(item.future_return_5d) }}</td>
                      <td class="py-2" :class="valueColor(item.future_return_20d)">{{ formatPct(item.future_return_20d) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p v-else class="mt-3 text-sm text-slate-500">暂无样本。</p>
            </details>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { echarts, type ECharts } from '@/lib/echarts'
import { useSentimentStore } from '@/stores/sentiment'
import { useInvestorLoadingQuotes } from '@/composables/useInvestorLoadingQuotes'
import AlgorithmExplainer from '@/components/AlgorithmExplainer.vue'

interface HorizonStats {
  avg_return: number
  median_return?: number
  win_rate: number
  count?: number
}

interface PercentileBucket {
  bucket: string
  sample_count: number
  '1y': number
  '3y': number
  '5y': number
}

interface PercentileSample {
  date: string
  bucket: string
  pb_pct: number
  future_return_1y: number
  future_return_3y: number
  future_return_5y: number
}

interface QualityComboSample {
  date: string
  price: number
  dividend_yield_pct: number
  roi_pct: number
  pb_pct: number
  future_return_1y: number
  future_return_3y: number
  future_return_5y: number
}

interface SentimentSample {
  date: string
  sentiment_score: number
  sentiment_label: string
  pb_pct: number
  pe_pct: number
  dividend_yield_pct: number
  roi_pct: number
  future_return_5d: number
  future_return_20d: number
}

interface BacktestPayload {
  symbol: string
  cache_status?: 'fresh' | 'stale'
  background_refreshing?: boolean
  sample_summary: { monthly_points: number; daily_points: number }
  methodology: {
    low_valuation: string
    percentile_relation: string
    quality_combo: string
    sentiment_value: string
  }
  low_valuation_returns: { horizons: Record<string, HorizonStats> }
  percentile_future_returns: {
    buckets: PercentileBucket[]
    samples: PercentileSample[]
  }
  quality_combo_performance: {
    definition: string
    signal_count: number
    horizons: Record<string, HorizonStats>
    samples: QualityComboSample[]
  }
  sentiment_value_signal: {
    definition: string
    sample_count: number
    latest_signal_date?: string
    horizons: Record<string, HorizonStats>
    samples: SentimentSample[]
  }
}

const route = useRoute()
const router = useRouter()
const store = useSentimentStore()
const symbol = route.params.symbol as string

const loading = ref(true)
const error = ref('')
const data = ref<BacktestPayload | null>(null)
const { loadingQuote } = useInvestorLoadingQuotes(loading)
const bucketChartRef = ref<HTMLElement | null>(null)
let bucketChart: ECharts | null = null

const stockName = computed(() => {
  return store.getStockBySymbol(symbol)?.stock_name || symbol
})

const methodologyItems = computed(() => {
  const m = data.value?.methodology
  return [
    { key: 'low_valuation', label: '低估区规则', text: m?.low_valuation || '--' },
    { key: 'percentile_relation', label: '分位数规则', text: m?.percentile_relation || '--' },
    { key: 'quality_combo', label: '组合规则', text: m?.quality_combo || '--' },
    { key: 'sentiment_value', label: '情绪联合信号', text: m?.sentiment_value || '--' },
  ]
})

const lowValuationCards = computed(() => {
  const horizons = data.value?.low_valuation_returns?.horizons || {}
  return [
    { key: '1y', label: '1Y', ...horizons['1y'] },
    { key: '3y', label: '3Y', ...horizons['3y'] },
    { key: '5y', label: '5Y', ...horizons['5y'] },
  ]
})

const qualityCards = computed(() => {
  const horizons = data.value?.quality_combo_performance?.horizons || {}
  return [
    { key: '1y', label: '1Y', ...horizons['1y'] },
    { key: '3y', label: '3Y', ...horizons['3y'] },
    { key: '5y', label: '5Y', ...horizons['5y'] },
  ]
})

const sentimentCards = computed(() => {
  const horizons = data.value?.sentiment_value_signal?.horizons || {}
  return [
    { key: '5d', label: '5D', ...horizons['5d'] },
    { key: '20d', label: '20D', ...horizons['20d'] },
  ]
})

const percentileBuckets = computed(() => data.value?.percentile_future_returns?.buckets || [])
const percentileSamples = computed(() => data.value?.percentile_future_returns?.samples || [])
const qualitySamples = computed(() => data.value?.quality_combo_performance?.samples || [])
const sentimentSamples = computed(() => data.value?.sentiment_value_signal?.samples || [])
const percentileSampleCount = computed(() => percentileSamples.value.length)

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return Number(value).toFixed(digits)
}

function formatPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatPercentile(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--'
  return `${value.toFixed(0)}%`
}

function valueColor(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'text-slate-400'
  if (value > 0) return 'text-rose-600'
  if (value < 0) return 'text-emerald-600'
  return 'text-slate-600'
}

const currentPct = computed(() => data.value?.current_status?.current_percentiles ?? {})

// 估值区间判定：基于 PB 分位为主，综合其他指标
const valuationZoneLabel = computed(() => {
  const s = data.value?.current_status
  if (!s) return '--'
  const pb = currentPct.value.pb_pct
  const pe = currentPct.value.pe_pct
  if (pb === null || pb === undefined) return '数据不足'
  // 综合 PB 和 PE 分位，取更保守的那个
  const ref = (pe !== null && pe !== undefined && pe < pb) ? pe : pb
  if (ref <= 10) return '极度低估'
  if (ref <= 25) return '低估'
  if (ref <= 40) return '偏低'
  if (ref <= 60) return '合理'
  if (ref <= 75) return '偏高'
  if (ref <= 90) return '高估'
  return '极度高估'
})

const valuationZoneClass = computed(() => {
  const label = valuationZoneLabel.value
  if (label === '极度低估' || label === '低估') return 'zone-low'
  if (label === '偏低') return 'zone-slightly-low'
  if (label === '合理') return 'zone-fair'
  if (label === '偏高') return 'zone-slightly-high'
  if (label === '高估' || label === '极度高估') return 'zone-high'
  return ''
})

const valuationInterpretation = computed(() => {
  const s = data.value?.current_status
  if (!s) return ''
  const pb = currentPct.value.pb_pct
  const pe = currentPct.value.pe_pct
  const dy = currentPct.value.dividend_yield_pct
  const roi = currentPct.value.roi_pct
  const label = valuationZoneLabel.value

  const parts: string[] = []
  if (pb !== null && pb !== undefined) {
    parts.push(`PB 处于历史 ${pb}% 分位`)
  }
  if (pe !== null && pe !== undefined) {
    parts.push(`PE 处于历史 ${pe}% 分位`)
  }

  let advice = ''
  if (label === '极度低估') {
    advice = '估值处于历史极低位置，安全边际充足，是少见的买入窗口。'
  } else if (label === '低估') {
    advice = '估值偏低，历史上这个位置买入后收益较好。'
  } else if (label === '偏低') {
    advice = '估值略低于中位数，不算贵但安全边际一般。'
  } else if (label === '合理') {
    advice = '估值在合理区间，不贵也不便宜，适合持有观望。'
  } else if (label === '偏高') {
    advice = '估值偏高，历史上这个位置买入后收益偏低。'
  } else if (label === '高估' || label === '极度高估') {
    advice = '估值处于历史高位，追高风险较大，建议谨慎。'
  }

  // 如果有优质组合信号，补充说明
  if (s.is_quality_combo) {
    advice += ' 同时满足高股息+高ROI+低PB的优质组合条件。'
  }

  return `${parts.join('，')}。${advice}`
})

function zoneHint(pct: number | null | undefined, type: string) {
  if (pct === null || pct === undefined) return '--'
  if (type === 'pb' || type === 'pe') {
    // 低分位 = 低估（好）
    if (pct <= 10) return '极低'
    if (pct <= 25) return '低估'
    if (pct <= 40) return '偏低'
    if (pct <= 60) return '中位'
    if (pct <= 75) return '偏高'
    if (pct <= 90) return '高'
    return '极高'
  }
  // 股息率和ROI：高分位 = 好
  if (pct >= 90) return '极高'
  if (pct >= 75) return '偏高'
  if (pct >= 60) return '中位'
  if (pct >= 40) return '偏低'
  if (pct >= 25) return '低'
  return '极低'
}

function renderBucketChart() {
  if (!bucketChartRef.value || !percentileBuckets.value.length) return
  if (!bucketChart) {
    bucketChart = echarts.init(bucketChartRef.value)
  }

  bucketChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['1Y', '3Y', '5Y'],
      top: 0,
      textStyle: { color: '#64748b' },
    },
    grid: { left: 32, right: 12, top: 24, bottom: 12 },
    xAxis: {
      type: 'category',
      data: percentileBuckets.value.map((item: any) => item.bucket),
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#64748b',
        formatter: '{value}%',
      },
      splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } },
    },
    series: [
      {
        name: '1Y',
        type: 'bar',
        barMaxWidth: 38,
        barCategoryGap: '18%',
        data: percentileBuckets.value.map((item: any) => item['1y']),
        itemStyle: { color: '#6366f1' },
      },
      {
        name: '3Y',
        type: 'bar',
        barMaxWidth: 38,
        barGap: '6%',
        data: percentileBuckets.value.map((item: any) => item['3y']),
        itemStyle: { color: '#14b8a6' },
      },
      {
        name: '5Y',
        type: 'bar',
        barMaxWidth: 38,
        barGap: '6%',
        data: percentileBuckets.value.map((item: any) => item['5y']),
        itemStyle: { color: '#f59e0b' },
      },
    ],
  })
}

function handleResize() {
  bucketChart?.resize()
}

onMounted(async () => {
  try {
    if (!store.stocks.length) {
      await store.fetchStocks()
    }
    if (!store.sentimentData.length) {
      await store.fetchLatestSentiment()
    }

    const cachedBacktest = store.backtestCache[symbol]?.data
    if (cachedBacktest) {
      data.value = cachedBacktest
      loading.value = false
      await nextTick()
      renderBucketChart()
      if (data.value!.cache_status === 'stale') {
         void store.getBacktest(symbol, true).then(res => {
            data.value = res
            renderBucketChart()
         })
      } else if (data.value!.cache_status === 'error') {
         error.value = '数据获取失败，请稍后重试。'
      }
      window.addEventListener('resize', handleResize)
      return
    }
    const res = await store.getBacktest(symbol)
    data.value = res
    if (res.cache_status === 'error') error.value = '数据获取失败，请稍后重试。'
    await nextTick()
    renderBucketChart()
    window.addEventListener('resize', handleResize)
  } catch (e: any) {
    error.value = e.response?.data?.error || '历史回撤数据加载失败'
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  bucketChart?.dispose()
})
</script>

<style scoped>
/* Terminal Dense 浅色版: 紧凑布局 + 等宽字体 + 浅色系（已统一为现代圆角浅色风） */
.terminal-page {
  background:
    radial-gradient(ellipse at 15% 0%, rgba(99, 102, 241, 0.06), transparent 40%),
    radial-gradient(ellipse at 85% 0%, rgba(14, 165, 233, 0.05), transparent 35%),
    radial-gradient(ellipse at 50% 100%, rgba(16, 185, 129, 0.03), transparent 30%),
    linear-gradient(180deg, #f8fafc 0%, #f0f4f8 100%);
  color: #0f172a;
  min-height: 100vh;
}

.history-container {
  max-width: 80rem;
  margin: 0 auto;
  padding: 0 16px;
}

.hero-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
}

.hero-nav {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.light-btn-outline {
  background: rgba(255, 255, 255, 0.6);
  color: #475569;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
}

.light-btn-outline:hover {
  background: #f8fafc;
  border-color: #94a3b8;
  color: #0f172a;
  box-shadow: 0 2px 8px -4px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.hero-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  min-width: 240px;
}

.terminal-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 24px;
  padding: 24px 28px;
  margin-bottom: 20px;
  box-shadow: 0 16px 40px -28px rgba(15, 23, 42, 0.12);
}

.terminal-stat {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px 16px;
  text-align: center;
  box-shadow: 0 2px 8px -4px rgba(15, 23, 42, 0.04);
}

.terminal-stat-label {
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', monospace;
}

.terminal-stat-value {
  font-size: 1.6rem;
  font-weight: 900;
  color: #0f172a;
  margin-top: 2px;
  font-family: 'Monaco', 'Menlo', monospace;
}

.content-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bucket-chart {
  height: 220px;
  margin-top: 4px;
}

.compact-section {
  padding: 14px 18px;
}

.section-desc {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  margin: 0;
  font-family: 'Monaco', 'Menlo', monospace;
}

.terminal-card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 18px;
  padding: 18px 20px;
  box-shadow: 0 6px 24px -8px rgba(15, 23, 42, 0.06), 0 2px 6px rgba(15, 23, 42, 0.03);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
}

.terminal-card:hover {
  box-shadow: 0 10px 32px -8px rgba(15, 23, 42, 0.1), 0 3px 8px rgba(15, 23, 42, 0.05);
}

.terminal-inner {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.terminal-inner:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.inner-label {
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94a3b8;
  font-family: 'Monaco', 'Menlo', monospace;
}

.terminal-detail {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 14px;
  padding: 14px 18px;
  transition: border-color 0.2s ease;
}

.terminal-detail:hover {
  border-color: #cbd5e1;
}

.detail-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 800;
  color: #0f172a;
  font-size: 0.85rem;
}

.detail-hint {
  font-size: 0.65rem;
  font-family: 'Monaco', 'Menlo', monospace;
  color: #94a3b8;
}

.error-card {
  color: #991b1b;
  background: #fef2f2;
  border-color: #fecaca;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 96px 0;
}

.loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #0f172a;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-text {
  margin-top: 16px;
  color: #64748b;
  font-weight: 700;
  font-size: 0.85rem;
  font-family: 'Monaco', 'Menlo', monospace;
}

.loading-quote {
  margin-top: 18px;
  max-width: 480px;
  padding: 14px 18px;
  border-left: 3px solid #0f172a;
  background: #f8fafc;
  text-align: left;
}

.loading-quote p {
  margin: 0;
  color: #0f172a;
  font-size: 0.88rem;
  font-weight: 700;
  line-height: 1.6;
  font-style: italic;
}

.loading-quote span {
  display: block;
  margin-top: 8px;
  color: #64748b;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 800;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.current-status-card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-left: 4px solid #94a3b8;
  border-radius: 18px;
  padding: 20px 24px;
  box-shadow: 0 6px 24px -8px rgba(15, 23, 42, 0.06), 0 2px 6px rgba(15, 23, 42, 0.03);
}

.current-status-card.zone-low {
  border-left-color: #16a34a;
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.current-status-card.zone-slightly-low {
  border-left-color: #65a30d;
  border-color: #d9f99d;
  background: #f7fee7;
}

.current-status-card.zone-fair {
  border-left-color: #3b82f6;
  border-color: #bfdbfe;
  background: #eff6ff;
}

.current-status-card.zone-slightly-high {
  border-left-color: #d97706;
  border-color: #fde68a;
  background: #fffbeb;
}

.current-status-card.zone-high {
  border-left-color: #dc2626;
  border-color: #fecaca;
  background: #fef2f2;
}

.zone-badge {
  padding: 4px 12px;
  font-size: 0.78rem;
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}

.zone-badge.zone-low {
  background: #dcfce7;
  color: #166534;
}

.zone-badge.zone-slightly-low {
  background: #ecfccb;
  color: #3f6212;
}

.zone-badge.zone-fair {
  background: #dbeafe;
  color: #1e40af;
}

.zone-badge.zone-slightly-high {
  background: #fef3c7;
  color: #92400e;
}

.zone-badge.zone-high {
  background: #fee2e2;
  color: #991b1b;
}

.status-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.status-title {
  font-size: 1rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px;
}

.status-desc {
  font-size: 0.82rem;
  color: #475569;
  margin: 0;
  line-height: 1.6;
}

.percentile-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 14px;
}

.percentile-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
  text-align: center;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.percentile-item:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.percentile-item.signal-active {
  background: #f0fdf4;
  border-color: #16a34a;
  box-shadow: 0 2px 8px -4px rgba(22, 163, 74, 0.15);
}

.percentile-label {
  display: block;
  font-size: 0.6rem;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-family: 'Monaco', 'Menlo', monospace;
}

.percentile-value {
  display: block;
  font-size: 1.1rem;
  font-weight: 900;
  color: #0f172a;
  margin-top: 2px;
  font-family: 'Monaco', 'Menlo', monospace;
}

.signal-active .percentile-value {
  color: #d97706;
}

.is-quality .signal-active .percentile-value {
  color: #16a34a;
}

.percentile-hint {
  display: block;
  font-size: 0.6rem;
  font-weight: 700;
  color: #94a3b8;
  margin-top: 2px;
}

.signal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.signal-tag {
  padding: 4px 12px;
  font-size: 0.7rem;
  font-weight: 700;
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
}

:deep(table) {
  border-collapse: collapse;
}

:deep(th) {
  color: #94a3b8;
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-family: 'Monaco', 'Menlo', monospace;
  padding: 8px 10px;
  border-bottom: 2px solid #e2e8f0;
  text-align: left;
}

:deep(td) {
  font-size: 0.78rem;
  font-family: 'Monaco', 'Menlo', monospace;
  padding: 6px 10px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

:deep(tr:hover) {
  background: #f8fafc;
}

@media (max-width: 768px) {
  .hero-stats {
    grid-template-columns: 1fr;
  }
  .hero-title-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .percentile-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

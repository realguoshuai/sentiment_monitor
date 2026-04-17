<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <div class="max-w-7xl mx-auto px-6 py-8">
      <header class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-8">
        <div>
          <div class="flex items-center gap-3 mb-3">
            <button
              @click="router.push(`/analysis/${symbol}`)"
              class="px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-100 transition"
            >
              返回深度分析
            </button>
            <button
              @click="router.push('/')"
              class="px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-100 transition"
            >
              返回首页
            </button>
          </div>
          <h1 class="text-3xl font-black text-slate-900">
            {{ stockName }} 历史回撤与信号复盘
          </h1>
          <p class="text-sm text-slate-500 mt-2">
            展示低估区买入后的 1/3/5 年收益、PB 分位与未来收益关系、高股息 / 高 ROI / 低 PB 组合表现，以及“情绪极弱 + 估值低”联合信号统计。
          </p>
        </div>
        <div v-if="data?.sample_summary" class="grid grid-cols-2 gap-3">
          <div class="bg-white border border-slate-200 rounded-2xl px-4 py-3 shadow-sm">
            <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Monthly Samples</div>
            <div class="text-2xl font-black text-slate-800">{{ data.sample_summary.monthly_points }}</div>
          </div>
          <div class="bg-white border border-slate-200 rounded-2xl px-4 py-3 shadow-sm">
            <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Daily Samples</div>
            <div class="text-2xl font-black text-slate-800">{{ data.sample_summary.daily_points }}</div>
          </div>
        </div>
      </header>

      <div v-if="loading" class="py-24 text-center">
        <div class="w-12 h-12 mx-auto border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin"></div>
        <p class="mt-4 text-slate-500 font-bold">正在计算历史回撤统计...</p>
        <div class="mt-5 max-w-xl mx-auto rounded-2xl border border-slate-200 bg-white/80 px-5 py-4 shadow-sm">
          <p class="text-slate-700 font-bold leading-7">“{{ loadingQuote.text }}”</p>
          <p class="mt-2 text-[11px] tracking-[0.22em] uppercase text-slate-400 font-black">{{ loadingQuote.author }}</p>
        </div>
      </div>

      <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-2xl px-6 py-5 text-red-700">
        {{ error }}
      </div>

      <div v-else-if="data" class="space-y-8">
        <section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h2 class="text-xl font-black text-slate-900">算法说明</h2>
              <p class="text-sm text-slate-500 mt-1">当前页面所有统计都直接来自后端公开规则。</p>
              <div class="mt-4 grid grid-cols-1 gap-3">
                <div
                  v-for="item in methodologyItems"
                  :key="item.key"
                  class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
                >
                  <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">{{ item.label }}</div>
                  <div class="mt-2 text-sm text-slate-700 leading-6">{{ item.text }}</div>
                </div>
              </div>
            </div>
            <details open class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4">
              <summary class="cursor-pointer list-none flex items-center justify-between text-slate-900 font-black">
                <span>样本说明</span>
                <span class="text-xs font-mono text-slate-400">click to fold</span>
              </summary>
              <div class="mt-4 space-y-3 text-sm text-slate-600 leading-6">
                <p>1. 月度样本来自 10 年历史序列，用于低估区、分位数关系和组合表现统计。</p>
                <p>2. 日度样本来自近 365 天价格序列，与舆情数据按日期对齐，用于“情绪极弱 + 估值低”统计。</p>
                <p>3. 下方每个模块都附带了样本明细，可以直接展开查看具体日期和指标。</p>
              </div>
            </details>
          </div>
        </section>

        <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div
            v-for="item in lowValuationCards"
            :key="item.key"
            class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6"
          >
            <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">{{ item.label }}</div>
            <div class="mt-4 text-4xl font-black" :class="valueColor(item.avg_return)">
              {{ formatPct(item.avg_return) }}
            </div>
            <div class="mt-3 text-sm text-slate-500">低估区买入后平均收益</div>
            <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div class="bg-slate-50 rounded-xl px-3 py-2">
                <div class="text-slate-400 text-[10px] uppercase">Median</div>
                <div class="font-bold text-slate-700">{{ formatPct(item.median_return) }}</div>
              </div>
              <div class="bg-slate-50 rounded-xl px-3 py-2">
                <div class="text-slate-400 text-[10px] uppercase">Win Rate</div>
                <div class="font-bold text-slate-700">{{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-4 text-xs text-slate-400">有效样本 {{ item.count }}</div>
          </div>
        </section>

        <section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-xl font-black text-slate-900">分位数与未来收益关系</h2>
              <p class="text-sm text-slate-500 mt-1">按 PB 分位数分桶，观察不同估值区间对应的未来 1/3/5 年收益。</p>
            </div>
          </div>
          <div ref="bucketChartRef" class="h-[260px] md:h-[290px]"></div>
          <div class="overflow-x-auto mt-4">
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
          <details class="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <summary class="cursor-pointer list-none flex items-center justify-between font-black text-slate-900">
              <span>样本明细</span>
              <span class="text-xs font-mono text-slate-400">{{ percentileSampleCount }} rows</span>
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
          <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
            <h2 class="text-xl font-black text-slate-900">高股息 / 高 ROI / 低 PB 组合表现</h2>
            <p class="text-sm text-slate-500 mt-1">{{ data.quality_combo_performance.definition }}</p>
            <div class="mt-5 grid grid-cols-3 gap-3">
              <div v-for="item in qualityCards" :key="item.key" class="bg-slate-50 rounded-2xl p-4">
                <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">{{ item.label }}</div>
                <div class="mt-3 text-2xl font-black" :class="valueColor(item.avg_return)">{{ formatPct(item.avg_return) }}</div>
                <div class="mt-2 text-xs text-slate-500">胜率 {{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-5 text-sm text-slate-500">信号样本 {{ data.quality_combo_performance.signal_count }}</div>
            <details class="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <summary class="cursor-pointer list-none flex items-center justify-between font-black text-slate-900">
                <span>样本明细</span>
                <span class="text-xs font-mono text-slate-400">{{ qualitySamples.length }} rows</span>
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

          <div class="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
            <h2 class="text-xl font-black text-slate-900">“情绪极弱 + 估值低” 联合信号统计</h2>
            <p class="text-sm text-slate-500 mt-1">{{ data.sentiment_value_signal.definition }}</p>
            <div class="mt-5 grid grid-cols-2 gap-4">
              <div v-for="item in sentimentCards" :key="item.key" class="bg-slate-50 rounded-2xl p-4">
                <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">{{ item.label }}</div>
                <div class="mt-3 text-2xl font-black" :class="valueColor(item.avg_return)">{{ formatPct(item.avg_return) }}</div>
                <div class="mt-2 text-xs text-slate-500">胜率 {{ formatPct(item.win_rate) }}</div>
              </div>
            </div>
            <div class="mt-5 text-sm text-slate-500">
              信号样本 {{ data.sentiment_value_signal.sample_count }}
              <span v-if="data.sentiment_value_signal.latest_signal_date">，最近一次触发 {{ data.sentiment_value_signal.latest_signal_date }}</span>
            </div>
            <details class="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <summary class="cursor-pointer list-none flex items-center justify-between font-black text-slate-900">
                <span>样本明细</span>
                <span class="text-xs font-mono text-slate-400">{{ sentimentSamples.length }} rows</span>
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
import { stockApi } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'
import { useInvestorLoadingQuotes } from '@/composables/useInvestorLoadingQuotes'

const route = useRoute()
const router = useRouter()
const store = useSentimentStore()
const symbol = route.params.symbol as string

const loading = ref(true)
const error = ref('')
const data = ref<any>(null)
const { loadingQuote } = useInvestorLoadingQuotes(loading)
const bucketChartRef = ref<HTMLElement | null>(null)
let bucketChart: ECharts | null = null

const stockName = computed(() => {
  return store.sentimentData.find(item => item.stock_symbol === symbol)?.stock_name || symbol
})

const methodologyItems = computed(() => {
  const methodology = data.value?.methodology || {}
  return [
    { key: 'low_valuation', label: '低估区规则', text: methodology.low_valuation || '--' },
    { key: 'percentile_relation', label: '分位数规则', text: methodology.percentile_relation || '--' },
    { key: 'quality_combo', label: '组合规则', text: methodology.quality_combo || '--' },
    { key: 'sentiment_value', label: '情绪联合信号', text: methodology.sentiment_value || '--' },
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

function valueColor(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'text-slate-400'
  if (value > 0) return 'text-rose-600'
  if (value < 0) return 'text-emerald-600'
  return 'text-slate-600'
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
    grid: { left: 32, right: 12, top: 36, bottom: 18 },
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
    if (!store.sentimentData.length) {
      await store.fetchLatestSentiment()
    }
    const response = await stockApi.getHistoryBacktest(symbol)
    data.value = response.data
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

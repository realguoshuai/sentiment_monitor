<template>
  <div class="screener-shell">
    <!-- 顶部栏 -->
    <header class="topbar">
      <div class="topbar-title">
        <button class="icon-btn" type="button" title="返回首页" @click="router.push('/')">←</button>
        <h1>条件选股工作台</h1>
        <span class="status-dot" :class="{ ready: screenerMeta.ready }"></span>
        <span class="topbar-meta">{{ screenerMeta.count || 0 }} 只 / {{ screenerMeta.industry_count || 0 }} 行业</span>
        <span v-if="screenerMeta.ready && screenerMeta.snapshot_date" class="snapshot-date-label">📸 {{ screenerMeta.snapshot_date }}</span>
      </div>
      <div class="topbar-actions">
        <button class="primary-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '刷新快照' }}
        </button>
      </div>
    </header>

    <!-- 横向筛选条 -->
    <form class="filter-bar" @submit.prevent="applyFilters(1)">
      <div class="filter-row">
        <input v-model.trim="filters.q" class="filter-input search-input" placeholder="搜索名称 / 代码" />

        <div class="filter-group">
          <label><span>PB ≤</span><input v-model.number="filters.pb_max" type="number" step="0.1" placeholder="--" /></label>
          <label><span>PE ≤</span><input v-model.number="filters.pe_max" type="number" step="0.1" placeholder="--" /></label>
          <label><span>ROE ≥</span><input v-model.number="filters.roe_min" type="number" step="0.5" placeholder="--" /></label>
          <label><span>股息率 ≥</span><input v-model.number="filters.dividend_yield_min" type="number" step="0.1" placeholder="--" /></label>
          <label><span>市值 ≥</span><input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="--" /><span class="unit">亿</span></label>
          <label><span>净现比 ≥</span><input v-model.number="filters.net_cash_ratio_min" type="number" step="0.1" placeholder="--" /></label>
          <label><span>现金流收益 ≥</span><input v-model.number="filters.cfo_yield_min" type="number" step="0.5" placeholder="--" /><span class="unit">%</span></label>
        </div>

        <div class="filter-actions">
          <button class="primary-btn" type="submit" :disabled="loading">筛选</button>
          <button class="secondary-btn" type="button" @click="resetFilters">重置</button>
        </div>
      </div>

      <div class="filter-row-secondary">
        <div class="preset-pills">
          <span class="preset-label">策略：</span>
          <button
            v-for="preset in presetCards"
            :key="preset.key"
            class="preset-pill"
            :class="`preset-${preset.tone}`"
            type="button"
            @click="applyPreset(preset.key)"
          >
            {{ preset.title }}
            <small>{{ preset.metrics.join(' / ') }}</small>
          </button>
        </div>

        <div class="sort-controls">
          <select v-model="filters.sort_by" class="filter-select">
            <option value="pb">PB</option>
            <option value="pe">PE</option>
            <option value="roe">ROE</option>
            <option value="roi">ROI</option>
            <option value="dividend_yield">股息率</option>
            <option value="market_cap">总市值</option>
            <option value="price">价格</option>
            <option value="net_cash_ratio">净现比</option>
            <option value="cfo_yield">现金流收益率</option>
          </select>
          <button class="sort-dir-btn" type="button" @click="filters.sort_order = filters.sort_order === 'asc' ? 'desc' : 'asc'; applyFilters(1)">
            {{ filters.sort_order === 'asc' ? '↑ 升序' : '↓ 降序' }}
          </button>
          <label class="toggle-label">
            <input v-model="filters.include_anomalies" type="checkbox" />
            <span>含异常</span>
          </label>
        </div>
      </div>

      <div v-if="activeFilterTags.length" class="active-tags">
        <span v-for="tag in activeFilterTags" :key="tag" class="active-tag">{{ tag }}</span>
      </div>
    </form>

    <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

    <!-- 结果区 -->
    <main class="main-area">
      <!-- 空状态 -->
      <div v-if="!screenerMeta.ready" class="empty-state">
        <strong>还没有可用快照</strong>
        <p>先刷新一次全市场快照，之后就可以连续筛选和排序。</p>
        <button class="primary-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '立即生成快照' }}
        </button>
      </div>

      <div v-else-if="loading" class="empty-state">
        <strong>正在更新候选池</strong>
        <p>当前只查询本地快照，不会重新抓取全市场数据。</p>
      </div>

      <div v-else-if="!results.length" class="empty-state">
        <strong>当前没有命中结果</strong>
        <p>建议先放宽 PB、PE 或股息率阈值，再重新筛选。</p>
        <button class="secondary-btn" type="button" @click="resetFilters">回到默认视图</button>
      </div>

      <template v-else>
        <!-- 统计条 -->
        <div class="stats-bar">
          <div class="stat-item">
            <span>命中</span><strong>{{ pagination.total }}</strong>
          </div>
          <div class="stat-item">
            <span>低 PB</span><strong>{{ valuationBuckets.lowPb }}</strong>
          </div>
          <div class="stat-item">
            <span>高股息</span><strong>{{ valuationBuckets.highDividend }}</strong>
          </div>
          <div class="stat-item">
            <span>高 ROE</span><strong>{{ valuationBuckets.highRoe }}</strong>
          </div>
          <div class="stat-item">
            <span>已监控</span><strong>{{ monitoredCount }}</strong>
          </div>
          <div class="stat-item">
            <span>排序</span><strong>{{ activeSortLabel }}</strong>
          </div>
        </div>

        <!-- 表格 -->
        <div class="table-shell">
          <table class="result-table">
            <thead>
              <tr>
                <th>公司</th>
                <th class="action-col">动作</th>
                <th><button class="sort-header" type="button" @click="toggleSort('price')">价格/市值 <span :class="{ active: filters.sort_by === 'price' }">{{ getSortIndicator('price') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('pe')">PE <span :class="{ active: filters.sort_by === 'pe' }">{{ getSortIndicator('pe') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('pb')">PB <span :class="{ active: filters.sort_by === 'pb' }">{{ getSortIndicator('pb') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('roe')">ROE <span :class="{ active: filters.sort_by === 'roe' }">{{ getSortIndicator('roe') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('roi')">ROI <span :class="{ active: filters.sort_by === 'roi' }">{{ getSortIndicator('roi') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('dividend_yield')">股息率 <span :class="{ active: filters.sort_by === 'dividend_yield' }">{{ getSortIndicator('dividend_yield') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('net_cash_ratio')">净现比 <span :class="{ active: filters.sort_by === 'net_cash_ratio' }">{{ getSortIndicator('net_cash_ratio') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('cfo_yield')">现金流收益 <span :class="{ active: filters.sort_by === 'cfo_yield' }">{{ getSortIndicator('cfo_yield') }}</span></button></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in results" :key="row.symbol">
                <td>
                  <div class="company-cell">
                    <strong>{{ row.name }}</strong>
                    <span v-if="row.is_monitored" class="monitor-badge">监控</span>
                    <div class="company-sub">
                      <span class="symbol-badge">{{ row.symbol }}</span>
                      <span v-if="row.industry" class="industry-badge">{{ row.industry }}</span>
                    </div>
                  </div>
                </td>
                <td class="action-col">
                  <div class="row-actions">
                    <button class="mini-btn" type="button" @click="openAnalysis(row.symbol)">分析</button>
                    <button class="mini-btn primary" type="button" @click="addToMonitor(row)" :disabled="row.is_monitored || addLoadingSymbol === row.symbol">
                      {{ row.is_monitored ? '已监控' : (addLoadingSymbol === row.symbol ? '...' : '加入') }}
                    </button>
                  </div>
                </td>
                <td>
                  <div class="price-cell">
                    <strong>{{ formatPrice(row.price) }}</strong>
                    <small>{{ formatMarketCap(row.market_cap) }}</small>
                  </div>
                </td>
                <td><span class="metric-pill" :class="getMetricTone('pe', row.pe)">{{ formatNumber(row.pe) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('pb', row.pb)">{{ formatNumber(row.pb) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('roe', row.roe_pct)">{{ formatPctValue(row.roe_pct) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('roi', row.roi_pct)">{{ formatPctValue(row.roi_pct) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('dividend', row.dividend_yield)">{{ formatPct(row.dividend_yield) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('net_cash_ratio', row.net_cash_ratio)">{{ formatNumber(row.net_cash_ratio) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('cfo_yield', row.cfo_yield)">{{ formatPct(row.cfo_yield) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pager">
          <button class="secondary-btn" type="button" @click="goToPage(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">上一页</button>
          <span>第 {{ pagination.page }} / {{ pagination.total_pages || 1 }} 页</span>
          <button class="secondary-btn" type="button" @click="goToPage(pagination.page + 1)" :disabled="pagination.page >= pagination.total_pages || loading">下一页</button>
        </div>

        <!-- 底部洞察 -->
        <div class="insight-row">
          <section class="insight-card">
            <h3>优先研究</h3>
            <div v-if="topIdeas.length" class="idea-list">
              <article v-for="idea in topIdeas" :key="idea.symbol" class="idea-card">
                <div class="idea-head">
                  <div>
                    <strong>{{ idea.name }}</strong>
                    <span>{{ idea.symbol }} · {{ idea.industry || '未分类' }}</span>
                  </div>
                  <b>{{ idea.score }}</b>
                </div>
                <div class="idea-reasons">
                  <span v-for="reason in idea.reasons" :key="reason">{{ reason }}</span>
                </div>
                <div class="idea-actions">
                  <button class="mini-btn" type="button" @click="openAnalysis(idea.symbol)">分析</button>
                  <button class="mini-btn primary" type="button" @click="addToMonitor(idea)" :disabled="idea.is_monitored || addLoadingSymbol === idea.symbol">
                    {{ idea.is_monitored ? '已监控' : '加入' }}
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="side-empty">拿到结果后，这里会自动列出更值得先看的标的。</p>
          </section>

          <section class="insight-card">
            <h3>行业分布</h3>
            <div v-if="industryHighlights.length" class="industry-list">
              <div v-for="item in industryHighlights" :key="item.name" class="industry-row">
                <div class="industry-label">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.count }} 只</span>
                </div>
                <div class="industry-bar-track">
                  <div class="industry-bar-fill" :style="{ width: `${item.ratio}%` }"></div>
                </div>
              </div>
            </div>
            <p v-else class="side-empty">当前结果还不足以观察行业分布。</p>
          </section>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { stockApi, type ScreenerMeta, type ScreenerResult } from '@/api'

type ScreenerPreset = 'dividend_value' | 'quality_value' | 'cash_cow'
type SortableField = 'price' | 'pe' | 'pb' | 'roe' | 'roi' | 'dividend_yield' | 'market_cap' | 'net_cash_ratio' | 'cfo_yield'

const router = useRouter()

const screenerMeta = ref<ScreenerMeta>({
  ready: false,
  snapshot_date: '',
  count: 0,
  industry_count: 0,
  roe_basis_label: '年报 ROE / 现价股息率 / ROI',
})

const results = ref<ScreenerResult[]>([])
const loading = ref(false)
const refreshing = ref(false)
const addLoadingSymbol = ref('')
const errorMessage = ref('')

const pagination = reactive({
  page: 1,
  page_size: 50,
  total: 0,
  total_pages: 0,
})

const filters = reactive({
  q: '',
  pb_max: null as number | null,
  pe_max: null as number | null,
  roe_min: null as number | null,
  dividend_yield_min: null as number | null,
  market_cap_min_100m: null as number | null,
  net_cash_ratio_min: null as number | null,
  cfo_yield_min: null as number | null,
  include_anomalies: false,
  sort_by: 'pb',
  sort_order: 'asc',
})

const presetCards: Array<{
  key: ScreenerPreset
  title: string
  tagline: string
  description: string
  metrics: string[]
  tone: 'income' | 'quality' | 'steady'
}> = [
  {
    key: 'dividend_value',
    title: '低估高股息',
    tagline: 'Preset 01',
    description: '先找估值有缓冲、现金回报也不差的成熟公司。',
    metrics: ['PB ≤ 1.5', 'PE ≤ 15', '股息率 ≥ 4%'],
    tone: 'income',
  },
  {
    key: 'quality_value',
    title: '高 ROE 价值',
    tagline: 'Preset 02',
    description: '先看回报质量，再看价格是否还在可接受区间。',
    metrics: ['PB ≤ 3', 'PE ≤ 25', 'ROE ≥ 15%'],
    tone: 'quality',
  },
  {
    key: 'cash_cow',
    title: '现金奶牛',
    tagline: 'Preset 03',
    description: '偏向高利润含金量的现金流丰沛企业。',
    metrics: ['ROE ≥ 12%', '净现比 ≥ 1.0', '现金流收益率 ≥ 6%'],
    tone: 'steady',
  },
]

const sortLabelMap: Record<string, string> = {
  pb: 'PB',
  pe: 'PE',
  roe: 'ROE',
  roi: 'ROI',
  dividend_yield: '股息率',
  market_cap: '总市值',
  price: '价格',
  net_cash_ratio: '净现比',
  cfo_yield: '现金流收益率',
}

const defaultSortOrderMap: Record<SortableField, 'asc' | 'desc'> = {
  price: 'desc',
  pe: 'asc',
  pb: 'asc',
  roe: 'desc',
  roi: 'desc',
  dividend_yield: 'desc',
  market_cap: 'desc',
  net_cash_ratio: 'desc',
  cfo_yield: 'desc',
}

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.q.trim()) count += 1
  if (filters.pb_max !== null) count += 1
  if (filters.pe_max !== null) count += 1
  if (filters.roe_min !== null) count += 1
  if (filters.dividend_yield_min !== null) count += 1
  if (filters.market_cap_min_100m !== null) count += 1
  if (filters.net_cash_ratio_min !== null) count += 1
  if (filters.cfo_yield_min !== null) count += 1
  if (filters.include_anomalies) count += 1
  return count
})

const activeSortLabel = computed(() => {
  const field = sortLabelMap[filters.sort_by] || filters.sort_by
  const direction = filters.sort_order === 'asc' ? '升序' : '降序'
  return `${field} · ${direction}`
})

const coverageDensityLabel = computed(() => {
  const total = Number(pagination.total || 0)
  const industries = new Set(results.value.map((item) => item.industry).filter(Boolean)).size
  if (!total || !industries) return '--'
  return `${(total / industries).toFixed(1)} 只/行业`
})

const activeFilterTags = computed(() => {
  const tags: string[] = []
  if (filters.q.trim()) tags.push(`搜索 ${filters.q.trim()}`)
  if (filters.pb_max !== null) tags.push(`PB ≤ ${filters.pb_max}`)
  if (filters.pe_max !== null) tags.push(`PE ≤ ${filters.pe_max}`)
  if (filters.roe_min !== null) tags.push(`ROE ≥ ${filters.roe_min}%`)
  if (filters.dividend_yield_min !== null) tags.push(`股息率 ≥ ${filters.dividend_yield_min}%`)
  if (filters.market_cap_min_100m !== null) tags.push(`市值 ≥ ${filters.market_cap_min_100m} 亿`)
  if (filters.net_cash_ratio_min !== null) tags.push(`净现比 ≥ ${filters.net_cash_ratio_min}`)
  if (filters.cfo_yield_min !== null) tags.push(`现金流收益率 ≥ ${filters.cfo_yield_min}%`)
  if (filters.include_anomalies) tags.push('包含异常样本')
  return tags
})

const monitoredCount = computed(() => results.value.filter((item) => item.is_monitored).length)

const valuationBuckets = computed(() => ({
  lowPb: results.value.filter((item) => Number(item.pb) > 0 && Number(item.pb) <= 1.5).length,
  highDividend: results.value.filter((item) => Number(item.dividend_yield) >= 5).length,
  highRoe: results.value.filter((item) => Number(item.roe_pct) >= 15).length,
}))

const industryHighlights = computed(() => {
  const counts = new Map<string, number>()

  for (const row of results.value) {
    const key = row.industry || '未分类'
    counts.set(key, (counts.get(key) || 0) + 1)
  }

  const maxCount = Math.max(...Array.from(counts.values()), 0)
  return Array.from(counts.entries())
    .map(([name, count]) => ({
      name,
      count,
      ratio: maxCount ? Math.max(16, (count / maxCount) * 100) : 0,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
})

const topIdeas = computed(() => {
  const scored = results.value.map((row) => {
    let score = 0
    const reasons: string[] = []

    const pb = Number(row.pb)
    const pe = Number(row.pe)
    const roe = Number(row.roe_pct)
    const dividend = Number(row.dividend_yield)
    const roi = Number(row.roi_pct)

    if (!Number.isNaN(pb) && pb > 0) {
      if (pb <= 1.5) {
        score += 30
        reasons.push(`PB ${pb.toFixed(2)}`)
      } else if (pb <= 2.5) {
        score += 16
      }
    }

    if (!Number.isNaN(pe) && pe > 0) {
      if (pe <= 15) {
        score += 22
        reasons.push(`PE ${pe.toFixed(1)}`)
      } else if (pe <= 22) {
        score += 10
      }
    }

    if (!Number.isNaN(roe)) {
      if (roe >= 18) {
        score += 28
        reasons.push(`ROE ${roe.toFixed(1)}%`)
      } else if (roe >= 12) {
        score += 14
      }
    }

    if (!Number.isNaN(dividend)) {
      if (dividend >= 5) {
        score += 18
        reasons.push(`股息率 ${dividend.toFixed(1)}%`)
      } else if (dividend >= 3) {
        score += 8
      }
    }

    if (!Number.isNaN(roi) && roi >= 10) {
      score += 10
      reasons.push(`ROI ${roi.toFixed(1)}%`)
    }

    if (row.is_monitored) {
      score += 4
    }

    return {
      ...row,
      score,
      reasons: reasons.slice(0, 3),
    }
  })

  return scored
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
})

const buildParams = (page = 1) => ({
  q: filters.q || undefined,
  pb_max: filters.pb_max ?? undefined,
  pe_max: filters.pe_max ?? undefined,
  roe_min: filters.roe_min ?? undefined,
  dividend_yield_min: filters.dividend_yield_min ?? undefined,
  market_cap_min: filters.market_cap_min_100m ? filters.market_cap_min_100m * 1e8 : undefined,
  net_cash_ratio_min: filters.net_cash_ratio_min ?? undefined,
  cfo_yield_min: filters.cfo_yield_min ?? undefined,
  include_anomalies: filters.include_anomalies ? 1 : undefined,
  sort_by: filters.sort_by,
  sort_order: filters.sort_order,
  page,
  page_size: pagination.page_size,
})

const fetchResults = async (page = 1) => {
  loading.value = true
  errorMessage.value = ''

  try {
    const res = await stockApi.getScreenerResults(buildParams(page))
    screenerMeta.value = res.data.meta
    results.value = res.data.results
    pagination.page = res.data.pagination.page
    pagination.page_size = res.data.pagination.page_size
    pagination.total = res.data.pagination.total
    pagination.total_pages = res.data.pagination.total_pages
  } catch (error) {
    console.error('Failed to fetch screener results:', error)
    errorMessage.value = '选股结果拉取失败，请稍后重试。'
    results.value = []
  } finally {
    loading.value = false
  }
}

const applyFilters = async (page = 1) => {
  await fetchResults(page)
}

let refreshAbortController: AbortController | null = null

const refreshSnapshot = async () => {
  // 取消之前的轮询（如果有）
  refreshAbortController?.abort()
  refreshAbortController = new AbortController()
  const signal = refreshAbortController.signal

  refreshing.value = true
  errorMessage.value = ''

  try {
    const res = await stockApi.refreshScreenerSnapshot()
    const data = res.data || {}

    if (data.status === 'started' || data.status === 'refreshing') {
      // 异步刷新已启动，轮询等待完成
      errorMessage.value = ''
      let consecutiveErrors = 0
      for (let i = 0; i < 120; i++) {
        if (signal.aborted) return
        await new Promise(r => setTimeout(r, 3000))
        if (signal.aborted) return
        try {
          const poll = await stockApi.pollScreenerRefresh()
          consecutiveErrors = 0
          const pollData = poll.data || {}
          if (pollData.status === 'done') {
            if (pollData.source !== 'upstream' && pollData.message) {
              errorMessage.value = pollData.message
            }
            break
          }
          if (pollData.status === 'error') {
            errorMessage.value = `快照刷新失败：${pollData.error || '未知错误'}`
            break
          }
          // status === 'refreshing' → 继续轮询
        } catch {
          if (signal.aborted) return
          if (++consecutiveErrors >= 5) {
            errorMessage.value = '轮询连接中断，请稍后重试'
            break
          }
        }
      }
      if (!signal.aborted && refreshing.value) {
        errorMessage.value = '刷新超时（6 分钟），后台仍在执行，稍后可查看结果'
      }
    } else {
      // 同步返回（旧路径或已完成）
      if (data.source !== 'upstream' && data.message) {
        errorMessage.value = data.message
      }
    }

    if (!signal.aborted) await fetchResults(1)
  } catch (error: any) {
    if (signal.aborted) return
    console.error('Failed to refresh screener snapshot:', error)
    const detail = error?.response?.data?.error || error?.response?.data?.message || error?.message || ''
    errorMessage.value = `快照刷新失败：${detail || '网络请求异常，请检查后端是否运行'}`
  } finally {
    if (!signal.aborted) refreshing.value = false
  }
}

const resetFilters = () => {
  filters.q = ''
  filters.pb_max = null
  filters.pe_max = null
  filters.roe_min = null
  filters.dividend_yield_min = null
  filters.market_cap_min_100m = null
  filters.net_cash_ratio_min = null
  filters.cfo_yield_min = null
  filters.include_anomalies = false
  filters.sort_by = 'pb'
  filters.sort_order = 'asc'
  void fetchResults(1)
}

const applyPreset = (preset: ScreenerPreset) => {
  filters.q = ''
  filters.pb_max = null
  filters.pe_max = null
  filters.roe_min = null
  filters.dividend_yield_min = null
  filters.market_cap_min_100m = null
  filters.net_cash_ratio_min = null
  filters.cfo_yield_min = null
  filters.include_anomalies = false
  filters.sort_by = 'pb'
  filters.sort_order = 'asc'

  if (preset === 'dividend_value') {
    filters.pb_max = 1.5
    filters.pe_max = 15
    filters.dividend_yield_min = 4
  }

  if (preset === 'quality_value') {
    filters.pb_max = 3
    filters.pe_max = 25
    filters.roe_min = 15
    filters.sort_by = 'roe'
    filters.sort_order = 'desc'
  }

  if (preset === 'cash_cow') {
    filters.roe_min = 12
    filters.net_cash_ratio_min = 1.0
    filters.cfo_yield_min = 6
    filters.sort_by = 'cfo_yield'
    filters.sort_order = 'desc'
  }

  void fetchResults(1)
}

const addToMonitor = async (row: ScreenerResult) => {
  addLoadingSymbol.value = row.symbol

  try {
    await stockApi.createStock({
      symbol: row.symbol,
      name: row.name,
      keywords: [row.name, row.symbol.slice(2)],
      industry: row.industry || '',
      peer_symbols: [],
    })
    row.is_monitored = true
  } catch (error) {
    console.error('Failed to add screener row to monitor list:', error)
  } finally {
    addLoadingSymbol.value = ''
  }
}

const openAnalysis = (symbol: string) => {
  router.push(`/analysis/${symbol}`)
}

const goToPage = (page: number) => {
  if (page < 1 || page > pagination.total_pages || loading.value) return
  void fetchResults(page)
}

const formatPrice = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value)) || Number(value) <= 0) return '--'
  return Number(value).toFixed(2)
}

const hasMissingMetric = (value?: number | null) => {
  if (value === undefined || value === null) return true
  const numeric = Number(value)
  return Number.isNaN(numeric) || numeric === 0
}

const formatNumber = (value?: number | null) => {
  if (hasMissingMetric(value)) return '--'
  return Number(value).toFixed(2)
}

const formatPct = (value?: number | null) => {
  if (hasMissingMetric(value)) return '--'
  return `${Number(value).toFixed(1)}%`
}

const formatPctValue = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return '--'
  return `${Number(value).toFixed(1)}%`
}

const formatMarketCap = (value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value)) || Number(value) <= 0) return '--'
  return `${(Number(value) / 1e8).toFixed(0)} 亿`
}

const toggleSort = (field: SortableField) => {
  if (filters.sort_by === field) {
    filters.sort_order = filters.sort_order === 'asc' ? 'desc' : 'asc'
  } else {
    filters.sort_by = field
    filters.sort_order = defaultSortOrderMap[field]
  }

  void fetchResults(1)
}

const getSortIndicator = (field: SortableField) => {
  if (filters.sort_by !== field) return '↕'
  return filters.sort_order === 'asc' ? '↑' : '↓'
}

const getMetricTone = (metric: 'pb' | 'pe' | 'roe' | 'roi' | 'dividend' | 'net_cash_ratio' | 'cfo_yield', value?: number | null) => {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return 'tone-muted'
  const numeric = Number(value)

  if (metric === 'pb') {
    if (numeric <= 1.5) return 'tone-cheap'
    if (numeric <= 3) return 'tone-neutral'
    return 'tone-warm'
  }

  if (metric === 'pe') {
    if (numeric <= 15) return 'tone-cheap'
    if (numeric <= 25) return 'tone-neutral'
    return 'tone-warm'
  }

  if (metric === 'roe') {
    if (numeric >= 20) return 'tone-strong'
    if (numeric >= 12) return 'tone-quality'
    return 'tone-muted'
  }

  if (metric === 'roi') {
    if (numeric >= 10) return 'tone-quality'
    if (numeric >= 5) return 'tone-neutral'
    return 'tone-muted'
  }

  if (metric === 'net_cash_ratio') {
    if (numeric >= 1.2) return 'tone-strong'
    if (numeric >= 1.0) return 'tone-quality'
    if (numeric <= 0) return 'tone-warm'
    return 'tone-neutral'
  }

  if (metric === 'cfo_yield') {
    if (numeric >= 8) return 'tone-strong'
    if (numeric >= 5) return 'tone-quality'
    if (numeric <= 2) return 'tone-muted'
    return 'tone-neutral'
  }

  if (numeric >= 5) return 'tone-income'
  if (numeric >= 3) return 'tone-neutral'
  return 'tone-muted'
}

onMounted(() => {
  void fetchResults(1)
})

onUnmounted(() => {
  refreshAbortController?.abort()
})
</script>

<style scoped>
.screener-shell {
  --bg: #f8fafc;
  --ink: #0f172a;
  --muted: #64748b;
  --faint: #94a3b8;
  --line: #e2e8f0;
  --accent: #0f766e;
  --accent-dark: #0b5f59;
  --danger: #b42318;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  padding: 16px 20px;
  max-width: 1600px;
  margin: 0 auto;
}

/* 顶部栏 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.topbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar-title h1 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d97706;
}

.status-dot.ready {
  background: #16a34a;
}

.topbar-meta {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 600;
}

.snapshot-date-label {
  font-size: 0.78rem;
  color: var(--primary, #0088ff);
  font-weight: 500;
}

/* 横向筛选条 */
.filter-bar {
  background: #fff;
  border: 1px solid var(--line);
  padding: 12px 16px;
  margin-bottom: 12px;
  display: grid;
  gap: 10px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.search-input {
  width: 180px;
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex: 1;
}

.filter-group label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--muted);
  white-space: nowrap;
}

.filter-group label span {
  color: var(--faint);
  font-size: 0.72rem;
}

.filter-group input,
.filter-input {
  width: 64px;
  height: 32px;
  border: 1px solid var(--line);
  padding: 0 8px;
  font-size: 0.82rem;
  background: #f8fafc;
  color: var(--ink);
}

.filter-group input:focus,
.filter-input:focus {
  outline: none;
  border-color: var(--accent);
}

.search-input {
  height: 32px;
  border: 1px solid var(--line);
  padding: 0 10px;
  font-size: 0.82rem;
  background: #fff;
  color: var(--ink);
}

.unit {
  font-size: 0.7rem;
  color: var(--faint);
}

.filter-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.filter-row-secondary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.preset-pills {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--faint);
}

.preset-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--line);
  background: #f8fafc;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
  transition: background 0.15s;
}

.preset-pill:hover {
  background: #f1f5f9;
}

.preset-pill small {
  font-size: 0.68rem;
  color: var(--faint);
  font-weight: 600;
}

.preset-income { border-left: 3px solid #f59e0b; }
.preset-quality { border-left: 3px solid #10b981; }
.preset-steady { border-left: 3px solid #3b82f6; }

.sort-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-select {
  height: 32px;
  border: 1px solid var(--line);
  padding: 0 8px;
  font-size: 0.78rem;
  background: #f8fafc;
  color: var(--ink);
}

.sort-dir-btn {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--line);
  background: #f8fafc;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--ink);
  cursor: pointer;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: var(--muted);
  cursor: pointer;
}

.toggle-label input {
  accent-color: var(--accent);
}

.active-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.active-tag {
  padding: 3px 8px;
  font-size: 0.7rem;
  font-weight: 700;
  background: #f1f5f9;
  color: var(--muted);
  border: 1px solid var(--line);
}

/* 按钮 */
.icon-btn,
.primary-btn,
.secondary-btn,
.mini-btn {
  border: 1px solid var(--line);
  cursor: pointer;
  font-weight: 700;
  transition: background 0.15s;
}

.icon-btn {
  width: 32px;
  height: 32px;
  background: #fff;
  color: var(--ink);
  font-size: 1rem;
  display: grid;
  place-items: center;
}

.primary-btn {
  height: 32px;
  padding: 0 14px;
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-size: 0.82rem;
}

.secondary-btn,
.mini-btn {
  height: 30px;
  padding: 0 10px;
  background: #fff;
  color: var(--ink);
  font-size: 0.78rem;
}

.mini-btn.primary {
  background: #ecfdf5;
  border-color: #99f6e4;
  color: var(--accent-dark);
}

.primary-btn:hover { background: var(--accent-dark); }
.secondary-btn:hover { background: #f8fafc; }
.mini-btn:hover { background: #f8fafc; }

.primary-btn:disabled,
.secondary-btn:disabled,
.mini-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 错误 */
.error-banner {
  padding: 10px 14px;
  margin-bottom: 12px;
  color: var(--danger);
  background: #fff7ed;
  border: 1px solid #fed7aa;
  font-size: 0.85rem;
  font-weight: 700;
}

/* 主区域 */
.main-area {
  display: grid;
  gap: 12px;
}

/* 统计条 */
.stats-bar {
  display: flex;
  gap: 2px;
  background: #fff;
  border: 1px solid var(--line);
  overflow: hidden;
}

.stat-item {
  flex: 1;
  padding: 10px 14px;
  display: grid;
  gap: 2px;
  border-right: 1px solid var(--line);
}

.stat-item:last-child {
  border-right: 0;
}

.stat-item span {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--faint);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.stat-item strong {
  font-size: 1rem;
  font-weight: 900;
  color: var(--ink);
}

/* 表格 */
.table-shell {
  overflow: auto;
  max-height: calc(100vh - 380px);
  min-height: 400px;
  border: 1px solid var(--line);
  background: #fff;
}

.result-table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
}

.result-table th,
.result-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f1f5f9;
  text-align: left;
  vertical-align: middle;
  white-space: nowrap;
}

.result-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f8fafc;
  color: var(--faint);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.result-table th:first-child,
.result-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  background: #fff;
}

.result-table th:first-child {
  z-index: 3;
  background: #f8fafc;
}

.result-table th.action-col,
.result-table td.action-col {
  position: sticky;
  left: 160px;
  z-index: 1;
  background: #fff;
}

.result-table th.action-col {
  z-index: 3;
  background: #f8fafc;
}

.result-table tbody tr:hover td {
  background: #f8fbfd;
}

.result-table tbody tr:hover td:first-child,
.result-table tbody tr:hover td.action-col {
  background: #f8fbfd;
}

.sort-header {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sort-header span {
  color: var(--faint);
  margin-left: 2px;
}

.sort-header span.active {
  color: var(--accent);
}

.company-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.company-cell strong {
  font-size: 0.85rem;
  color: var(--ink);
}

.company-sub {
  display: flex;
  gap: 4px;
  align-items: center;
}

.symbol-badge,
.industry-badge,
.monitor-badge {
  padding: 1px 5px;
  font-size: 0.68rem;
  font-weight: 700;
  border: 1px solid var(--line);
  background: #f8fafc;
  color: var(--muted);
}

.monitor-badge {
  color: var(--accent-dark);
  border-color: #99f6e4;
  background: #ecfdf5;
}

.row-actions {
  display: flex;
  gap: 4px;
}

.price-cell {
  display: grid;
  gap: 2px;
}

.price-cell strong {
  font-size: 0.85rem;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.price-cell small {
  font-size: 0.68rem;
  color: var(--faint);
  font-weight: 700;
}

.metric-pill {
  display: inline-flex;
  min-width: 44px;
  justify-content: center;
  padding: 3px 6px;
  border-radius: 999px;
  font-weight: 800;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  border: 1px solid var(--line);
  background: #f8fafc;
  color: var(--muted);
}

.tone-cheap, .tone-income, .tone-strong, .tone-quality {
  background: #ecfdf5;
  border-color: #99f6e4;
  color: #047857;
}

.tone-neutral {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.tone-warm {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #b45309;
}

.tone-muted {
  background: #f8fafc;
  color: var(--faint);
}

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--muted);
  font-size: 0.82rem;
}

/* 空状态 */
.empty-state {
  min-height: 300px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  text-align: center;
  color: var(--muted);
  border: 1px dashed var(--line);
  background: #fff;
}

.empty-state strong {
  color: var(--ink);
  font-size: 1rem;
}

.empty-state p {
  margin: 0;
  max-width: 360px;
  line-height: 1.6;
  font-size: 0.88rem;
}

/* 底部洞察 */
.insight-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.insight-card {
  background: #fff;
  border: 1px solid var(--line);
  padding: 14px 16px;
  display: grid;
  gap: 12px;
}

.insight-card h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 800;
  color: var(--ink);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}

.idea-list {
  display: grid;
  gap: 8px;
}

.idea-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--line);
  background: #f8fafc;
}

.idea-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.idea-head div {
  display: grid;
  gap: 2px;
}

.idea-head strong {
  font-size: 0.85rem;
  color: var(--ink);
}

.idea-head span {
  font-size: 0.72rem;
  color: var(--muted);
}

.idea-head b {
  min-width: 32px;
  height: 24px;
  display: inline-grid;
  place-items: center;
  background: #ecfdf5;
  color: var(--accent-dark);
  font-size: 0.75rem;
  font-weight: 800;
}

.idea-reasons {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.idea-reasons span {
  padding: 2px 6px;
  font-size: 0.68rem;
  font-weight: 700;
  background: #fff;
  border: 1px solid var(--line);
  color: var(--muted);
}

.idea-actions {
  display: flex;
  gap: 4px;
}

.industry-list {
  display: grid;
  gap: 8px;
}

.industry-row {
  display: grid;
  gap: 4px;
}

.industry-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
}

.industry-label strong {
  color: var(--ink);
}

.industry-label span {
  color: var(--faint);
  font-size: 0.72rem;
}

.industry-bar-track {
  height: 6px;
  overflow: hidden;
  background: #edf2f7;
}

.industry-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #38bdf8);
}

.side-empty {
  margin: 0;
  color: var(--faint);
  font-size: 0.82rem;
}

/* 响应式 */
@media (max-width: 1040px) {
  .filter-group {
    display: none;
  }

  .insight-row {
    grid-template-columns: 1fr;
  }

  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .table-shell {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .screener-shell {
    padding: 10px;
  }

  .stats-bar {
    flex-wrap: wrap;
  }

  .stat-item {
    flex: 0 0 50%;
    border-bottom: 1px solid var(--line);
  }

  .result-table {
    min-width: 0;
  }

  .result-table thead {
    display: none;
  }

  .result-table,
  .result-table tbody,
  .result-table tr,
  .result-table td {
    display: block;
    width: 100%;
  }

  .result-table tr {
    border-bottom: 1px solid var(--line);
    padding: 8px 0;
  }

  .result-table td,
  .result-table td:first-child,
  .result-table td.action-col {
    position: static;
    display: flex;
    justify-content: space-between;
    gap: 14px;
    border-bottom: 0;
    box-shadow: none;
    white-space: normal;
  }

  .result-table td::before {
    content: attr(data-label);
    color: var(--faint);
    font-weight: 800;
    font-size: 0.72rem;
  }
}
</style>

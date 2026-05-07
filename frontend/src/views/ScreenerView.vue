<template>
  <div class="screener-shell">
    <header class="topbar">
      <div class="topbar-title">
        <button class="icon-btn" type="button" title="返回首页" @click="router.push('/')">←</button>
        <div>
          <span class="eyebrow">Stock Screener</span>
          <h1>条件选股工作台</h1>
        </div>
      </div>

      <div class="topbar-actions">
        <span class="status-dot" :class="{ ready: screenerMeta.ready }"></span>
        <span class="topbar-meta">快照 {{ screenerMeta.snapshot_date || '--' }}</span>
        <button class="primary-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '刷新全市场快照' }}
        </button>
      </div>
    </header>

    <main class="screener-workspace">
      <aside class="filter-panel panel">
        <div class="panel-head compact">
          <div>
            <span class="eyebrow">Controls</span>
            <h2>筛选条件</h2>
          </div>
          <button class="text-btn" type="button" @click="resetFilters">重置</button>
        </div>

        <form class="filter-form" @submit.prevent="applyFilters(1)">
          <label class="field full">
            <span>名称 / 代码</span>
            <input v-model.trim="filters.q" placeholder="银行 / 600000 / 贵州茅台" />
          </label>

          <div class="field-pair">
            <label class="field">
              <span>PB ≤</span>
              <input v-model.number="filters.pb_max" type="number" step="0.1" placeholder="1.5" />
            </label>
            <label class="field">
              <span>PE ≤</span>
              <input v-model.number="filters.pe_max" type="number" step="0.1" placeholder="15" />
            </label>
          </div>

          <div class="field-pair">
            <label class="field">
              <span>ROE ≥</span>
              <input v-model.number="filters.roe_min" type="number" step="0.5" placeholder="12" />
            </label>
            <label class="field">
              <span>股息率 ≥</span>
              <input v-model.number="filters.dividend_yield_min" type="number" step="0.1" placeholder="4" />
            </label>
          </div>

          <label class="field full">
            <span>市值 ≥（亿）</span>
            <input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="100" />
          </label>

          <div class="field-pair">
            <label class="field">
              <span>排序字段</span>
              <select v-model="filters.sort_by">
                <option value="pb">PB</option>
                <option value="pe">PE</option>
                <option value="roe">ROE</option>
                <option value="roi">ROI</option>
                <option value="dividend_yield">股息率</option>
                <option value="market_cap">总市值</option>
                <option value="price">价格</option>
              </select>
            </label>
            <label class="field">
              <span>排序方向</span>
              <select v-model="filters.sort_order">
                <option value="asc">升序</option>
                <option value="desc">降序</option>
              </select>
            </label>
          </div>

          <label class="toggle-row">
            <input v-model="filters.include_anomalies" type="checkbox" />
            <span>包含异常估值样本</span>
          </label>

          <button class="primary-btn full" type="submit" :disabled="loading">开始筛选</button>
        </form>

        <section class="preset-section">
          <div class="section-label">策略预设</div>
          <button
            v-for="preset in presetCards"
            :key="preset.key"
            class="preset-card"
            :class="`preset-${preset.tone}`"
            type="button"
            @click="applyPreset(preset.key)"
          >
            <div>
              <span>{{ preset.tagline }}</span>
              <strong>{{ preset.title }}</strong>
            </div>
            <p>{{ preset.metrics.join(' / ') }}</p>
          </button>
        </section>
      </aside>

      <section class="main-panel">
        <section class="summary-grid">
          <article class="metric-card panel">
            <span>快照状态</span>
            <strong>{{ screenerMeta.ready ? '可筛选' : '未准备' }}</strong>
            <p>{{ screenerMeta.count || 0 }} 只股票 / {{ screenerMeta.industry_count || 0 }} 个行业</p>
          </article>
          <article class="metric-card panel">
            <span>当前命中</span>
            <strong>{{ pagination.total }}</strong>
            <p>第 {{ pagination.page }} / {{ pagination.total_pages || 1 }} 页</p>
          </article>
          <article class="metric-card panel">
            <span>筛选强度</span>
            <strong>{{ activeFilterCount }} 项</strong>
            <p>{{ activeFilterCount ? coverageDensityLabel : '全市场浏览模式' }}</p>
          </article>
          <article class="metric-card panel">
            <span>排序</span>
            <strong>{{ activeSortLabel }}</strong>
            <p>{{ screenerMeta.roe_basis_label || '年报 ROE / 现价股息率 / ROI' }}</p>
          </article>
        </section>

        <div v-if="errorMessage" class="error-banner panel">{{ errorMessage }}</div>

        <section class="result-panel panel">
          <div class="result-toolbar">
            <div>
              <span class="eyebrow">Candidates</span>
              <h2>候选股票池</h2>
            </div>
            <div class="result-actions">
              <span v-if="loading" class="loading-chip">筛选中...</span>
              <span v-else class="loading-chip muted">{{ pagination.total }} 条结果</span>
            </div>
          </div>

          <div class="active-tag-row">
            <span v-for="tag in activeFilterTags" :key="tag" class="active-tag">{{ tag }}</span>
            <span v-if="!activeFilterTags.length" class="active-tag muted">当前没有额外筛选条件</span>
          </div>

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
            <div class="table-summary">
              <div>
                <strong>本页 {{ results.length }} 只</strong>
                <span>低 PB {{ valuationBuckets.lowPb }} / 高股息 {{ valuationBuckets.highDividend }} / 高 ROE {{ valuationBuckets.highRoe }}</span>
              </div>
            </div>

            <div class="table-shell">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>公司</th>
                    <th class="action-col">动作</th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('price')">
                        价格 / 市值 <span :class="{ active: filters.sort_by === 'price' }">{{ getSortIndicator('price') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('pe')">
                        PE <span :class="{ active: filters.sort_by === 'pe' }">{{ getSortIndicator('pe') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('pb')">
                        PB <span :class="{ active: filters.sort_by === 'pb' }">{{ getSortIndicator('pb') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('roe')">
                        ROE <span :class="{ active: filters.sort_by === 'roe' }">{{ getSortIndicator('roe') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('roi')">
                        ROI <span :class="{ active: filters.sort_by === 'roi' }">{{ getSortIndicator('roi') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('dividend_yield')">
                        股息率 <span :class="{ active: filters.sort_by === 'dividend_yield' }">{{ getSortIndicator('dividend_yield') }}</span>
                      </button>
                    </th>
                  </tr>
                </thead>

                <tbody>
                  <tr v-for="row in results" :key="row.symbol">
                    <td data-label="公司">
                      <div class="company-cell">
                        <div class="company-mainline">
                          <strong>{{ row.name }}</strong>
                          <span v-if="row.is_monitored" class="monitor-badge">已监控</span>
                        </div>
                        <div class="company-subline">
                          <span class="symbol-badge">{{ row.symbol }}</span>
                          <span v-if="row.industry" class="industry-badge">{{ row.industry }}</span>
                        </div>
                      </div>
                    </td>
                    <td class="action-col" data-label="动作">
                      <div class="row-actions">
                        <button class="mini-btn" type="button" @click="openAnalysis(row.symbol)">分析</button>
                        <button
                          class="mini-btn primary"
                          type="button"
                          @click="addToMonitor(row)"
                          :disabled="row.is_monitored || addLoadingSymbol === row.symbol"
                        >
                          {{ row.is_monitored ? '已监控' : (addLoadingSymbol === row.symbol ? '加入中...' : '加入') }}
                        </button>
                      </div>
                    </td>
                    <td data-label="价格 / 市值">
                      <div class="price-cell">
                        <strong class="price-text">{{ formatPrice(row.price) }}</strong>
                        <span class="market-cap-inline">{{ formatMarketCap(row.market_cap) }}</span>
                      </div>
                    </td>
                    <td data-label="PE"><span class="metric-pill" :class="getMetricTone('pe', row.pe)">{{ formatNumber(row.pe) }}</span></td>
                    <td data-label="PB"><span class="metric-pill" :class="getMetricTone('pb', row.pb)">{{ formatNumber(row.pb) }}</span></td>
                    <td data-label="ROE"><span class="metric-pill" :class="getMetricTone('roe', row.roe_pct)">{{ formatPctValue(row.roe_pct) }}</span></td>
                    <td data-label="ROI"><span class="metric-pill" :class="getMetricTone('roi', row.roi_pct)">{{ formatPctValue(row.roi_pct) }}</span></td>
                    <td data-label="股息率"><span class="metric-pill" :class="getMetricTone('dividend', row.dividend_yield)">{{ formatPct(row.dividend_yield) }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="pager">
              <button class="secondary-btn" type="button" @click="goToPage(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">
                上一页
              </button>
              <span>第 {{ pagination.page }} 页 / 共 {{ pagination.total_pages || 1 }} 页</span>
              <button
                class="secondary-btn"
                type="button"
                @click="goToPage(pagination.page + 1)"
                :disabled="pagination.page >= pagination.total_pages || loading"
              >
                下一页
              </button>
            </div>
          </template>
        </section>
      </section>

      <aside class="insight-panel-wrap">
        <section class="insight-card panel">
          <div class="panel-head compact">
            <div>
              <span class="eyebrow">Readout</span>
              <h2>筛选雷达</h2>
            </div>
          </div>
          <div class="radar-list">
            <div><span>低 PB</span><strong>{{ valuationBuckets.lowPb }}</strong></div>
            <div><span>高股息</span><strong>{{ valuationBuckets.highDividend }}</strong></div>
            <div><span>高 ROE</span><strong>{{ valuationBuckets.highRoe }}</strong></div>
            <div><span>已监控</span><strong>{{ monitoredCount }}</strong></div>
          </div>
        </section>

        <section class="insight-card panel">
          <div class="panel-head compact">
            <div>
              <span class="eyebrow">Ideas</span>
              <h2>优先研究</h2>
            </div>
          </div>
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
                <button
                  class="mini-btn primary"
                  type="button"
                  @click="addToMonitor(idea)"
                  :disabled="idea.is_monitored || addLoadingSymbol === idea.symbol"
                >
                  {{ idea.is_monitored ? '已监控' : '加入' }}
                </button>
              </div>
            </article>
          </div>
          <p v-else class="side-empty">拿到结果后，这里会自动列出更值得先看的标的。</p>
        </section>

        <section class="insight-card panel">
          <div class="panel-head compact">
            <div>
              <span class="eyebrow">Industry</span>
              <h2>行业分布</h2>
            </div>
          </div>
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
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { stockApi, type ScreenerMeta, type ScreenerResult } from '@/api'

type ScreenerPreset = 'dividend_value' | 'quality_value' | 'cash_cow'
type SortableField = 'price' | 'pe' | 'pb' | 'roe' | 'roi' | 'dividend_yield' | 'market_cap'

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
    description: '偏向成熟企业，要求盈利、分红和估值都不过分。',
    metrics: ['ROE ≥ 12%', '股息率 ≥ 5%', 'PE ≤ 18'],
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
}

const defaultSortOrderMap: Record<SortableField, 'asc' | 'desc'> = {
  price: 'desc',
  pe: 'asc',
  pb: 'asc',
  roe: 'desc',
  roi: 'desc',
  dividend_yield: 'desc',
  market_cap: 'desc',
}

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.q.trim()) count += 1
  if (filters.pb_max !== null) count += 1
  if (filters.pe_max !== null) count += 1
  if (filters.roe_min !== null) count += 1
  if (filters.dividend_yield_min !== null) count += 1
  if (filters.market_cap_min_100m !== null) count += 1
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

const refreshSnapshot = async () => {
  refreshing.value = true
  errorMessage.value = ''

  try {
    const res = await stockApi.refreshScreenerSnapshot()
    await fetchResults(1)
    if (res.data?.source !== 'upstream' && res.data?.message) {
      errorMessage.value = res.data.message
    }
  } catch (error) {
    console.error('Failed to refresh screener snapshot:', error)
    errorMessage.value = '全市场快照刷新失败，上游数据源可能暂时不稳定。'
  } finally {
    refreshing.value = false
  }
}

const resetFilters = () => {
  filters.q = ''
  filters.pb_max = null
  filters.pe_max = null
  filters.roe_min = null
  filters.dividend_yield_min = null
  filters.market_cap_min_100m = null
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
    filters.pe_max = 18
    filters.roe_min = 12
    filters.dividend_yield_min = 5
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

const getMetricTone = (metric: 'pb' | 'pe' | 'roe' | 'roi' | 'dividend', value?: number | null) => {
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

  if (numeric >= 5) return 'tone-income'
  if (numeric >= 3) return 'tone-neutral'
  return 'tone-muted'
}

onMounted(() => {
  void fetchResults(1)
})
</script>

<style scoped>
.screener-shell {
  --bg: #f4f6f8;
  --panel: #ffffff;
  --panel-soft: #f8fafc;
  --ink: #152033;
  --muted: #637083;
  --faint: #8a96a8;
  --line: #dde4ee;
  --line-strong: #cbd5e1;
  --accent: #0f766e;
  --accent-dark: #0b5f59;
  --warn: #b45309;
  --danger: #b42318;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  padding: 18px;
}

.topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  max-width: 1760px;
  margin: 0 auto 14px;
  padding: 0 4px;
}

.topbar-title,
.topbar-actions,
.result-actions,
.row-actions,
.idea-actions,
.active-tag-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.result-table .row-actions {
  gap: 6px;
  flex-wrap: nowrap;
}

.result-table .mini-btn {
  min-height: 30px;
  padding: 0 8px;
  font-size: 0.8rem;
}

.topbar-title h1,
.panel-head h2,
.result-toolbar h2 {
  margin: 0;
  letter-spacing: 0;
  color: var(--ink);
}

.topbar-title h1 {
  font-size: 1.35rem;
  line-height: 1.2;
}

.eyebrow,
.section-label,
.field span,
.metric-card span,
.radar-list span {
  color: var(--faint);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 42px -34px rgba(15, 23, 42, 0.34);
}

.screener-workspace {
  max-width: 1760px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 320px;
  gap: 14px;
  align-items: start;
}

.filter-panel,
.result-panel,
.insight-card,
.metric-card {
  padding: 16px;
}

.filter-panel,
.insight-panel-wrap {
  position: sticky;
  top: 14px;
}

.panel-head,
.result-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.panel-head.compact h2,
.result-toolbar h2 {
  font-size: 1rem;
}

.filter-form,
.preset-section,
.main-panel,
.insight-panel-wrap,
.idea-list,
.industry-list {
  display: grid;
  gap: 12px;
}

.filter-form {
  margin-top: 14px;
}

.field,
.field-pair {
  display: grid;
  gap: 8px;
}

.field-pair {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field input,
.field select {
  width: 100%;
  height: 38px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  padding: 0 10px;
  font-size: 0.9rem;
}

.field input:focus,
.field select:focus {
  outline: none;
  border-color: rgba(15, 118, 110, 0.65);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.toggle-row {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 0.88rem;
}

.toggle-row input {
  accent-color: var(--accent);
}

.icon-btn,
.primary-btn,
.secondary-btn,
.text-btn,
.mini-btn {
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  cursor: pointer;
  font-weight: 800;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
}

.icon-btn {
  width: 38px;
  height: 38px;
  background: var(--panel);
  color: var(--ink);
  font-size: 1.1rem;
}

.primary-btn {
  min-height: 38px;
  padding: 0 14px;
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.primary-btn.full {
  width: 100%;
}

.secondary-btn,
.mini-btn,
.text-btn {
  min-height: 32px;
  padding: 0 10px;
  background: #fff;
  color: var(--ink);
}

.text-btn {
  border-color: transparent;
  color: var(--accent);
}

.mini-btn.primary {
  background: #ecfdf5;
  border-color: #99f6e4;
  color: var(--accent-dark);
}

.primary-btn:hover,
.icon-btn:hover,
.secondary-btn:hover,
.text-btn:hover,
.mini-btn:hover,
.preset-card:hover {
  transform: translateY(-1px);
}

.primary-btn:disabled,
.secondary-btn:disabled,
.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 99px;
  background: var(--warn);
  box-shadow: 0 0 0 4px rgba(180, 83, 9, 0.12);
}

.status-dot.ready {
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
}

.topbar-meta,
.loading-chip,
.active-tag,
.symbol-badge,
.industry-badge,
.monitor-badge,
.idea-reasons span {
  border-radius: 999px;
  font-weight: 800;
  font-size: 0.76rem;
}

.topbar-meta,
.loading-chip,
.active-tag,
.idea-reasons span {
  padding: 6px 9px;
  background: #fff;
  border: 1px solid var(--line);
  color: var(--muted);
}

.loading-chip {
  background: #ecfdf5;
  color: var(--accent-dark);
  border-color: #99f6e4;
}

.loading-chip.muted,
.active-tag.muted {
  background: var(--panel-soft);
  color: var(--faint);
}

.preset-section {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.preset-card {
  display: grid;
  gap: 6px;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel-soft);
  padding: 11px;
  cursor: pointer;
}

.preset-card div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.preset-card span {
  color: var(--faint);
  font-size: 0.68rem;
  font-weight: 900;
  text-transform: uppercase;
}

.preset-card strong {
  color: var(--ink);
}

.preset-card p {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.45;
}

.preset-income { border-left: 3px solid #f59e0b; }
.preset-quality { border-left: 3px solid #10b981; }
.preset-steady { border-left: 3px solid #3b82f6; }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  display: grid;
  gap: 6px;
}

.metric-card strong {
  color: var(--ink);
  font-size: 1.35rem;
  line-height: 1.1;
}

.metric-card p,
.table-summary span,
.side-empty,
.idea-head span {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

.error-banner {
  padding: 12px 14px;
  color: var(--danger);
  background: #fff7ed;
  border-color: #fed7aa;
  font-weight: 800;
}

.result-panel {
  min-width: 0;
  display: grid;
  gap: 12px;
}

.active-tag-row {
  align-items: flex-start;
}

.table-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel-soft);
}

.table-summary div {
  display: grid;
  gap: 3px;
}

.table-shell {
  overflow: auto;
  scrollbar-gutter: stable;
  max-height: calc(100vh - 320px);
  min-height: 420px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
}

.result-table {
  width: 100%;
  min-width: 850px;
  border-collapse: collapse;
}

.result-table th:first-child,
.result-table td:first-child {
  width: 180px;
  min-width: 180px;
}

.result-table th.action-col,
.result-table td.action-col {
  width: 124px;
  min-width: 124px;
}

.result-table th,
.result-table td {
  padding: 10px 9px;
  border-bottom: 1px solid #eef2f7;
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
  font-size: 0.72rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.result-table th:first-child,
.result-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  background: #fff;
  box-shadow: 10px 0 18px -18px rgba(15, 23, 42, 0.34);
}

.result-table th:first-child {
  z-index: 3;
  background: #f8fafc;
}

.result-table th.action-col,
.result-table td.action-col {
  position: sticky;
  left: 180px;
  z-index: 1;
  background: #fff;
  box-shadow: 10px 0 18px -18px rgba(15, 23, 42, 0.34);
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
  margin-left: 4px;
}

.sort-header span.active {
  color: var(--accent);
}

.company-cell {
  display: grid;
  gap: 5px;
}

.company-mainline,
.company-subline {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.company-mainline strong,
.idea-head strong {
  color: var(--ink);
  font-size: 0.88rem;
}

.symbol-badge,
.industry-badge,
.monitor-badge {
  padding: 2px 6px;
  border: 1px solid var(--line);
  background: var(--panel-soft);
  color: var(--muted);
}

.monitor-badge {
  color: var(--accent-dark);
  border-color: #99f6e4;
  background: #ecfdf5;
}

.price-text {
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.price-cell {
  display: inline-grid;
  gap: 3px;
  align-items: center;
}

.market-cap-inline {
  color: var(--faint);
  font-size: 0.72rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.metric-pill {
  display: inline-flex;
  min-width: 48px;
  justify-content: center;
  padding: 5px 7px;
  border-radius: 999px;
  font-weight: 900;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  border: 1px solid var(--line);
  background: var(--panel-soft);
  color: var(--muted);
}

.tone-cheap,
.tone-income,
.tone-strong,
.tone-quality {
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

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--muted);
  font-size: 0.86rem;
}

.empty-state {
  min-height: 420px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  text-align: center;
  color: var(--muted);
  border: 1px dashed var(--line-strong);
  border-radius: 8px;
  background: var(--panel-soft);
}

.empty-state strong {
  color: var(--ink);
  font-size: 1rem;
}

.empty-state p {
  margin: 0;
  max-width: 360px;
  line-height: 1.6;
}

.insight-card {
  display: grid;
  gap: 12px;
}

.radar-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.radar-list div {
  display: grid;
  gap: 5px;
  padding: 10px;
  border-radius: 8px;
  background: var(--panel-soft);
  border: 1px solid var(--line);
}

.radar-list strong {
  font-size: 1.25rem;
  color: var(--ink);
}

.idea-card {
  display: grid;
  gap: 10px;
  padding: 11px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--panel-soft);
}

.idea-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.idea-head div {
  display: grid;
  gap: 3px;
}

.idea-head b {
  min-width: 36px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: #ecfdf5;
  color: var(--accent-dark);
  font-size: 0.8rem;
}

.idea-reasons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.industry-row {
  display: grid;
  gap: 6px;
}

.industry-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.82rem;
}

.industry-label strong {
  color: var(--ink);
}

.industry-label span {
  color: var(--faint);
}

.industry-bar-track {
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf2f7;
}

.industry-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), #38bdf8);
}

@media (max-width: 1380px) {
  .screener-workspace {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .insight-panel-wrap {
    grid-column: 1 / -1;
    position: static;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    display: grid;
  }
}

@media (max-width: 1040px) {
  .screener-workspace,
  .summary-grid,
  .insight-panel-wrap {
    grid-template-columns: 1fr;
  }

  .filter-panel {
    position: static;
  }

  .topbar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
  }

  .table-shell {
    max-height: none;
  }
}

@media (max-width: 720px) {
  .screener-shell {
    padding: 12px;
  }

  .field-pair,
  .radar-list {
    grid-template-columns: 1fr;
  }

  .result-table {
    min-width: 0;
  }

  .result-table th:first-child,
  .result-table td:first-child,
  .result-table th.action-col,
  .result-table td.action-col {
    width: 100%;
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
    padding: 10px 0;
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
  }

  .company-cell {
    text-align: right;
  }
}
</style>

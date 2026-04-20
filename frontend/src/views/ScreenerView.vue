<template>
  <div class="screener-shell" :class="{ 'drawer-open': isFilterDrawerOpen }">
    <div class="shell-orb orb-left"></div>
    <div class="shell-orb orb-right"></div>
    <div class="shell-grid"></div>

    <transition name="drawer-fade">
      <button
        v-if="isFilterDrawerOpen"
        class="drawer-backdrop"
        type="button"
        aria-label="关闭筛选面板"
        @click="closeFilterDrawer"
      ></button>
    </transition>

    <transition name="drawer-slide">
      <aside
        v-if="isFilterDrawerOpen"
        class="filter-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="条件筛选面板"
      >
        <div class="drawer-shell">
          <div class="drawer-topbar">
            <div class="drawer-topbar-copy">
              <span class="panel-kicker">Filter Drawer</span>
              <h2>条件筛选</h2>
              <p class="panel-copy">调条件时专注看抽屉，有结果后自动收起，结果区保持完整视野。</p>
            </div>
            <button class="drawer-close-btn" type="button" @click="closeFilterDrawer">关闭</button>
          </div>

          <div class="drawer-scroll filter-panel sidebar-column">
            <section class="panel-card sidebar-intro">
          <span class="panel-kicker">Screening Desk</span>
          <h2>条件筛选</h2>
          <p class="panel-copy">先定义阈值，再让候选池自己浮到结果区；没有结果时保留当前面板，方便继续回调。</p>
          <div class="sidebar-meta">
            <div class="sidebar-meta-item">
              <span>已启用</span>
              <strong>{{ activeFilterCount }} 项</strong>
            </div>
            <div class="sidebar-meta-item">
              <span>当前排序</span>
              <strong>{{ activeSortLabel }}</strong>
            </div>
            <div class="sidebar-meta-item">
              <span>快照日期</span>
              <strong>{{ screenerMeta.snapshot_date || '--' }}</strong>
            </div>
          </div>
            </section>

            <section class="panel-card filter-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">Filters</span>
              <h2>筛选条件</h2>
              <p class="panel-copy">先用估值做粗筛，再用 ROE、股息率和市值收窄范围。</p>
            </div>
            <button class="text-btn" type="button" @click="resetFilters">重置</button>
          </div>
          <form class="filter-stack" @submit.prevent="applyFilters(1)">
            <div class="filter-section">
              <div class="section-label">检索</div>
              <div class="filter-grid filter-grid-single">
                <label class="field">
                  <span>名称 / 代码</span>
                  <input v-model.trim="filters.q" placeholder="如 银行 / 600000 / 阿胶" />
                </label>
              </div>
            </div>

            <div class="filter-section">
              <div class="section-label">估值与回报</div>
              <div class="filter-grid">
                <label class="field">
                  <span>PB ≤</span>
                  <input v-model.number="filters.pb_max" type="number" step="0.1" placeholder="1.5" />
                </label>
                <label class="field">
                  <span>PE ≤</span>
                  <input v-model.number="filters.pe_max" type="number" step="0.1" placeholder="15" />
                </label>
                <label class="field">
                  <span>ROE ≥</span>
                  <input v-model.number="filters.roe_min" type="number" step="0.5" placeholder="12" />
                </label>
                <label class="field">
                  <span>股息率 ≥</span>
                  <input v-model.number="filters.dividend_yield_min" type="number" step="0.1" placeholder="4" />
                </label>
                <label class="field field-full">
                  <span>总市值 ≥</span>
                  <input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="100" />
                  <small>单位：亿元。用于过滤过小样本，减少流动性噪音。</small>
                </label>
              </div>
            </div>

            <div class="filter-section">
              <div class="section-label">排序与样本</div>
              <div class="filter-grid">
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
                <label class="field field-checkbox field-full">
                  <span>异常样本</span>
                  <div class="checkbox-row">
                    <input v-model="filters.include_anomalies" type="checkbox" />
                    <strong>包含异常估值样本</strong>
                  </div>
                  <small>默认剔除 PE≤0 或 PB≤0 的样本，避免失真值干扰筛选。</small>
                </label>
              </div>
            </div>

            <div class="drawer-form-actions">
              <button class="ghost-btn drawer-ghost-btn" type="button" @click="closeFilterDrawer">先收起</button>
              <button class="apply-btn" type="submit" :disabled="loading">开始筛选</button>
            </div>
          </form>
            </section>

            <section class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">Presets</span>
              <h2>常用组合</h2>
              <p class="panel-copy">给没有明确阈值时一个像样的起点，而不是空白表单。</p>
            </div>
          </div>
          <div class="preset-stack">
            <button
              v-for="preset in presetCards"
              :key="preset.key"
              class="preset-card"
              :class="`preset-${preset.tone}`"
              @click="applyPreset(preset.key)"
            >
              <span class="preset-kicker">{{ preset.tagline }}</span>
              <strong>{{ preset.title }}</strong>
              <p>{{ preset.description }}</p>
              <div class="preset-metrics">
                <span v-for="metric in preset.metrics" :key="metric">{{ metric }}</span>
              </div>
            </button>
          </div>
            </section>
          </div>
        </div>
      </aside>
    </transition>

    <main class="screener-layout">
      <section class="result-panel result-column">
        <section class="panel-card masthead-card">
          <div class="masthead-head">
            <div class="toolbar-copy">
              <div class="header-topline">A-SHARE VALUE SCREENER</div>
              <div class="toolbar-headline">
                <h1>价值筛选工作台</h1>
                <p class="header-copy">
                  按估值、回报和股息率收窄候选池，让真正值得研究的公司尽快浮到结果区顶部。
                </p>
              </div>
              <div class="toolbar-chips">
                <span class="hero-chip">年报 ROE 优先</span>
                <span class="hero-chip">SQLite 本地快照</span>
                <span class="hero-chip">点击表头即可排序</span>
              </div>
            </div>

            <div class="header-actions">
              <button class="ghost-btn" @click="router.push('/')">返回首页</button>
              <button class="drawer-trigger-btn" @click="openFilterDrawer">
                <span>打开筛选器</span>
                <span class="trigger-badge">{{ activeFilterCount }}</span>
              </button>
              <button class="refresh-btn" @click="refreshSnapshot" :disabled="refreshing">
                {{ refreshing ? '刷新中...' : '刷新全市场快照' }}
              </button>
            </div>
          </div>

          <div class="filter-summary-bar">
            <div class="summary-copy">
              <span class="panel-kicker">Interaction</span>
              <h3>{{ pagination.total ? '结果优先展示，筛选器按需弹出' : '先设条件，再让结果自己浮出来' }}</h3>
              <p class="panel-copy">筛选区改成弹出式抽屉，拿到结果就自动收起；没有命中时保持展开，方便立刻继续回调条件。</p>
            </div>

            <div class="summary-actions">
              <button class="summary-trigger" @click="openFilterDrawer">
                {{ isFilterDrawerOpen ? '正在调整条件' : '调整条件' }}
              </button>
              <div class="summary-metrics">
                <span class="summary-pill">快照 {{ screenerMeta.snapshot_date || '--' }}</span>
                <span class="summary-pill">排序 {{ activeSortLabel }}</span>
                <span class="summary-pill">候选 {{ pagination.total }} 只</span>
                <span class="summary-pill">覆盖 {{ screenerMeta.industry_count || '--' }} 个行业</span>
              </div>
            </div>

            <div class="active-tag-row">
              <span v-for="tag in activeFilterTags" :key="tag" class="active-tag">{{ tag }}</span>
              <span v-if="!activeFilterTags.length" class="active-tag muted">当前未设置额外筛选条件</span>
            </div>
          </div>

          <div v-if="errorMessage" class="error-banner inline-error">
            {{ errorMessage }}
          </div>

          <div class="overview-grid">
            <article class="overview-item">
              <span>快照日期</span>
              <strong>{{ screenerMeta.snapshot_date || '--' }}</strong>
              <p>本页查询只读最新一轮落库数据。</p>
            </article>
            <article class="overview-item">
              <span>可筛标的</span>
              <strong>{{ screenerMeta.count || 0 }}</strong>
              <p>全市场快照入库后，筛选直接走本地 SQLite。</p>
            </article>
            <article class="overview-item">
              <span>当前排序</span>
              <strong>{{ activeSortLabel }}</strong>
              <p>既可在筛选抽屉中修改，也可以直接点击结果表头。</p>
            </article>
            <article class="overview-item">
              <span>筛选概况</span>
              <strong>{{ activeFilterCount }} 项 / {{ coverageDensityLabel }}</strong>
              <p>用行业覆盖判断这次结果是否过度集中在单一板块。</p>
            </article>
          </div>
        </section>

        <div class="panel-card result-card">
          <div class="panel-head result-head">
            <div class="result-copy-block">
              <span class="panel-kicker">Results</span>
              <h2>候选池</h2>
              <p class="result-copy">
                当前筛出 {{ pagination.total }} 只。先看便宜和回报，再决定哪些标的值得进入深度分析。
              </p>
              <div class="result-ribbon">
                <span class="ribbon-item">排序 {{ activeSortLabel }}</span>
                <span class="ribbon-item">快照 {{ screenerMeta.snapshot_date || '--' }}</span>
                <span class="ribbon-item">覆盖 {{ screenerMeta.industry_count || '--' }} 个行业</span>
              </div>
            </div>

            <div class="result-status-stack">
              <div class="result-status">
                <span v-if="loading">正在筛选...</span>
                <span v-else>第 {{ pagination.page }} / {{ pagination.total_pages || 1 }} 页</span>
              </div>
              <div class="result-status subtle">
                候选 {{ pagination.total }} 只
              </div>
              <button class="ghost-btn compact-btn" @click="openFilterDrawer">调整筛选</button>
            </div>
          </div>

          <div v-if="!screenerMeta.ready" class="empty-state">
            <div class="empty-orb"></div>
            <strong>还没有选股快照</strong>
            <p>先刷新一次全市场快照，SQLite 本地库里就会生成可筛选的数据表。</p>
            <div class="empty-actions">
              <button class="refresh-btn" @click="refreshSnapshot" :disabled="refreshing">
                {{ refreshing ? '刷新中...' : '立即生成快照' }}
              </button>
            </div>
          </div>

          <div v-else-if="loading" class="empty-state">
            <div class="empty-orb loading"></div>
            <strong>正在按条件筛选</strong>
            <p>这一步只查本地 SQLite，不会重新抓全市场数据。</p>
          </div>

          <div v-else-if="!results.length" class="empty-state">
            <div class="empty-orb muted"></div>
            <strong>没有命中结果</strong>
            <p>当前抽屉会保持打开，方便你继续放宽 PB / PE / 股息率等阈值后再试一次。</p>
            <div class="empty-actions">
              <button class="ghost-btn" @click="openFilterDrawer">继续调条件</button>
            </div>
          </div>

          <div v-else class="table-shell">
            <table class="result-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>
                    <button class="sort-header" @click="toggleSort('price')">
                      <span>价格</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'price' }">{{ getSortIndicator('price') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('pe')">
                      <span>PE</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'pe' }">{{ getSortIndicator('pe') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('pb')">
                      <span>PB</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'pb' }">{{ getSortIndicator('pb') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('roe')">
                      <span>ROE</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'roe' }">{{ getSortIndicator('roe') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('roi')">
                      <span>ROI</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'roi' }">{{ getSortIndicator('roi') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('dividend_yield')">
                      <span>股息率</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'dividend_yield' }">{{ getSortIndicator('dividend_yield') }}</span>
                    </button>
                  </th>
                  <th>
                    <button class="sort-header" @click="toggleSort('market_cap')">
                      <span>总市值</span>
                      <span class="sort-indicator" :class="{ active: filters.sort_by === 'market_cap' }">{{ getSortIndicator('market_cap') }}</span>
                    </button>
                  </th>
                  <th>动作</th>
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
                  <td data-label="价格">
                    <strong class="price-text">{{ formatPrice(row.price) }}</strong>
                  </td>
                  <td data-label="PE">
                    <span class="metric-pill" :class="getMetricTone('pe', row.pe)">{{ formatNumber(row.pe) }}</span>
                  </td>
                  <td data-label="PB">
                    <span class="metric-pill" :class="getMetricTone('pb', row.pb)">{{ formatNumber(row.pb) }}</span>
                  </td>
                  <td data-label="ROE">
                    <span class="metric-pill" :class="getMetricTone('roe', row.roe_pct)">{{ formatPctValue(row.roe_pct) }}</span>
                  </td>
                  <td data-label="ROI">
                    <span class="metric-pill" :class="getMetricTone('roi', row.roi_pct)">{{ formatPctValue(row.roi_pct) }}</span>
                  </td>
                  <td data-label="股息率">
                    <span class="metric-pill" :class="getMetricTone('dividend', row.dividend_yield)">{{ formatPct(row.dividend_yield) }}</span>
                  </td>
                  <td data-label="总市值">
                    <span class="market-cap-text">{{ formatMarketCap(row.market_cap) }}</span>
                  </td>
                  <td data-label="动作">
                    <div class="row-actions">
                      <button class="mini-btn" @click="openAnalysis(row.symbol)">分析</button>
                      <button
                        class="mini-btn mini-btn-primary"
                        @click="addToMonitor(row)"
                        :disabled="row.is_monitored || addLoadingSymbol === row.symbol"
                      >
                        {{ row.is_monitored ? '已监控' : (addLoadingSymbol === row.symbol ? '加入中...' : '加入监控') }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="results.length" class="pager">
            <button class="ghost-btn" @click="goToPage(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">
              上一页
            </button>
            <span>第 {{ pagination.page }} 页，共 {{ pagination.total_pages || 1 }} 页</span>
            <button class="ghost-btn" @click="goToPage(pagination.page + 1)" :disabled="pagination.page >= pagination.total_pages || loading">
              下一页
            </button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { stockApi, type ScreenerMeta, type ScreenerResult } from '@/api'

type ScreenerPreset = 'dividend_value' | 'quality_value' | 'cash_cow'
type SortableField = 'price' | 'pe' | 'pb' | 'roe' | 'roi' | 'dividend_yield' | 'market_cap'
type FetchResultsOptions = {
  closeDrawerOnSuccess?: boolean
}

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
const isFilterDrawerOpen = ref(false)
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
    description: '先看安全边际，再看现金回报，适合从成熟生意里找便宜货。',
    metrics: ['PB ≤ 1.5', 'PE ≤ 15', '股息率 ≥ 4%'],
    tone: 'income',
  },
  {
    key: 'quality_value',
    title: '高 ROE 价值',
    tagline: 'Preset 02',
    description: '更看重盈利质量与定价能力，适合先筛高回报公司。',
    metrics: ['PB ≤ 3', 'PE ≤ 25', 'ROE ≥ 15%'],
    tone: 'quality',
  },
  {
    key: 'cash_cow',
    title: '现金奶牛',
    tagline: 'Preset 03',
    description: '优先找现金回流稳定、回报不差、估值不过分的成熟企业。',
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
  const total = Number(screenerMeta.value.count || 0)
  const industries = Number(screenerMeta.value.industry_count || 0)
  if (!total || !industries) return '--'
  return `${(total / industries).toFixed(1)} 只/行业`
})

const activeFilterTags = computed(() => {
  const tags: string[] = []
  if (filters.q.trim()) tags.push(`检索 ${filters.q.trim()}`)
  if (filters.pb_max !== null) tags.push(`PB ≤ ${filters.pb_max}`)
  if (filters.pe_max !== null) tags.push(`PE ≤ ${filters.pe_max}`)
  if (filters.roe_min !== null) tags.push(`ROE ≥ ${filters.roe_min}%`)
  if (filters.dividend_yield_min !== null) tags.push(`股息率 ≥ ${filters.dividend_yield_min}%`)
  if (filters.market_cap_min_100m !== null) tags.push(`市值 ≥ ${filters.market_cap_min_100m} 亿`)
  if (filters.include_anomalies) tags.push('包含异常样本')
  return tags
})

const openFilterDrawer = () => {
  isFilterDrawerOpen.value = true
}

const closeFilterDrawer = () => {
  isFilterDrawerOpen.value = false
}

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

const fetchResults = async (page = 1, options: FetchResultsOptions = {}) => {
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

    if (options.closeDrawerOnSuccess) {
      if (res.data.results.length > 0) {
        closeFilterDrawer()
      } else {
        openFilterDrawer()
      }
    }
  } catch (error) {
    console.error('Failed to fetch screener results:', error)
    errorMessage.value = '选股结果拉取失败，请稍后重试。'
    results.value = []
    if (options.closeDrawerOnSuccess) {
      openFilterDrawer()
    }
  } finally {
    loading.value = false
  }
}

const applyFilters = async (page = 1) => {
  await fetchResults(page, { closeDrawerOnSuccess: true })
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

const resetFilters = (shouldFetch = true) => {
  filters.q = ''
  filters.pb_max = null
  filters.pe_max = null
  filters.roe_min = null
  filters.dividend_yield_min = null
  filters.market_cap_min_100m = null
  filters.include_anomalies = false
  filters.sort_by = 'pb'
  filters.sort_order = 'asc'
  if (shouldFetch) {
    void fetchResults(1, { closeDrawerOnSuccess: true })
  }
}

const applyPreset = (preset: ScreenerPreset) => {
  resetFilters(false)
  if (preset === 'dividend_value') {
    filters.pb_max = 1.5
    filters.pe_max = 15
    filters.dividend_yield_min = 4
  }
  if (preset === 'quality_value') {
    filters.pb_max = 3
    filters.pe_max = 25
    filters.roe_min = 15
  }
  if (preset === 'cash_cow') {
    filters.roe_min = 12
    filters.dividend_yield_min = 5
    filters.pe_max = 18
  }
  void fetchResults(1, { closeDrawerOnSuccess: true })
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
  return `${(Number(value) / 1e8).toFixed(0)}亿`
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

const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && isFilterDrawerOpen.value) {
    closeFilterDrawer()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
  void fetchResults(1)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
})
</script>

<style scoped>
.screener-shell {
  --bg-panel: rgba(255, 255, 255, 0.86);
  --border-soft: rgba(148, 163, 184, 0.24);
  --text-main: #0f172a;
  --text-soft: #475569;
  --text-faint: #64748b;
  --accent-cyan: #0f766e;
  min-height: 100vh;
  position: relative;
  padding: 28px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(45, 212, 191, 0.14), transparent 26%),
    radial-gradient(circle at top right, rgba(251, 146, 60, 0.11), transparent 20%),
    linear-gradient(180deg, #f7fbfc 0%, #f2f7fb 42%, #edf3f8 100%);
}

.shell-orb,
.shell-grid {
  pointer-events: none;
  position: absolute;
}

.shell-orb {
  width: 520px;
  height: 520px;
  border-radius: 999px;
  filter: blur(70px);
  opacity: 0.16;
}

.orb-left {
  top: -160px;
  left: -120px;
  background: rgba(45, 212, 191, 0.36);
}

.orb-right {
  top: 80px;
  right: -180px;
  background: rgba(251, 146, 60, 0.24);
}

.shell-grid {
  inset: 0;
  opacity: 0.05;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.16) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.16) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.75), transparent 92%);
}

.masthead-card,
.panel-card {
  position: relative;
  z-index: 1;
}

.panel-card {
  border: 1px solid var(--border-soft);
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.92));
  backdrop-filter: blur(18px);
  box-shadow: 0 28px 60px -42px rgba(15, 23, 42, 0.22);
}

.masthead-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.toolbar-copy {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.inline-error {
  margin-top: 4px;
}

.toolbar-headline {
  display: grid;
  gap: 8px;
}

.header-topline,
.panel-kicker,
.section-label,
.preset-kicker {
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-cyan);
}

.toolbar-headline h1,
.panel-head h2 {
  margin: 0;
  color: #0f172a;
}

.toolbar-headline h1 {
  font-size: clamp(1.8rem, 3vw, 2.5rem);
  line-height: 1.02;
  letter-spacing: -0.03em;
}

.header-copy,
.panel-copy,
.result-copy,
.meta-card p,
.preset-card p,
.field small {
  color: var(--text-soft);
  line-height: 1.72;
}

.header-copy {
  max-width: 760px;
  margin: 0;
  font-size: 0.98rem;
}

.toolbar-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.header-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.ghost-btn,
.refresh-btn,
.apply-btn,
.text-btn,
.mini-btn,
.preset-card {
  border: none;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    border-color 0.22s ease,
    background 0.22s ease,
    color 0.22s ease;
}

.ghost-btn,
.refresh-btn,
.apply-btn {
  padding: 12px 18px;
  border-radius: 14px;
  font-weight: 800;
}

.ghost-btn {
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.86);
  color: #334155;
}

.refresh-btn,
.apply-btn,
.mini-btn-primary {
  background: linear-gradient(135deg, #0f766e, #0ea5a4);
  color: #f7fffe;
  box-shadow: 0 18px 35px -24px rgba(20, 184, 166, 0.55);
}

.ghost-btn:hover,
.refresh-btn:hover,
.apply-btn:hover,
.mini-btn:hover,
.preset-card:hover {
  transform: translateY(-1px);
}

.refresh-btn:disabled,
.apply-btn:disabled,
.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.screener-layout,
.filter-grid,
.preset-stack,
.filter-panel {
  display: grid;
  gap: 16px;
}

.sidebar-column,
.result-column {
  display: grid;
  gap: 16px;
}

.error-banner {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 237, 213, 0.9);
  border: 1px solid rgba(251, 146, 60, 0.28);
  color: #9a3412;
  font-weight: 700;
}

.hero-chip {
  padding: 8px 12px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  border-radius: 999px;
  background: rgba(240, 253, 250, 0.92);
  color: #0f766e;
  font-size: 0.78rem;
  font-weight: 700;
}

.sidebar-intro {
  display: grid;
  gap: 12px;
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.88), rgba(248, 250, 252, 0.96));
}

.sidebar-intro h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.55rem;
  line-height: 1.08;
}

.sidebar-meta {
  display: grid;
  gap: 10px;
}

.sidebar-meta-item {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.82);
}

.sidebar-meta-item span {
  display: block;
  font-size: 0.72rem;
  color: #64748b;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sidebar-meta-item strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 0.98rem;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.overview-item {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(248, 250, 252, 0.85);
}

.overview-item span,
.field span {
  display: block;
  font-size: 0.74rem;
  color: var(--text-faint);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.overview-item strong {
  display: block;
  margin-top: 10px;
  font-size: 1.08rem;
  color: #0f172a;
}

.overview-item p {
  margin: 8px 0 0;
}

.screener-layout {
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  align-items: start;
}

.filter-panel,
.result-panel {
  display: grid;
  gap: 16px;
}

.filter-panel {
  position: sticky;
  top: 22px;
}

.panel-card {
  padding: 22px;
}

.panel-head,
.result-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.panel-copy {
  margin: 8px 0 0;
  font-size: 0.92rem;
}

.text-btn {
  background: transparent;
  color: #2563eb;
  font-weight: 700;
}

.filter-stack {
  display: grid;
  gap: 16px;
}

.filter-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.78);
}

.filter-grid {
  grid-template-columns: 1fr 1fr;
}

.filter-grid-single {
  grid-template-columns: 1fr;
}

.field {
  display: grid;
  gap: 8px;
}

.field-checkbox {
  grid-column: span 2;
}

.field-full {
  grid-column: span 2;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  padding: 0 2px;
}

.checkbox-row input {
  width: 16px;
  height: 16px;
  accent-color: #14b8a6;
}

.checkbox-row strong {
  color: var(--text-main);
  font-size: 0.95rem;
}

.field input,
.field select {
  width: 100%;
  padding: 13px 14px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.98);
  color: #0f172a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.field input::placeholder {
  color: #94a3b8;
}

.field input:focus,
.field select:focus {
  outline: none;
  border-color: rgba(103, 232, 249, 0.5);
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.12);
}

.apply-btn {
  width: 100%;
  margin-top: 4px;
}

.preset-stack {
  display: grid;
  gap: 12px;
}

.preset-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  text-align: left;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 252, 0.94));
}

.preset-card strong {
  color: #0f172a;
  font-size: 1.06rem;
}

.preset-card p {
  margin: 0;
  font-size: 0.92rem;
}

.preset-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-metrics span {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  color: #334155;
  background: rgba(241, 245, 249, 0.95);
}

.preset-income {
  border-color: rgba(251, 191, 36, 0.28);
}

.preset-quality {
  border-color: rgba(34, 197, 94, 0.24);
}

.preset-steady {
  border-color: rgba(103, 232, 249, 0.22);
}

.result-card {
  min-height: 760px;
}

.result-copy-block {
  display: grid;
  gap: 10px;
}

.result-copy {
  margin: 0;
  max-width: 720px;
}

.result-ribbon {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ribbon-item,
.result-status {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(248, 250, 252, 0.95);
  color: #334155;
  font-size: 0.8rem;
  font-weight: 700;
}

.result-status {
  font-size: 0.82rem;
}

.result-status-stack {
  display: grid;
  gap: 8px;
  justify-items: end;
}

.result-status.subtle {
  color: #64748b;
}

.empty-state {
  min-height: 340px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-radius: 22px;
  border: 1px dashed rgba(148, 163, 184, 0.3);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94));
  text-align: center;
}

.empty-orb {
  width: 54px;
  height: 54px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(103, 232, 249, 0.75), rgba(103, 232, 249, 0.08));
  box-shadow: 0 0 32px rgba(103, 232, 249, 0.16);
}

.empty-orb.loading {
  animation: pulse-orb 1.7s ease-in-out infinite;
}

.empty-orb.muted {
  background: radial-gradient(circle, rgba(148, 163, 184, 0.5), rgba(148, 163, 184, 0.08));
  box-shadow: none;
}

.empty-state strong {
  color: #0f172a;
  font-size: 1.08rem;
}

.empty-state p {
  max-width: 540px;
  margin: 0;
  color: var(--text-soft);
  line-height: 1.72;
}

.table-shell {
  overflow: auto;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.96);
}

.result-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.result-table th,
.result-table td {
  padding: 15px 16px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.92);
  text-align: left;
  color: #334155;
  font-size: 0.9rem;
  vertical-align: middle;
}

.result-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(248, 250, 252, 0.98);
  color: #64748b;
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sort-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sort-indicator {
  color: #94a3b8;
  font-size: 0.8rem;
  line-height: 1;
}

.sort-indicator.active {
  color: #0f766e;
}

.result-table tbody tr {
  transition: background 0.2s ease, transform 0.2s ease;
}

.result-table tbody tr:hover {
  background: rgba(236, 253, 245, 0.9);
}

.company-cell {
  display: grid;
  gap: 8px;
}

.company-mainline,
.company-subline,
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.company-mainline strong {
  color: #0f172a;
  font-size: 0.98rem;
}

.monitor-badge,
.symbol-badge,
.industry-badge {
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
}

.monitor-badge {
  border: 1px solid rgba(16, 185, 129, 0.25);
  background: rgba(220, 252, 231, 0.95);
  color: #047857;
}

.symbol-badge {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(241, 245, 249, 0.96);
  color: #334155;
  font-family: 'Monaco', monospace;
}

.industry-badge {
  border: 1px solid rgba(125, 211, 252, 0.2);
  background: rgba(224, 242, 254, 0.95);
  color: #0369a1;
}

.price-text {
  color: #0f172a;
  font-size: 1rem;
}

.metric-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 78px;
  padding: 7px 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(241, 245, 249, 0.96);
  font-size: 0.8rem;
  font-weight: 800;
  color: #334155;
}

.tone-cheap {
  border-color: rgba(52, 211, 153, 0.24);
  background: rgba(220, 252, 231, 0.95);
  color: #047857;
}

.tone-quality {
  border-color: rgba(34, 211, 238, 0.24);
  background: rgba(224, 242, 254, 0.95);
  color: #0f766e;
}

.tone-strong {
  border-color: rgba(74, 222, 128, 0.28);
  background: rgba(209, 250, 229, 0.96);
  color: #166534;
}

.tone-income {
  border-color: rgba(251, 191, 36, 0.26);
  background: rgba(254, 249, 195, 0.95);
  color: #a16207;
}

.tone-neutral {
  border-color: rgba(125, 211, 252, 0.18);
  background: rgba(239, 246, 255, 0.96);
  color: #1d4ed8;
}

.tone-warm {
  border-color: rgba(251, 146, 60, 0.24);
  background: rgba(255, 237, 213, 0.95);
  color: #c2410c;
}

.tone-muted {
  color: #64748b;
}

.market-cap-text {
  color: #0f172a;
  font-weight: 700;
}

.mini-btn {
  padding: 9px 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.96);
  color: #334155;
  font-size: 0.78rem;
  font-weight: 800;
}

.pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 18px;
}

.pager span {
  color: #475569;
  font-size: 0.9rem;
  font-weight: 700;
}

.screener-shell {
  overflow-x: hidden;
}

.screener-shell.drawer-open {
  height: 100vh;
  overflow: hidden;
}

.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 18;
  border: none;
  background: rgba(15, 23, 42, 0.2);
  backdrop-filter: blur(6px);
  cursor: pointer;
}

.filter-drawer {
  position: fixed;
  top: 18px;
  left: 18px;
  bottom: 18px;
  width: min(420px, calc(100vw - 36px));
  z-index: 20;
}

.drawer-shell {
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 14px;
}

.drawer-topbar {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  padding: 22px 24px;
  border: 1px solid var(--border-soft);
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.92));
  backdrop-filter: blur(18px);
  box-shadow: 0 28px 60px -42px rgba(15, 23, 42, 0.22);
}

.drawer-topbar-copy {
  display: grid;
  gap: 8px;
}

.drawer-topbar-copy h2 {
  margin: 0;
  color: #0f172a;
  font-size: 1.4rem;
  line-height: 1.05;
}

.drawer-scroll {
  min-height: 0;
  overflow: auto;
  padding-right: 6px;
}

.drawer-scroll::-webkit-scrollbar {
  width: 7px;
}

.drawer-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.3);
}

.drawer-close-btn,
.drawer-trigger-btn,
.summary-trigger {
  border: none;
  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease,
    border-color 0.22s ease,
    background 0.22s ease,
    color 0.22s ease;
  padding: 12px 18px;
  border-radius: 14px;
  font-weight: 800;
}

.drawer-close-btn {
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.9);
  color: #334155;
}

.drawer-trigger-btn,
.summary-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid rgba(15, 118, 110, 0.2);
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.98), rgba(232, 250, 247, 0.96));
  color: #0f766e;
  box-shadow: 0 16px 32px -26px rgba(15, 118, 110, 0.36);
}

.drawer-close-btn:hover,
.drawer-trigger-btn:hover,
.summary-trigger:hover {
  transform: translateY(-1px);
}

.trigger-badge {
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #0f766e;
  color: #f8fafc;
  font-size: 0.78rem;
  font-weight: 800;
}

.masthead-card {
  display: grid;
  gap: 18px;
}

.masthead-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.filter-summary-bar {
  display: grid;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(180deg, rgba(240, 253, 250, 0.78), rgba(248, 250, 252, 0.94));
}

.summary-copy {
  display: grid;
  gap: 8px;
}

.summary-copy h3 {
  margin: 0;
  color: #0f172a;
  font-size: 1.14rem;
}

.summary-actions {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.summary-metrics,
.active-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-pill,
.active-tag {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.92);
  color: #334155;
  font-size: 0.8rem;
  font-weight: 700;
}

.active-tag {
  background: rgba(248, 250, 252, 0.95);
}

.active-tag.muted {
  color: #64748b;
  border-style: dashed;
}

.screener-layout {
  max-width: 1480px;
  margin: 0 auto;
  grid-template-columns: 1fr;
}

.overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.filter-panel {
  position: static;
}

.drawer-form-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 12px;
}

.drawer-ghost-btn {
  width: 100%;
}

.compact-btn {
  padding: 10px 14px;
}

.empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.drawer-fade-enter-active,
.drawer-fade-leave-active,
.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: all 0.24s ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  opacity: 0;
  transform: translateX(-18px);
}

@keyframes pulse-orb {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.8;
  }

  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@media (max-width: 1240px) {
  .masthead-card,
  .screener-layout {
    grid-template-columns: 1fr;
  }

  .masthead-card {
    display: grid;
  }

  .filter-panel {
    position: static;
  }

  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .overview-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .field-checkbox,
  .field-full {
    grid-column: span 1;
  }

  .result-table,
  .result-table tbody,
  .result-table tr,
  .result-table td {
    display: block;
    width: 100%;
  }

  .result-table thead {
    display: none;
  }

  .result-table tbody {
    display: grid;
    gap: 14px;
    padding: 14px;
  }

  .result-table tbody tr {
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.98);
    overflow: hidden;
  }

  .result-table td {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }

  .result-table td::before {
    content: attr(data-label);
    flex: 0 0 74px;
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .result-table td:last-child {
    border-bottom: none;
  }
}

@media (max-width: 760px) {
  .screener-shell {
    padding: 18px;
  }

  .toolbar-copy,
  .overview-item,
  .panel-card,
  .table-shell {
    border-radius: 22px;
  }

  .header-actions,
  .masthead-card,
  .panel-head,
  .result-head,
  .pager {
    display: grid;
  }

  .result-status-stack {
    justify-items: start;
  }

  .row-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .mini-btn,
  .ghost-btn,
  .refresh-btn {
    width: 100%;
  }

}

@media (max-width: 1180px) {
  .masthead-head,
  .summary-actions,
  .panel-head,
  .result-head {
    display: grid;
  }

  .result-status-stack {
    justify-items: start;
  }

  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .filter-drawer {
    top: 10px;
    left: 10px;
    right: 10px;
    bottom: 10px;
    width: auto;
  }
}

@media (max-width: 760px) {
  .drawer-topbar {
    padding: 18px 18px 16px;
  }

  .drawer-form-actions {
    grid-template-columns: 1fr;
  }

  .drawer-trigger-btn,
  .summary-trigger,
  .compact-btn,
  .empty-actions,
  .drawer-close-btn {
    width: 100%;
  }

  .empty-actions {
    display: grid;
  }
}
</style>

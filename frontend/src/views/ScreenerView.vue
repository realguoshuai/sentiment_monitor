<template>
  <div class="screener-shell">
    <!-- 顶部栏 -->
    <header class="topbar">
      <div class="topbar-title">
        <button class="icon-btn" type="button" title="返回首页" @click="router.push('/')">←</button>
        <div class="title-block">
          <h1>条件选股工作台</h1>
          <p class="title-sub">价值投资 · 多因子筛选与候选池洞察</p>
        </div>
        <span class="status-dot" :class="{ ready: screenerMeta.ready }"></span>
        <span class="topbar-meta">{{ screenerMeta.count || 0 }} 只 / {{ screenerMeta.industry_count || 0 }} 行业</span>
        <span v-if="screenerMeta.ready && screenerMeta.snapshot_date" class="snapshot-date-label">📸 {{ screenerMeta.snapshot_date }}</span>
      </div>
      <div class="topbar-actions">
        <button class="primary-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
          <span v-if="refreshing" class="btn-spinner"></span>
          {{ refreshing ? '刷新中...' : '刷新快照' }}
        </button>
      </div>
    </header>

    <!-- 筛选卡片 -->
    <section class="filter-card">
      <div class="filter-toolbar">
        <div class="search-wrap">
          <svg class="search-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="7" /><path stroke-linecap="round" d="M21 21l-4.3-4.3" />
          </svg>
          <input v-model.trim="filters.q" class="filter-input search-input" placeholder="搜索名称 / 代码" @keyup.enter="applyFilters(1)" />
        </div>

        <button class="filter-toggle" type="button" :class="{ active: filtersExpanded }" @click="filtersExpanded = !filtersExpanded">
          <svg class="toggle-ico" :class="{ open: filtersExpanded }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 9l6 6 6-6" />
          </svg>
          筛选条件
          <span v-if="activeFilterCount" class="count-badge">{{ activeFilterCount }}</span>
        </button>

        <div class="toolbar-actions">
          <button class="primary-btn" type="button" @click="applyFilters(1)" :disabled="loading">筛选</button>
          <button class="secondary-btn" type="button" @click="resetFilters">重置</button>
        </div>
      </div>

      <!-- 策略预设 -->
      <div class="preset-row">
        <span class="preset-label">策略</span>
        <button
          v-for="preset in presetCards"
          :key="preset.key"
          class="preset-pill"
          :class="[`preset-${preset.tone}`, { on: presetActive(preset.key) }]"
          type="button"
          @click="applyPreset(preset.key)"
        >
          <span class="preset-title">{{ preset.title }}</span>
          <small>{{ preset.metrics.join(' / ') }}</small>
        </button>
      </div>

      <!-- 排序与异常 -->
      <div class="sort-row">
        <span class="sort-label">排序</span>
        <div class="sort-select-wrap">
          <select v-model="filters.sort_by" class="filter-select" @change="applyFilters(1)">
            <option value="pb">PB</option>
            <option value="pe">PE</option>
            <option value="roe">ROE</option>
            <option value="roi">ROI</option>
            <option value="dividend_yield">股息率</option>
            <option value="market_cap">总市值</option>
            <option value="price">价格</option>
            <option value="net_cash_ratio">净现比</option>
            <option value="cfo_yield">现金流收益率</option>
            <option value="fcf_yield">FCF 收益率</option>
            <option value="f_score">F-Score</option>
            <option value="moat_label">护城河</option>
            <option value="debt_to_assets_pct">负债率</option>
            <option value="dividend_years">连续分红年数</option>
          </select>
        </div>
        <button class="sort-dir-btn" type="button" @click="filters.sort_order = filters.sort_order === 'asc' ? 'desc' : 'asc'; applyFilters(1)">
          <span class="dir-ico">{{ filters.sort_order === 'asc' ? '↑' : '↓' }}</span>
          {{ filters.sort_order === 'asc' ? '升序' : '降序' }}
        </button>
        <label class="toggle-label">
          <input v-model="filters.include_anomalies" type="checkbox" @change="applyFilters(1)" />
          <span>含异常样本</span>
        </label>
      </div>

      <!-- 可折叠分组筛选 -->
      <div v-show="filtersExpanded" class="filter-grid">
        <div class="filter-group-card">
          <h4 class="group-title"><span class="group-bar bar-teal"></span>估值指标</h4>
          <div class="group-fields">
            <label class="field">
              <span>PB ≤</span>
              <input v-model.number="filters.pb_max" type="number" step="0.1" placeholder="--" />
            </label>
            <label class="field">
              <span>PE ≤</span>
              <input v-model.number="filters.pe_max" type="number" step="0.1" placeholder="--" />
            </label>
            <label class="field">
              <span>市值 ≥</span>
              <input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="--" />
              <em class="unit">亿</em>
            </label>
          </div>
        </div>

        <div class="filter-group-card">
          <h4 class="group-title"><span class="group-bar bar-indigo"></span>盈利质量</h4>
          <div class="group-fields">
            <label class="field">
              <span>ROE ≥</span>
              <input v-model.number="filters.roe_min" type="number" step="0.5" placeholder="--" />
              <em class="unit">%</em>
            </label>
            <label class="field">
              <span>净现比 ≥</span>
              <input v-model.number="filters.net_cash_ratio_min" type="number" step="0.1" placeholder="--" />
            </label>
            <label class="field">
              <span>现金流收益 ≥</span>
              <input v-model.number="filters.cfo_yield_min" type="number" step="0.5" placeholder="--" />
              <em class="unit">%</em>
            </label>
            <label class="field">
              <span>FCF 收益 ≥</span>
              <input v-model.number="filters.fcf_yield_min" type="number" step="0.5" placeholder="--" />
              <em class="unit">%</em>
            </label>
          </div>
        </div>

        <div class="filter-group-card">
          <h4 class="group-title"><span class="group-bar bar-amber"></span>分红与护城河</h4>
          <div class="group-fields">
            <label class="field">
              <span>股息率 ≥</span>
              <input v-model.number="filters.dividend_yield_min" type="number" step="0.1" placeholder="--" />
              <em class="unit">%</em>
            </label>
            <label class="field">
              <span>连续分红 ≥</span>
              <input v-model.number="filters.dividend_years_min" type="number" step="1" min="0" placeholder="--" />
              <em class="unit">年</em>
            </label>
            <label class="field">
              <span>护城河</span>
              <select v-model="filters.moat" class="field-select">
                <option value="">不限</option>
                <option value="wide">宽</option>
                <option value="medium">中</option>
                <option value="none">无</option>
              </select>
            </label>
            <label class="field">
              <span>负债率 ≤</span>
              <input v-model.number="filters.debt_to_assets_max" type="number" step="1" placeholder="--" />
              <em class="unit">%</em>
            </label>
            <label class="field">
              <span>F-Score ≥</span>
              <input v-model.number="filters.f_score_min" type="number" step="1" min="0" max="9" placeholder="--" />
            </label>
          </div>
        </div>
      </div>

      <!-- 已生效筛选标签 -->
      <div v-if="activeFilterTags.length" class="active-tags">
        <span v-for="tag in activeFilterTags" :key="tag" class="active-tag">{{ tag }}</span>
      </div>
    </section>

    <div v-if="errorMessage" class="error-banner">
      <span class="err-ico">!</span>{{ errorMessage }}
    </div>

    <!-- 结果区 -->
    <main class="main-area">
      <!-- 空状态 -->
      <div v-if="!screenerMeta.ready" class="empty-state">
        <div class="empty-ico">🛰️</div>
        <strong>还没有可用快照</strong>
        <p>先刷新一次全市场快照，之后就可以连续筛选和排序。</p>
        <button class="primary-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '立即生成快照' }}
        </button>
      </div>

      <div v-else-if="loading" class="empty-state">
        <div class="empty-spinner"></div>
        <strong>正在更新候选池</strong>
        <p>当前只查询本地快照，不会重新抓取全市场数据。</p>
      </div>

      <div v-else-if="!results.length" class="empty-state">
        <div class="empty-ico">🔍</div>
        <strong>当前没有命中结果</strong>
        <p>建议先放宽 PB、PE 或股息率阈值，再重新筛选。</p>
        <button class="secondary-btn" type="button" @click="resetFilters">回到默认视图</button>
      </div>

      <template v-else>
        <!-- 统计条 -->
        <div class="stats-bar">
          <div class="stat-item">
            <span class="stat-ico ico-hit">◎</span>
            <div class="stat-body">
              <span>命中</span><strong>{{ pagination.total }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-cheap">⬇</span>
            <div class="stat-body">
              <span>低 PB</span><strong>{{ valuationBuckets.lowPb }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-income">✦</span>
            <div class="stat-body">
              <span>高股息</span><strong>{{ valuationBuckets.highDividend }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-quality">▲</span>
            <div class="stat-body">
              <span>高 ROE</span><strong>{{ valuationBuckets.highRoe }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-cash">≋</span>
            <div class="stat-body">
              <span>高 FCF</span><strong>{{ valuationBuckets.highFcf }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-monitor">★</span>
            <div class="stat-body">
              <span>已监控</span><strong>{{ monitoredCount }}</strong>
            </div>
          </div>
          <div class="stat-item">
            <span class="stat-ico ico-sort">⇅</span>
            <div class="stat-body">
              <span>排序</span><strong class="stat-sort">{{ activeSortLabel }}</strong>
            </div>
          </div>
        </div>

        <!-- 表格 -->
        <div class="table-shell">
          <table class="result-table">
            <thead>
              <tr class="cat-row">
                <th class="cat-cell sticky-col" rowspan="2">公司</th>
                <th class="cat-cell sticky-col action" rowspan="2">动作</th>
                <th class="cat-cell" colspan="1">行情</th>
                <th class="cat-cell" colspan="2">估值</th>
                <th class="cat-cell" colspan="3">盈利质量</th>
                <th class="cat-cell" colspan="2">现金流</th>
                <th class="cat-cell" colspan="3">护城河与财务</th>
                <th class="cat-cell" colspan="2">分红</th>
              </tr>
              <tr class="field-row">
                <th><button class="sort-header" type="button" @click="toggleSort('price')">价格/市值 <span :class="{ active: filters.sort_by === 'price' }">{{ getSortIndicator('price') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('pe')">PE <span :class="{ active: filters.sort_by === 'pe' }">{{ getSortIndicator('pe') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('pb')">PB <span :class="{ active: filters.sort_by === 'pb' }">{{ getSortIndicator('pb') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('roe')">ROE <span :class="{ active: filters.sort_by === 'roe' }">{{ getSortIndicator('roe') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('roi')">ROI <span :class="{ active: filters.sort_by === 'roi' }">{{ getSortIndicator('roi') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('net_cash_ratio')">净现比 <span :class="{ active: filters.sort_by === 'net_cash_ratio' }">{{ getSortIndicator('net_cash_ratio') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('cfo_yield')">现金流收益 <span :class="{ active: filters.sort_by === 'cfo_yield' }">{{ getSortIndicator('cfo_yield') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('fcf_yield')">FCF 收益率 <span :class="{ active: filters.sort_by === 'fcf_yield' }">{{ getSortIndicator('fcf_yield') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('f_score')">F-Score <span :class="{ active: filters.sort_by === 'f_score' }">{{ getSortIndicator('f_score') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('moat_label')">护城河 <span :class="{ active: filters.sort_by === 'moat_label' }">{{ getSortIndicator('moat_label') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('debt_to_assets_pct')">负债率 <span :class="{ active: filters.sort_by === 'debt_to_assets_pct' }">{{ getSortIndicator('debt_to_assets_pct') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('dividend_yield')">股息率 <span :class="{ active: filters.sort_by === 'dividend_yield' }">{{ getSortIndicator('dividend_yield') }}</span></button></th>
                <th><button class="sort-header" type="button" @click="toggleSort('dividend_years')">连续分红 <span :class="{ active: filters.sort_by === 'dividend_years' }">{{ getSortIndicator('dividend_years') }}</span></button></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in results" :key="row.symbol">
                <td class="sticky-col">
                  <div class="company-cell">
                    <strong>{{ row.name }}</strong>
                    <span v-if="row.is_monitored" class="monitor-badge">监控</span>
                    <div class="company-sub">
                      <span class="symbol-badge">{{ row.symbol }}</span>
                      <span v-if="row.industry" class="industry-badge">{{ row.industry }}</span>
                    </div>
                  </div>
                </td>
                <td class="sticky-col action">
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
                <td><span class="metric-pill" :class="getMetricTone('net_cash_ratio', row.net_cash_ratio)">{{ formatNumber(row.net_cash_ratio) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('cfo_yield', row.cfo_yield)">{{ formatPct(row.cfo_yield) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('fcf_yield', row.fcf_yield)">{{ formatPct(row.fcf_yield) }}</span></td>
                <td><span class="metric-pill fscore-pill">{{ row.f_score }}</span></td>
                <td>
                  <span class="moat-pill" :class="`moat-${row.moat_label || 'none'}`">{{ row.moat_label === 'wide' ? '宽' : row.moat_label === 'medium' ? '中' : row.moat_label === 'none' ? '无' : '—' }}</span>
                </td>
                <td><span class="metric-pill" :class="row.debt_to_assets_pct > 60 ? 'bad' : ''">{{ formatPct(row.debt_to_assets_pct) }}</span></td>
                <td><span class="metric-pill" :class="getMetricTone('dividend', row.dividend_yield)">{{ formatPct(row.dividend_yield) }}</span></td>
                <td>{{ row.dividend_years }} 年</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页 -->
        <div class="pager">
          <button class="secondary-btn" type="button" @click="goToPage(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">上一页</button>
          <span class="pager-info">第 {{ pagination.page }} / {{ pagination.total_pages || 1 }} 页 · 共 {{ pagination.total }} 只</span>
          <button class="secondary-btn" type="button" @click="goToPage(pagination.page + 1)" :disabled="pagination.page >= pagination.total_pages || loading">下一页</button>
        </div>

        <!-- 底部洞察 -->
        <div class="insight-row">
          <section class="insight-card">
            <div class="insight-head">
              <span class="insight-bar bar-teal"></span>
              <h3>优先研究</h3>
              <span class="insight-hint">综合估值 / 盈利 / 现金流打分</span>
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
                  <button class="mini-btn primary" type="button" @click="addToMonitor(idea)" :disabled="idea.is_monitored || addLoadingSymbol === idea.symbol">
                    {{ idea.is_monitored ? '已监控' : '加入' }}
                  </button>
                </div>
              </article>
            </div>
            <p v-else class="side-empty">拿到结果后，这里会自动列出更值得先看的标的。</p>
          </section>

          <section class="insight-card">
            <div class="insight-head">
              <span class="insight-bar bar-indigo"></span>
              <h3>行业分布</h3>
              <span class="insight-hint">当前候选池行业占比</span>
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
        </div>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { stockApi, type ScreenerMeta, type ScreenerResult } from '@/api'

type ScreenerPreset = 'dividend_value' | 'quality_value' | 'cash_cow' | 'ten_year_payback'
type SortableField = 'price' | 'pe' | 'pb' | 'roe' | 'roi' | 'dividend_yield' | 'market_cap' | 'net_cash_ratio' | 'cfo_yield' | 'fcf_yield' | 'f_score' | 'moat_label' | 'debt_to_assets_pct' | 'dividend_years'

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
const filtersExpanded = ref(false)

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
  fcf_yield_min: null as number | null,
  f_score_min: null as number | null,
  moat: '' as string,
  debt_to_assets_max: null as number | null,
  dividend_years_min: null as number | null,
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
    metrics: ['PB ≤ 1.5', 'PE ≤ 15', '股息率 ≥ 3%'],
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
  {
    key: 'ten_year_payback',
    title: '十年回本',
    tagline: 'Preset 04',
    description: '自由现金流 FCF 收益率 ≥ 10%，近似十年回本。',
    metrics: ['FCF 收益率 ≥ 10%', '净现比 ≥ 1.0'],
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
  fcf_yield: 'FCF 收益率',
  f_score: 'F-Score',
  moat_label: '护城河',
  debt_to_assets_pct: '负债率',
  dividend_years: '连续分红年数',
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
  fcf_yield: 'desc',
  f_score: 'desc',
  moat_label: 'desc',
  debt_to_assets_pct: 'asc',
  dividend_years: 'desc',
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
  if (filters.fcf_yield_min !== null) count += 1
  if (filters.f_score_min !== null) count += 1
  if (filters.moat) count += 1
  if (filters.debt_to_assets_max !== null) count += 1
  if (filters.dividend_years_min !== null) count += 1
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
  if (filters.fcf_yield_min !== null) tags.push(`FCF 收益率 ≥ ${filters.fcf_yield_min}%`)
  if (filters.f_score_min !== null) tags.push(`F-Score ≥ ${filters.f_score_min}`)
  if (filters.moat) tags.push(`护城河 = ${filters.moat === 'wide' ? '宽' : filters.moat === 'medium' ? '中' : '无'}`)
  if (filters.debt_to_assets_max !== null) tags.push(`负债率 ≤ ${filters.debt_to_assets_max}%`)
  if (filters.dividend_years_min !== null) tags.push(`连续分红 ≥ ${filters.dividend_years_min} 年`)
  if (filters.include_anomalies) tags.push('包含异常样本')
  return tags
})

const monitoredCount = computed(() => results.value.filter((item) => item.is_monitored).length)

const valuationBuckets = computed(() => ({
  lowPb: results.value.filter((item) => Number(item.pb) > 0 && Number(item.pb) <= 1.5).length,
  highDividend: results.value.filter((item) => Number(item.dividend_yield) >= 5).length,
  highRoe: results.value.filter((item) => Number(item.roe_pct) >= 15).length,
  highFcf: results.value.filter((item) => Number(item.fcf_yield) >= 10).length,
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
    const fcf = Number(row.fcf_yield)

    if (!Number.isNaN(fcf) && fcf >= 10) {
      score += 25
      reasons.push(`FCF 收益率 ${fcf.toFixed(1)}%`)
    } else if (!Number.isNaN(fcf) && fcf >= 5) {
      score += 10
    }

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

const presetActive = (key: ScreenerPreset): boolean => {
  if (key === 'dividend_value') {
    return filters.pb_max === 1.5 && filters.pe_max === 15 && filters.dividend_yield_min === 3
  }
  if (key === 'quality_value') {
    return filters.pb_max === 3 && filters.pe_max === 25 && filters.roe_min === 15
  }
  if (key === 'cash_cow') {
    return filters.roe_min === 12 && filters.net_cash_ratio_min === 1.0 && filters.cfo_yield_min === 6
  }
  if (key === 'ten_year_payback') {
    return filters.fcf_yield_min === 10 && filters.net_cash_ratio_min === 1.0
  }
  return false
}

const buildParams = (page = 1) => ({
  q: filters.q || undefined,
  pb_max: filters.pb_max ?? undefined,
  pe_max: filters.pe_max ?? undefined,
  roe_min: filters.roe_min ?? undefined,
  dividend_yield_min: filters.dividend_yield_min ?? undefined,
  market_cap_min: filters.market_cap_min_100m ? filters.market_cap_min_100m * 1e8 : undefined,
  net_cash_ratio_min: filters.net_cash_ratio_min ?? undefined,
  cfo_yield_min: filters.cfo_yield_min ?? undefined,
  fcf_yield_min: filters.fcf_yield_min ?? undefined,
  f_score_min: filters.f_score_min ?? undefined,
  moat: filters.moat || undefined,
  debt_to_assets_max: filters.debt_to_assets_max ?? undefined,
  dividend_years_min: filters.dividend_years_min ?? undefined,
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
      for (let i = 0; i < 200; i++) {
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
  filters.fcf_yield_min = null
  filters.f_score_min = null
  filters.moat = ''
  filters.debt_to_assets_max = null
  filters.dividend_years_min = null
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
  filters.fcf_yield_min = null
  filters.f_score_min = null
  filters.moat = ''
  filters.debt_to_assets_max = null
  filters.dividend_years_min = null
  filters.include_anomalies = false
  filters.sort_by = 'pb'
  filters.sort_order = 'asc'

  if (preset === 'ten_year_payback') {
    filters.fcf_yield_min = 10
    filters.net_cash_ratio_min = 1.0
    filters.sort_by = 'fcf_yield'
    filters.sort_order = 'desc'
  }

  if (preset === 'dividend_value') {
    filters.pb_max = 1.5
    filters.pe_max = 15
    filters.dividend_yield_min = 3
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

const getMetricTone = (metric: 'pb' | 'pe' | 'roe' | 'roi' | 'dividend' | 'net_cash_ratio' | 'cfo_yield' | 'fcf_yield', value?: number | null) => {
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

  if (metric === 'fcf_yield') {
    if (numeric >= 10) return 'tone-strong'
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
  --bg: #eef2f6;
  --card: #ffffff;
  --ink: #0f172a;
  --ink-soft: #334155;
  --muted: #64748b;
  --faint: #94a3b8;
  --line: #e2e8f0;
  --line-soft: #f1f5f9;
  --accent: #0f766e;
  --accent-dark: #0b5f59;
  --accent-soft: #f0fdfa;
  --primary: #0088ff;
  --danger: #b42318;
  --shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 16px rgba(15, 23, 42, 0.06);
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  padding: 18px 22px;
  max-width: 1680px;
  margin: 0 auto;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

/* 顶部栏 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.topbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-block {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.topbar-title h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: 0.01em;
}

.title-sub {
  margin: 2px 0 0;
  font-size: 0.7rem;
  color: var(--faint);
  font-weight: 500;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #d97706;
  flex-shrink: 0;
}

.status-dot.ready {
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
}

.topbar-meta {
  font-size: 0.78rem;
  color: var(--muted);
  font-weight: 600;
}

.snapshot-date-label {
  font-size: 0.76rem;
  color: var(--primary);
  font-weight: 600;
  background: rgba(0, 136, 255, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
}

/* 筛选卡片 */
.filter-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 14px 16px;
  margin-bottom: 14px;
  display: grid;
  gap: 12px;
}

.filter-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  flex: 1;
  min-width: 220px;
}

.search-ico {
  position: absolute;
  left: 11px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--faint);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: 38px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0 12px 0 34px;
  font-size: 0.85rem;
  background: #f8fafc;
  color: var(--ink);
  transition: border-color 0.15s, background 0.15s;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
  background: #fff;
}

.filter-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #f8fafc;
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--ink-soft);
  cursor: pointer;
  transition: all 0.15s;
}

.filter-toggle:hover {
  background: #f1f5f9;
}

.filter-toggle.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-dark);
}

.toggle-ico {
  width: 15px;
  height: 15px;
  transition: transform 0.2s ease;
}

.toggle-ico.open {
  transform: rotate(180deg);
}

.count-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  display: inline-grid;
  place-items: center;
  background: var(--accent);
  color: #fff;
  font-size: 0.68rem;
  font-weight: 800;
  border-radius: 999px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.preset-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preset-label {
  font-size: 0.74rem;
  font-weight: 800;
  color: var(--faint);
  letter-spacing: 0.04em;
}

.preset-pill {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-left-width: 3px;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.preset-pill:hover {
  background: #f8fafc;
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}

.preset-pill.on {
  background: var(--accent-soft);
  border-color: #99f6e4;
}

.preset-title {
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--ink);
}

.preset-pill small {
  font-size: 0.66rem;
  color: var(--faint);
  font-weight: 600;
}

.preset-income { border-left-color: #f59e0b; }
.preset-quality { border-left-color: #10b981; }
.preset-steady { border-left-color: #3b82f6; }

.sort-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}

.sort-label {
  font-size: 0.74rem;
  font-weight: 800;
  color: var(--faint);
  letter-spacing: 0.04em;
}

.sort-select-wrap {
  position: relative;
}

.filter-select {
  height: 34px;
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 0 28px 0 10px;
  font-size: 0.8rem;
  background: #f8fafc url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='none' stroke='%2394a3b8' stroke-width='2' viewBox='0 0 24 24'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") no-repeat right 9px center;
  color: var(--ink);
  appearance: none;
  cursor: pointer;
}

.filter-select:focus {
  outline: none;
  border-color: var(--accent);
}

.sort-dir-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #f8fafc;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--ink-soft);
  cursor: pointer;
  transition: all 0.15s;
}

.sort-dir-btn:hover {
  background: #f1f5f9;
}

.dir-ico {
  font-size: 0.9rem;
  color: var(--accent);
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.76rem;
  color: var(--muted);
  cursor: pointer;
  margin-left: auto;
}

.toggle-label input {
  accent-color: var(--accent);
  width: 15px;
  height: 15px;
}

/* 可折叠分组筛选 */
.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.filter-group-card {
  background: #f8fafc;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px;
}

.group-title {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 10px;
  font-size: 0.82rem;
  font-weight: 800;
  color: var(--ink);
}

.group-bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
}

.bar-teal { background: #0f766e; }
.bar-indigo { background: #6366f1; }
.bar-amber { background: #f59e0b; }

.group-fields {
  display: grid;
  gap: 8px;
}

.field {
  display: grid;
  grid-template-columns: 84px 1fr auto;
  align-items: center;
  gap: 8px;
}

.field > span {
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--muted);
}

.field input,
.field-select {
  height: 32px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 9px;
  font-size: 0.82rem;
  background: #fff;
  color: var(--ink);
  width: 100%;
}

.field input:focus,
.field-select:focus {
  outline: none;
  border-color: var(--accent);
}

.unit {
  font-size: 0.7rem;
  color: var(--faint);
  font-style: normal;
}

.active-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: 4px;
}

.active-tag {
  padding: 4px 10px;
  font-size: 0.72rem;
  font-weight: 700;
  background: var(--accent-soft);
  color: var(--accent-dark);
  border: 1px solid #99f6e4;
  border-radius: 999px;
}

/* 按钮 */
.icon-btn,
.primary-btn,
.secondary-btn,
.mini-btn {
  border: 1px solid var(--line);
  cursor: pointer;
  font-weight: 700;
  transition: all 0.15s;
}

.icon-btn {
  width: 34px;
  height: 34px;
  background: #fff;
  color: var(--ink-soft);
  font-size: 1.05rem;
  border-radius: 9px;
  display: grid;
  place-items: center;
}

.icon-btn:hover {
  background: #f1f5f9;
}

.primary-btn {
  height: 38px;
  padding: 0 18px;
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-size: 0.84rem;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.primary-btn:hover { background: var(--accent-dark); }

.secondary-btn,
.mini-btn {
  height: 34px;
  padding: 0 14px;
  background: #fff;
  color: var(--ink-soft);
  font-size: 0.8rem;
  border-radius: 9px;
}

.secondary-btn:hover { background: #f8fafc; }

.mini-btn {
  height: 28px;
  padding: 0 10px;
  font-size: 0.74rem;
}

.mini-btn:hover { background: #f8fafc; }

.mini-btn.primary {
  background: var(--accent-soft);
  border-color: #99f6e4;
  color: var(--accent-dark);
}

.primary-btn:disabled,
.secondary-btn:disabled,
.mini-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 错误 */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  margin-bottom: 14px;
  color: var(--danger);
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  font-size: 0.84rem;
  font-weight: 700;
}

.err-ico {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  background: var(--danger);
  color: #fff;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 900;
  flex-shrink: 0;
}

/* 主区域 */
.main-area {
  display: grid;
  gap: 14px;
}

/* 统计条 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 10px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--shadow);
}

.stat-ico {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  font-size: 1rem;
  flex-shrink: 0;
}

.ico-hit { background: #eef2ff; color: #4f46e5; }
.ico-cheap { background: #ecfdf5; color: #059669; }
.ico-income { background: #fff7ed; color: #ea580c; }
.ico-quality { background: #f0fdfa; color: #0d9488; }
.ico-cash { background: #eff6ff; color: #2563eb; }
.ico-monitor { background: #fef9c3; color: #ca8a04; }
.ico-sort { background: #f3e8ff; color: #9333ea; }

.stat-body {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.stat-body span {
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--faint);
  letter-spacing: 0.03em;
}

.stat-body strong {
  font-size: 1.05rem;
  font-weight: 900;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.stat-sort {
  font-size: 0.78rem !important;
  font-weight: 800 !important;
  color: var(--accent-dark) !important;
}

/* 表格 */
.table-shell {
  overflow: auto;
  max-height: calc(100vh - 420px);
  min-height: 420px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--card);
  box-shadow: var(--shadow);
}

.result-table {
  width: 100%;
  min-width: 1080px;
  border-collapse: separate;
  border-spacing: 0;
}

.result-table thead tr.cat-row th {
  position: sticky;
  top: 0;
  z-index: 4;
  height: 32px;
  background: #f1f5f9;
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-align: center;
  border-bottom: 1px solid var(--line);
}

.result-table thead tr.field-row th {
  position: sticky;
  top: 32px;
  z-index: 3;
  height: 36px;
  background: #f8fafc;
  color: var(--faint);
  font-size: 0.72rem;
  font-weight: 700;
  text-align: center;
  border-bottom: 1px solid var(--line);
  padding: 0 10px;
}

.result-table tbody td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--line-soft);
  text-align: center;
  vertical-align: middle;
  white-space: nowrap;
  color: var(--ink-soft);
  font-size: 0.82rem;
}

.result-table tbody tr:hover td {
  background: #f8fbfd;
}

/* 分类表头分组底色 */
.cat-cell:nth-child(3),
.cat-cell:nth-child(4) { box-shadow: inset 0 -2px 0 #cbd5e1; }
.cat-cell:nth-child(5),
.cat-cell:nth-child(6),
.cat-cell:nth-child(7) { box-shadow: inset 0 -2px 0 #c7d2fe; }
.cat-cell:nth-child(8),
.cat-cell:nth-child(9) { box-shadow: inset 0 -2px 0 #bae6fd; }
.cat-cell:nth-child(10),
.cat-cell:nth-child(11),
.cat-cell:nth-child(12) { box-shadow: inset 0 -2px 0 #ddd6fe; }
.cat-cell:nth-child(13),
.cat-cell:nth-child(14) { box-shadow: inset 0 -2px 0 #fde68a; }

/* 固定首列 */
.result-table th.sticky-col,
.result-table td.sticky-col {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #fff;
  text-align: left;
}

.result-table thead tr.cat-row th.sticky-col {
  z-index: 6;
  background: #f1f5f9;
}

.result-table thead tr.cat-row th.sticky-col.action {
  left: 150px;
  z-index: 6;
  background: #f1f5f9;
}

.result-table tbody td.sticky-col.action {
  left: 150px;
  z-index: 2;
}

.result-table tbody tr:hover td.sticky-col {
  background: #f8fbfd;
}

.sort-header {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.sort-header span {
  color: var(--faint);
  font-size: 0.8rem;
}

.sort-header span.active {
  color: var(--accent);
  font-weight: 900;
}

.company-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.company-cell strong {
  font-size: 0.86rem;
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
  padding: 1px 6px;
  font-size: 0.66rem;
  font-weight: 700;
  border: 1px solid var(--line);
  background: #f8fafc;
  color: var(--muted);
  border-radius: 5px;
}

.monitor-badge {
  color: var(--accent-dark);
  border-color: #99f6e4;
  background: var(--accent-soft);
}

.row-actions {
  display: flex;
  gap: 4px;
}

.price-cell {
  display: grid;
  gap: 2px;
  justify-items: center;
}

.price-cell strong {
  font-size: 0.86rem;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.price-cell small {
  font-size: 0.66rem;
  color: var(--faint);
  font-weight: 700;
}

.metric-pill {
  display: inline-flex;
  min-width: 46px;
  justify-content: center;
  padding: 3px 7px;
  border-radius: 999px;
  font-weight: 800;
  font-size: 0.76rem;
  font-variant-numeric: tabular-nums;
  border: 1px solid var(--line);
  background: #f8fafc;
  color: var(--muted);
}

.tone-cheap, .tone-income, .tone-strong, .tone-quality {
  background: #ecfdf5;
  border-color: #a7f3d0;
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

.metric-pill.bad {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 600;
}

.pager-info {
  color: var(--faint);
}

/* 空状态 */
.empty-state {
  min-height: 320px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  text-align: center;
  color: var(--muted);
  border: 1px dashed var(--line);
  background: var(--card);
  border-radius: 16px;
  box-shadow: var(--shadow);
}

.empty-ico {
  font-size: 2.4rem;
}

.empty-spinner {
  width: 30px;
  height: 30px;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.empty-state strong {
  color: var(--ink);
  font-size: 1.05rem;
}

.empty-state p {
  margin: 0;
  max-width: 380px;
  line-height: 1.6;
  font-size: 0.88rem;
}

/* 底部洞察 */
.insight-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.insight-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  box-shadow: var(--shadow);
  display: grid;
  gap: 12px;
}

.insight-head {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}

.insight-bar {
  width: 4px;
  height: 16px;
  border-radius: 2px;
}

.insight-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--ink);
}

.insight-hint {
  margin-left: auto;
  font-size: 0.68rem;
  color: var(--faint);
  font-weight: 600;
}

.idea-list {
  display: grid;
  gap: 9px;
}

.idea-card {
  display: grid;
  gap: 8px;
  padding: 11px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #f8fafc;
  transition: all 0.15s;
}

.idea-card:hover {
  border-color: #cbd5e1;
  box-shadow: var(--shadow);
}

.idea-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.idea-head div {
  display: grid;
  gap: 2px;
}

.idea-head strong {
  font-size: 0.86rem;
  color: var(--ink);
}

.idea-head span {
  font-size: 0.72rem;
  color: var(--muted);
}

.idea-head b {
  min-width: 34px;
  height: 26px;
  display: inline-grid;
  place-items: center;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-size: 0.78rem;
  font-weight: 900;
  border-radius: 8px;
}

.idea-reasons {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.idea-reasons span {
  padding: 2px 7px;
  font-size: 0.68rem;
  font-weight: 700;
  background: #fff;
  border: 1px solid var(--line);
  color: var(--muted);
  border-radius: 6px;
}

.idea-actions {
  display: flex;
  gap: 5px;
}

.industry-list {
  display: grid;
  gap: 9px;
}

.industry-row {
  display: grid;
  gap: 5px;
}

.industry-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
}

.industry-label strong {
  color: var(--ink);
  font-weight: 700;
}

.industry-label span {
  color: var(--faint);
  font-size: 0.72rem;
}

.industry-bar-track {
  height: 7px;
  overflow: hidden;
  background: #edf2f7;
  border-radius: 999px;
}

.industry-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #38bdf8);
  border-radius: 999px;
}

.side-empty {
  margin: 0;
  color: var(--faint);
  font-size: 0.82rem;
}

/* 响应式 */
@media (max-width: 1100px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .stats-bar {
    grid-template-columns: repeat(4, 1fr);
  }

  .insight-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .screener-shell {
    padding: 12px;
  }

  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .stats-bar {
    grid-template-columns: repeat(2, 1fr);
  }

  .table-shell {
    max-height: none;
  }
}
</style>

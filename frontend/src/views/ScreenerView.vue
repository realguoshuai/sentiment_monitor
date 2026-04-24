<template>
  <div class="screener-shell">
    <div class="shell-glow shell-glow-left"></div>
    <div class="shell-glow shell-glow-right"></div>

    <main class="workspace">
      <section class="hero panel-card">
        <div class="hero-copy">
          <span class="eyebrow">A-share Value Research Desk</span>
          <h1>价值筛选工作台</h1>
          <p>
            把常用条件、排序和候选池放在同一视野里。先快速缩小范围，再从结果表和右侧洞察判断哪些公司值得继续深入。
          </p>
          <div class="hero-pills">
            <span class="hero-pill">年报 ROE 优先</span>
            <span class="hero-pill">本地快照筛选</span>
            <span class="hero-pill">表头点击即排序</span>
          </div>
        </div>

        <div class="hero-actions">
          <button class="ghost-btn" type="button" @click="router.push('/')">返回首页</button>
          <button class="refresh-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
            {{ refreshing ? '刷新中...' : '刷新全市场快照' }}
          </button>
        </div>
      </section>

      <section class="toolbar panel-card">
        <div class="toolbar-head">
          <div>
            <span class="eyebrow">Screening Controls</span>
            <h2>筛选与排序</h2>
          </div>
          <div class="toolbar-meta">
            <span class="meta-chip">快照 {{ screenerMeta.snapshot_date || '--' }}</span>
            <span class="meta-chip">候选 {{ pagination.total }}</span>
            <span class="meta-chip">排序 {{ activeSortLabel }}</span>
          </div>
        </div>

        <form class="control-grid" @submit.prevent="applyFilters(1)">
          <label class="field search-field">
            <span>名称 / 代码</span>
            <input v-model.trim="filters.q" placeholder="例如：银行 / 600000 / 贵州茅台" />
          </label>

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

          <label class="field">
            <span>市值 ≥（亿）</span>
            <input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="100" />
          </label>

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

          <label class="field checkbox-field">
            <span>样本范围</span>
            <div class="checkbox-wrap">
              <input v-model="filters.include_anomalies" type="checkbox" />
              <strong>包含异常估值样本</strong>
            </div>
          </label>

          <div class="control-actions">
            <button class="ghost-btn" type="button" @click="resetFilters">重置条件</button>
            <button class="apply-btn" type="submit" :disabled="loading">开始筛选</button>
          </div>
        </form>

        <div class="preset-row">
          <button
            v-for="preset in presetCards"
            :key="preset.key"
            class="preset-card"
            :class="`preset-${preset.tone}`"
            type="button"
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

        <div class="active-tag-row">
          <span v-for="tag in activeFilterTags" :key="tag" class="active-tag">{{ tag }}</span>
          <span v-if="!activeFilterTags.length" class="active-tag muted">当前没有额外筛选条件</span>
        </div>
      </section>

      <section class="summary-strip">
        <article class="summary-card panel-card">
          <span>快照状态</span>
          <strong>{{ screenerMeta.ready ? '可筛选' : '未准备' }}</strong>
          <p>{{ screenerMeta.ready ? '当前查询走本地快照，适合连续试错。' : '需要先刷新一次全市场快照。' }}</p>
        </article>
        <article class="summary-card panel-card">
          <span>当前命中</span>
          <strong>{{ pagination.total }}</strong>
          <p>共 {{ pagination.total_pages || 1 }} 页，当前第 {{ pagination.page }} 页。</p>
        </article>
        <article class="summary-card panel-card">
          <span>筛选强度</span>
          <strong>{{ activeFilterCount }} 项</strong>
          <p>{{ activeFilterCount ? `结果密度 ${coverageDensityLabel}` : '当前更接近全市场浏览模式。' }}</p>
        </article>
        <article class="summary-card panel-card">
          <span>ROE 口径</span>
          <strong>{{ screenerMeta.roe_basis_label || '--' }}</strong>
          <p>排序和判断时优先参考当前快照中的同一口径。</p>
        </article>
      </section>

      <div v-if="errorMessage" class="error-banner panel-card">
        {{ errorMessage }}
      </div>

      <section class="workspace-grid">
        <section class="result-panel panel-card">
          <div class="panel-head">
            <div class="candidate-headline">
              <span class="eyebrow">Candidates</span>
              <h2>候选池</h2>
              <p class="panel-copy">
                先用表格做第一轮剔除，再把感兴趣的标的加入监控或进入深度分析。
              </p>
            </div>
            <div class="result-status-stack">
              <span class="status-pill">{{ loading ? '正在筛选...' : `当前排序：${activeSortLabel}` }}</span>
              <span class="status-note">点击表头可以直接切换排序。</span>
            </div>
          </div>

          <div v-if="!screenerMeta.ready" class="empty-state">
            <div class="empty-dot"></div>
            <strong>还没有可用快照</strong>
            <p>先刷新一次全市场快照，之后这页就能像工作台一样连续筛选。</p>
            <button class="refresh-btn" type="button" @click="refreshSnapshot" :disabled="refreshing">
              {{ refreshing ? '刷新中...' : '立即生成快照' }}
            </button>
          </div>

          <div v-else-if="loading" class="empty-state">
            <div class="empty-dot pulse"></div>
            <strong>正在更新候选池</strong>
            <p>这一步只查询本地 SQLite 快照，不会重新抓取全市场数据。</p>
          </div>

          <div v-else-if="!results.length" class="empty-state">
            <div class="empty-dot muted"></div>
            <strong>当前没有命中结果</strong>
            <p>建议先放宽 PB、PE 或股息率阈值，再重新试一轮。</p>
            <button class="ghost-btn" type="button" @click="resetFilters">回到默认视图</button>
          </div>

          <template v-else>
            <div class="candidate-stage">
              <div class="candidate-stage-top">
                <div class="candidate-stage-copy">
                  <strong>当前共筛出 {{ pagination.total }} 只标的</strong>
                  <span>按 {{ activeSortLabel }} 排序，优先把最值得看的一批放到前面。</span>
                </div>
                <div class="candidate-stage-pills">
                  <span>低 PB {{ valuationBuckets.lowPb }}</span>
                  <span>高股息 {{ valuationBuckets.highDividend }}</span>
                  <span>高 ROE {{ valuationBuckets.highRoe }}</span>
                </div>
              </div>

            <div class="table-shell">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>公司</th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('price')">
                        <span>价格</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'price' }">{{ getSortIndicator('price') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('pe')">
                        <span>PE</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'pe' }">{{ getSortIndicator('pe') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('pb')">
                        <span>PB</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'pb' }">{{ getSortIndicator('pb') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('roe')">
                        <span>ROE</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'roe' }">{{ getSortIndicator('roe') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('roi')">
                        <span>ROI</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'roi' }">{{ getSortIndicator('roi') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('dividend_yield')">
                        <span>股息率</span>
                        <span class="sort-indicator" :class="{ active: filters.sort_by === 'dividend_yield' }">{{ getSortIndicator('dividend_yield') }}</span>
                      </button>
                    </th>
                    <th>
                      <button class="sort-header" type="button" @click="toggleSort('market_cap')">
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
                        <button class="mini-btn" type="button" @click="openAnalysis(row.symbol)">分析</button>
                        <button
                          class="mini-btn mini-btn-primary"
                          type="button"
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
            </div>

            <div class="pager">
              <button class="ghost-btn" type="button" @click="goToPage(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">
                上一页
              </button>
              <span>第 {{ pagination.page }} 页，共 {{ pagination.total_pages || 1 }} 页</span>
              <button
                class="ghost-btn"
                type="button"
                @click="goToPage(pagination.page + 1)"
                :disabled="pagination.page >= pagination.total_pages || loading"
              >
                下一页
              </button>
            </div>
          </template>
        </section>

        <aside class="insight-column">
          <section class="panel-card insight-panel">
            <div class="panel-head compact-head">
              <div>
                <span class="eyebrow">Workbench Readout</span>
                <h2>筛选雷达</h2>
              </div>
            </div>

            <div class="radar-grid">
              <article class="radar-card">
                <span>低 PB</span>
                <strong>{{ valuationBuckets.lowPb }}</strong>
                <p>PB ≤ 1.5 的标的，更适合作为第一轮低估观察池。</p>
              </article>
              <article class="radar-card">
                <span>高股息</span>
                <strong>{{ valuationBuckets.highDividend }}</strong>
                <p>股息率 ≥ 5% 的标的，便于快速看现金回报线索。</p>
              </article>
              <article class="radar-card">
                <span>高 ROE</span>
                <strong>{{ valuationBuckets.highRoe }}</strong>
                <p>ROE ≥ 15% 的标的，更适合继续验证质量与定价能力。</p>
              </article>
              <article class="radar-card">
                <span>已监控</span>
                <strong>{{ monitoredCount }}</strong>
                <p>结果里已经进入监控列表的公司数量。</p>
              </article>
            </div>
          </section>

          <section class="panel-card insight-panel">
            <div class="panel-head compact-head">
              <div>
                <span class="eyebrow">Best Starting Points</span>
                <h2>优先研究名单</h2>
              </div>
            </div>

            <div v-if="topIdeas.length" class="idea-list">
              <article v-for="idea in topIdeas" :key="idea.symbol" class="idea-card">
                <div class="idea-head">
                  <div>
                    <strong>{{ idea.name }}</strong>
                    <div class="idea-subline">
                      <span>{{ idea.symbol }}</span>
                      <span v-if="idea.industry">{{ idea.industry }}</span>
                    </div>
                  </div>
                  <span class="idea-score">评分 {{ idea.score }}</span>
                </div>
                <div class="idea-reasons">
                  <span v-for="reason in idea.reasons" :key="reason">{{ reason }}</span>
                </div>
                <div class="idea-actions">
                  <button class="mini-btn" type="button" @click="openAnalysis(idea.symbol)">查看分析</button>
                  <button
                    class="mini-btn mini-btn-primary"
                    type="button"
                    @click="addToMonitor(idea)"
                    :disabled="idea.is_monitored || addLoadingSymbol === idea.symbol"
                  >
                    {{ idea.is_monitored ? '已监控' : '加入监控' }}
                  </button>
                </div>
              </article>
            </div>
            <div v-else class="side-empty">
              <p>拿到结果后，这里会自动给出更适合作为第一批研究对象的标的。</p>
            </div>
          </section>

          <section class="panel-card insight-panel">
            <div class="panel-head compact-head">
              <div>
                <span class="eyebrow">Industry Spread</span>
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
            <div v-else class="side-empty">
              <p>当前结果还不足以观察行业分布，可以先放宽条件再看一轮。</p>
            </div>
          </section>
        </aside>
      </section>
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
  --paper: rgba(255, 253, 247, 0.96);
  --paper-strong: rgba(255, 255, 255, 0.98);
  --ink: #1e293b;
  --ink-soft: #526072;
  --ink-faint: #708095;
  --line: rgba(116, 94, 66, 0.18);
  --accent: #0f766e;
  --accent-2: #b45309;
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 22%),
    radial-gradient(circle at right 10% top 12%, rgba(217, 119, 6, 0.12), transparent 18%),
    linear-gradient(180deg, #f6f0e7 0%, #f8f5ef 36%, #eef2f5 100%);
}

.shell-glow {
  position: absolute;
  width: 34rem;
  height: 34rem;
  border-radius: 999px;
  filter: blur(78px);
  opacity: 0.2;
  pointer-events: none;
}

.shell-glow-left {
  left: -10rem;
  top: -8rem;
  background: rgba(15, 118, 110, 0.46);
}

.shell-glow-right {
  right: -12rem;
  top: 4rem;
  background: rgba(217, 119, 6, 0.34);
}

.workspace {
  position: relative;
  z-index: 1;
  max-width: 1600px;
  margin: 0 auto;
  padding: 28px;
  display: grid;
  gap: 18px;
}

.panel-card {
  border: 1px solid var(--line);
  border-radius: 28px;
  background: linear-gradient(180deg, var(--paper-strong), var(--paper));
  box-shadow: 0 26px 55px -42px rgba(30, 41, 59, 0.38);
  backdrop-filter: blur(18px);
}

.hero,
.toolbar,
.result-panel,
.insight-panel,
.summary-card {
  padding: 22px;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  padding-bottom: 18px;
}

.hero-copy,
.toolbar-head,
.panel-head,
.summary-card,
.radar-card,
.idea-card {
  display: grid;
  gap: 10px;
}

.eyebrow,
.preset-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 800;
  color: var(--accent);
}

.hero h1,
.toolbar h2,
.panel-head h2 {
  margin: 0;
  color: var(--ink);
}

.hero h1 {
  font-size: clamp(2rem, 3vw, 3rem);
  line-height: 0.98;
  letter-spacing: -0.04em;
}

.hero p,
.panel-copy,
.summary-card p,
.radar-card p,
.idea-card p,
.side-empty p {
  margin: 0;
  color: var(--ink-soft);
  line-height: 1.68;
}

.hero-copy p {
  max-width: 560px;
  font-size: 0.9rem;
}

.hero-pills,
.hero-actions,
.toolbar-meta,
.active-tag-row,
.preset-metrics,
.row-actions,
.idea-actions,
.idea-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-pill,
.meta-chip,
.active-tag,
.preset-metrics span,
.status-pill,
.monitor-badge,
.symbol-badge,
.industry-badge,
.idea-score,
.idea-reasons span {
  border-radius: 999px;
  font-weight: 700;
}

.hero-pill,
.meta-chip,
.active-tag,
.preset-metrics span,
.idea-reasons span {
  padding: 8px 12px;
  border: 1px solid rgba(15, 118, 110, 0.12);
  background: rgba(255, 255, 255, 0.78);
  color: var(--ink-soft);
  font-size: 0.8rem;
}

.hero-pills,
.summary-strip {
  display: none;
}

.active-tag.muted {
  border-style: dashed;
  color: var(--ink-faint);
}

.hero-actions {
  justify-content: flex-end;
  min-width: 230px;
}

.ghost-btn,
.refresh-btn,
.apply-btn,
.mini-btn,
.preset-card,
.sort-header {
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.ghost-btn,
.refresh-btn,
.apply-btn,
.mini-btn {
  padding: 12px 18px;
  border-radius: 14px;
  border: 1px solid rgba(116, 94, 66, 0.18);
  font-weight: 800;
  cursor: pointer;
}

.ghost-btn,
.mini-btn {
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink);
}

.refresh-btn,
.apply-btn,
.mini-btn-primary {
  background: linear-gradient(135deg, #0f766e, #115e59);
  color: #f8fafc;
  border-color: rgba(15, 118, 110, 0.2);
  box-shadow: 0 18px 34px -24px rgba(15, 118, 110, 0.55);
}

.ghost-btn:hover,
.refresh-btn:hover,
.apply-btn:hover,
.mini-btn:hover,
.preset-card:hover {
  transform: translateY(-1px);
}

.ghost-btn:disabled,
.refresh-btn:disabled,
.apply-btn:disabled,
.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.toolbar {
  display: grid;
  gap: 14px;
  background: linear-gradient(180deg, rgba(251, 250, 247, 0.92), rgba(247, 249, 251, 0.9));
  border-style: dashed;
}

.toolbar-head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.control-grid {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) repeat(7, minmax(120px, 1fr));
  gap: 14px;
  align-items: end;
}

.field {
  display: grid;
  gap: 8px;
}

.field span,
.summary-card span,
.radar-card span,
.industry-label span {
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 800;
  color: var(--ink-faint);
}

.field input,
.field select {
  width: 100%;
  padding: 13px 14px;
  border-radius: 14px;
  border: 1px solid rgba(116, 94, 66, 0.18);
  background: rgba(255, 255, 255, 0.84);
  color: var(--ink);
}

.field input:focus,
.field select:focus {
  outline: none;
  border-color: rgba(15, 118, 110, 0.42);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.search-field {
  grid-column: span 2;
}

.checkbox-field {
  min-width: 190px;
}

.checkbox-wrap {
  min-height: 50px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.checkbox-wrap input {
  width: 16px;
  height: 16px;
  accent-color: #0f766e;
}

.checkbox-wrap strong {
  color: var(--ink);
  font-size: 0.92rem;
}

.control-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.preset-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.preset-card {
  border: 1px solid rgba(116, 94, 66, 0.14);
  border-radius: 22px;
  padding: 18px;
  text-align: left;
  background: rgba(255, 255, 255, 0.68);
  cursor: pointer;
}

.preset-card strong,
.summary-card strong,
.radar-card strong {
  color: var(--ink);
}

.preset-card p {
  margin: 0;
  color: var(--ink-soft);
  line-height: 1.62;
}

.preset-card {
  padding: 14px;
}

.preset-card p {
  display: none;
}

.preset-income {
  background: linear-gradient(180deg, rgba(255, 247, 237, 0.92), rgba(255, 255, 255, 0.72));
}

.preset-quality {
  background: linear-gradient(180deg, rgba(236, 253, 245, 0.92), rgba(255, 255, 255, 0.72));
}

.preset-steady {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.72));
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card strong {
  font-size: 1.2rem;
}

.error-banner {
  padding: 16px 20px;
  color: #9a3412;
  background: linear-gradient(180deg, rgba(255, 237, 213, 0.94), rgba(255, 247, 237, 0.9));
  font-weight: 700;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(280px, 0.62fr);
  gap: 18px;
  align-items: start;
  padding-top: 6px;
}

.result-panel {
  min-height: 760px;
  min-width: 0;
  background:
    linear-gradient(180deg, rgba(252, 250, 246, 0.98), rgba(247, 249, 251, 0.96));
  border-color: rgba(15, 118, 110, 0.18);
  box-shadow:
    0 30px 60px -44px rgba(15, 23, 42, 0.3),
    0 0 0 1px rgba(255, 255, 255, 0.55) inset;
}

.candidate-headline {
  display: grid;
  gap: 8px;
}

.candidate-headline .panel-copy {
  display: none;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.compact-head {
  margin-bottom: 14px;
}

.result-status-stack {
  display: grid;
  gap: 6px;
  justify-items: end;
}

.status-pill {
  padding: 7px 10px;
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(107, 114, 128, 0.14);
  color: var(--ink);
  font-size: 0.76rem;
  font-family: Consolas, Monaco, monospace;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.status-note {
  color: var(--ink-faint);
  font-size: 0.78rem;
}

.candidate-stage {
  display: grid;
  gap: 12px;
}

.candidate-stage-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(252, 252, 251, 0.98), rgba(246, 248, 250, 0.96));
}

.candidate-stage-copy {
  display: grid;
  gap: 4px;
}

.candidate-stage-copy strong {
  color: var(--ink);
  font-size: 0.96rem;
  letter-spacing: -0.01em;
}

.candidate-stage-copy span {
  color: var(--ink-soft);
  font-size: 0.82rem;
}

.candidate-stage-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.candidate-stage-pills span {
  padding: 7px 10px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.88);
  color: var(--ink-soft);
  font-size: 0.73rem;
  font-weight: 700;
  font-family: Consolas, Monaco, monospace;
}

.table-shell {
  overflow: auto;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(253, 253, 252, 0.98), rgba(247, 249, 251, 0.97));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 18px 34px -32px rgba(30, 41, 59, 0.22);
  overscroll-behavior-x: contain;
}

.insight-panel {
  background: linear-gradient(180deg, rgba(250, 250, 248, 0.92), rgba(246, 248, 250, 0.92));
}

.result-table {
  width: 100%;
  min-width: 1080px;
  border-collapse: collapse;
}

.result-table th,
.result-table td {
  padding: 13px 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.92);
  text-align: left;
  vertical-align: middle;
  white-space: nowrap;
}

.result-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(241, 245, 249, 0.98);
  color: var(--ink-faint);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-family: Consolas, Monaco, monospace;
}

.result-table th:first-child,
.result-table td:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  background: rgba(252, 252, 251, 0.99);
}

.result-table th:first-child {
  z-index: 3;
  background: rgba(241, 245, 249, 0.99);
}

.result-table td:first-child {
  min-width: 220px;
  box-shadow: 10px 0 16px -18px rgba(30, 41, 59, 0.26);
}

.result-table tbody tr:nth-child(even) {
  background: rgba(248, 250, 252, 0.56);
}

.result-table td:last-child {
  min-width: 150px;
}

.sort-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sort-indicator {
  color: #94a3b8;
}

.sort-indicator.active {
  color: var(--accent);
}

.result-table tbody tr:hover {
  background: rgba(236, 253, 245, 0.62);
}

.company-cell {
  display: grid;
  gap: 6px;
}

.company-mainline,
.company-subline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.company-mainline strong,
.idea-head strong {
  color: var(--ink);
  font-size: 0.95rem;
  letter-spacing: -0.02em;
}

.monitor-badge,
.symbol-badge,
.industry-badge,
.idea-score {
  padding: 4px 8px;
  font-size: 0.68rem;
}

.monitor-badge {
  background: rgba(220, 252, 231, 0.95);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.16);
}

.symbol-badge {
  background: rgba(241, 245, 249, 0.98);
  color: #475569;
  font-family: Consolas, Monaco, monospace;
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.industry-badge {
  background: rgba(224, 242, 254, 0.94);
  color: #0369a1;
  border: 1px solid rgba(56, 189, 248, 0.14);
}

.price-text,
.market-cap-text {
  color: var(--ink);
  font-weight: 700;
  font-family: Consolas, Monaco, monospace;
}

.price-text {
  font-size: 0.92rem;
}

.metric-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 7px 10px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(248, 250, 252, 0.98);
  font-size: 0.76rem;
  font-weight: 800;
  color: #334155;
  font-family: Consolas, Monaco, monospace;
}

.tone-cheap {
  background: rgba(220, 252, 231, 0.95);
  color: #047857;
}

.tone-quality {
  background: rgba(224, 242, 254, 0.95);
  color: #0f766e;
}

.tone-strong {
  background: rgba(209, 250, 229, 0.96);
  color: #166534;
}

.tone-income {
  background: rgba(254, 249, 195, 0.95);
  color: #a16207;
}

.tone-neutral {
  background: rgba(239, 246, 255, 0.96);
  color: #1d4ed8;
}

.tone-warm {
  background: rgba(255, 237, 213, 0.95);
  color: #c2410c;
}

.tone-muted {
  color: #64748b;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding-top: 2px;
}

.pager span {
  color: var(--ink-soft);
  font-weight: 700;
}

.empty-state,
.side-empty {
  min-height: 260px;
  border: 1px dashed rgba(116, 94, 66, 0.18);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.56);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  text-align: center;
  padding: 24px;
}

.side-empty {
  min-height: 120px;
}

.empty-state strong {
  color: var(--ink);
  font-size: 1.05rem;
}

.empty-dot {
  width: 52px;
  height: 52px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(15, 118, 110, 0.74), rgba(15, 118, 110, 0.08));
}

.empty-dot.pulse {
  animation: pulse-dot 1.6s ease-in-out infinite;
}

.empty-dot.muted {
  background: radial-gradient(circle, rgba(148, 163, 184, 0.6), rgba(148, 163, 184, 0.08));
}

.insight-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.insight-panel {
  display: grid;
}

.insight-column .insight-panel {
  position: sticky;
  top: 20px;
}

.radar-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.radar-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(116, 94, 66, 0.12);
}

.radar-card strong {
  font-size: 1.24rem;
}

.idea-list,
.industry-list {
  display: grid;
  gap: 12px;
}

.idea-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(116, 94, 66, 0.12);
}

.idea-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.idea-subline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  color: var(--ink-faint);
  font-size: 0.82rem;
}

.idea-score {
  background: rgba(15, 118, 110, 0.1);
  color: var(--accent);
  white-space: nowrap;
}

.industry-row {
  display: grid;
  gap: 8px;
}

.industry-label {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.industry-label strong {
  color: var(--ink);
}

.industry-bar-track {
  height: 10px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.9);
  overflow: hidden;
}

.industry-bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e, #0ea5a4);
}

@keyframes pulse-dot {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.82;
  }

  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@media (max-width: 1340px) {
  .control-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .search-field {
    grid-column: span 2;
  }

  .control-actions {
    grid-column: span 2;
    justify-content: stretch;
  }

  .control-actions .ghost-btn,
  .control-actions .apply-btn {
    flex: 1;
  }

  .summary-strip,
  .preset-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .insight-column {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .insight-column .insight-panel {
    position: static;
    top: auto;
  }
}

@media (max-width: 1100px) {
  .hero,
  .toolbar-head,
  .panel-head,
  .idea-head {
    display: grid;
  }

  .result-status-stack {
    justify-items: start;
  }

  .insight-column {
    grid-template-columns: 1fr;
  }

  .candidate-stage-top {
    display: grid;
  }
}

@media (max-width: 860px) {
  .workspace {
    padding: 18px;
  }

  .control-grid,
  .summary-strip,
  .preset-row,
  .radar-grid {
    grid-template-columns: 1fr;
  }

  .search-field,
  .control-actions {
    grid-column: span 1;
  }

  .result-table {
    min-width: 0;
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

  .result-table th:first-child,
  .result-table td:first-child {
    position: static;
    left: auto;
    box-shadow: none;
    min-width: 0;
  }

  .result-table tbody {
    display: grid;
    gap: 14px;
    padding: 14px;
  }

  .result-table tbody tr {
    border: 1px solid rgba(116, 94, 66, 0.14);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.92);
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
    color: var(--ink-faint);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .pager,
  .hero-actions,
  .row-actions,
  .idea-actions {
    display: grid;
  }

  .ghost-btn,
  .refresh-btn,
  .apply-btn,
  .mini-btn {
    width: 100%;
  }
}
</style>

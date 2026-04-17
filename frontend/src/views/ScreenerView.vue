<template>
  <div class="screener-shell">
    <header class="screener-header">
      <div>
        <div class="header-topline">A-Share Screener</div>
        <h1>自定义选股矩阵</h1>
        <p class="header-copy">
          先用估值和分红做一轮全市场初筛，再把候选标的送进深度分析和财务溯源。
        </p>
      </div>
      <div class="header-actions">
        <button class="ghost-btn" @click="router.push('/')">返回首页</button>
        <button class="refresh-btn" @click="refreshSnapshot" :disabled="refreshing">
          {{ refreshing ? '刷新中...' : '刷新全市场快照' }}
        </button>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>

    <div class="meta-grid">
      <article class="meta-card">
        <span>快照日期</span>
        <strong>{{ screenerMeta.snapshot_date || '--' }}</strong>
        <p>SQLite 本地快照，不影响现有分析链路。</p>
      </article>
      <article class="meta-card">
        <span>可筛标的</span>
        <strong>{{ screenerMeta.count || 0 }}</strong>
        <p>只筛最新一轮落库快照。</p>
      </article>
      <article class="meta-card">
        <span>核心指标</span>
        <strong>{{ screenerMeta.roe_basis_label || '年报 ROE / 现价股息率 / ROI' }}</strong>
        <p>展示字段值，可直接排序与筛选。</p>
      </article>
    </div>

    <main class="screener-layout">
      <aside class="filter-panel">
        <section class="panel-card">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">Filters</span>
              <h2>筛选条件</h2>
            </div>
            <button class="text-btn" @click="resetFilters">重置</button>
          </div>
          <form class="filter-grid" @submit.prevent="applyFilters(1)">
            <label class="field">
              <span>名称 / 代码</span>
              <input v-model.trim="filters.q" placeholder="如 银行 / 600000" />
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
              <span>总市值 ≥</span>
              <input v-model.number="filters.market_cap_min_100m" type="number" step="1" placeholder="100" />
              <small>单位：亿元</small>
            </label>
            <label class="field field-checkbox">
              <span>异常样本</span>
              <div class="checkbox-row">
                <input v-model="filters.include_anomalies" type="checkbox" />
                <strong>包含异常估值样本</strong>
              </div>
              <small>默认剔除 PE≤0 或 PB≤0 的样本，避免失真值干扰筛选。</small>
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
            <button class="apply-btn" type="submit" :disabled="loading">开始筛选</button>
          </form>
        </section>

        <section class="panel-card">
          <span class="panel-kicker">Presets</span>
          <h2>常用组合</h2>
          <div class="preset-stack">
            <button class="preset-btn" @click="applyPreset('dividend_value')">低估高股息</button>
            <button class="preset-btn" @click="applyPreset('quality_value')">高 ROE 价值</button>
            <button class="preset-btn" @click="applyPreset('cash_cow')">现金奶牛</button>
          </div>
        </section>
      </aside>

      <section class="result-panel">
        <div class="panel-card result-card">
          <div class="panel-head result-head">
            <div>
              <span class="panel-kicker">Results</span>
              <h2>候选池</h2>
              <p class="result-copy">
                当前筛出 {{ pagination.total }} 只。先看便宜与股息，再决定哪些值得加入监控。
              </p>
            </div>
            <div class="result-status">
              <span v-if="loading">正在筛选...</span>
              <span v-else>{{ pagination.page }} / {{ pagination.total_pages || 1 }} 页</span>
            </div>
          </div>

          <div v-if="!screenerMeta.ready" class="empty-state">
            <strong>还没有选股快照</strong>
            <p>先刷新一次全市场快照，SQLite 本地库里就会生成可筛选的数据表。</p>
          </div>

          <div v-else-if="loading" class="empty-state">
            <strong>正在按条件筛选</strong>
            <p>这一步只查本地 SQLite，不会重新抓全市场数据。</p>
          </div>

          <div v-else-if="!results.length" class="empty-state">
            <strong>没有命中结果</strong>
            <p>条件过严了，先放宽 PB / PE / 股息率阈值，再重新筛选。</p>
          </div>

          <div v-else class="table-shell">
            <table class="result-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>价格</th>
                  <th>PE</th>
                  <th>PB</th>
                  <th>ROE</th>
                  <th>ROI</th>
                  <th>股息率</th>
                  <th>总市值</th>
                  <th>动作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in results" :key="row.symbol">
                  <td>
                    <div class="name-cell">
                      <strong>{{ row.name }}</strong>
                      <span>{{ row.symbol }}</span>
                    </div>
                  </td>
                  <td>{{ formatPrice(row.price) }}</td>
                  <td>{{ formatNumber(row.pe) }}</td>
                  <td>{{ formatNumber(row.pb) }}</td>
                  <td>{{ formatPctValue(row.roe_pct) }}</td>
                  <td>{{ formatPctValue(row.roi_pct) }}</td>
                  <td>{{ formatPct(row.dividend_yield) }}</td>
                  <td>{{ formatMarketCap(row.market_cap) }}</td>
                  <td>
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
            <button class="ghost-btn" @click="applyFilters(pagination.page - 1)" :disabled="pagination.page <= 1 || loading">
              上一页
            </button>
            <span>第 {{ pagination.page }} 页，共 {{ pagination.total_pages || 1 }} 页</span>
            <button class="ghost-btn" @click="applyFilters(pagination.page + 1)" :disabled="pagination.page >= pagination.total_pages || loading">
              下一页
            </button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { stockApi, type ScreenerMeta, type ScreenerResult } from '@/api'

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
    void fetchResults(1)
  }
}

const applyPreset = (preset: 'dividend_value' | 'quality_value' | 'cash_cow') => {
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

onMounted(() => {
  void fetchResults(1)
})
</script>

<style scoped>
.screener-shell {
  min-height: 100vh;
  padding: 28px;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 24%),
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 20%),
    linear-gradient(180deg, #f8fbff 0%, #f1f5f9 100%);
}

.screener-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.header-topline,
.panel-kicker {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}

.screener-header h1,
.panel-head h2 {
  margin: 8px 0 0;
  color: #0f172a;
}

.header-copy,
.result-copy,
.meta-card p,
.field small {
  color: #64748b;
  line-height: 1.7;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.ghost-btn,
.refresh-btn,
.apply-btn,
.text-btn,
.preset-btn,
.mini-btn {
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-btn,
.refresh-btn,
.apply-btn {
  padding: 10px 16px;
  border-radius: 12px;
  font-weight: 700;
}

.ghost-btn {
  background: #ffffff;
  border: 1px solid #dbe4f0;
  color: #334155;
}

.refresh-btn,
.apply-btn,
.mini-btn-primary {
  background: #0f766e;
  color: #ffffff;
}

.refresh-btn:disabled,
.apply-btn:disabled,
.mini-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.meta-grid,
.screener-layout,
.filter-grid {
  display: grid;
  gap: 16px;
}

.error-banner {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  color: #9a3412;
  font-weight: 700;
}

.meta-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 18px;
}

.meta-card,
.panel-card {
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 20px;
  box-shadow: 0 20px 40px -34px rgba(15, 23, 42, 0.28);
}

.meta-card {
  padding: 18px;
}

.meta-card span,
.field span {
  display: block;
  font-size: 0.78rem;
  color: #64748b;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.meta-card strong {
  display: block;
  margin-top: 10px;
  color: #0f172a;
  font-size: 1.4rem;
  font-weight: 900;
}

.screener-layout {
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  align-items: start;
}

.filter-panel,
.result-panel {
  display: grid;
  gap: 16px;
}

.panel-card {
  padding: 20px;
}

.panel-head,
.result-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.text-btn {
  background: transparent;
  color: #2563eb;
  font-weight: 700;
}

.filter-grid {
  grid-template-columns: 1fr 1fr;
}

.field {
  display: grid;
  gap: 8px;
}

.field-checkbox {
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
  accent-color: #0f766e;
}

.checkbox-row strong {
  color: #0f172a;
  font-size: 0.95rem;
}

.field input,
.field select {
  width: 100%;
  padding: 12px 13px;
  border-radius: 12px;
  border: 1px solid #dbe4f0;
  background: #ffffff;
  color: #0f172a;
}

.apply-btn {
  grid-column: span 2;
  margin-top: 6px;
}

.preset-stack {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.preset-btn {
  padding: 12px 14px;
  text-align: left;
  border-radius: 14px;
  background: #f8fafc;
  color: #334155;
  border: 1px solid #e2e8f0;
  font-weight: 700;
}

.result-card {
  min-height: 720px;
}

.result-status {
  padding: 8px 12px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #dbe4f0;
  color: #475569;
  font-size: 0.82rem;
  font-weight: 700;
}

.empty-state {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 18px;
  border: 1px dashed #cbd5e1;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  text-align: center;
}

.empty-state strong {
  color: #0f172a;
  font-size: 1.05rem;
}

.empty-state p {
  max-width: 540px;
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.table-shell {
  overflow-x: auto;
  border-radius: 18px;
  border: 1px solid #dbe4f0;
  background: #ffffff;
}

.result-table {
  width: 100%;
  border-collapse: collapse;
}

.result-table th,
.result-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  color: #334155;
  font-size: 0.9rem;
}

.result-table th {
  background: #f8fafc;
  color: #64748b;
  font-size: 0.76rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.name-cell {
  display: grid;
  gap: 4px;
}

.name-cell strong {
  color: #0f172a;
}

.name-cell span {
  color: #64748b;
  font-size: 0.78rem;
  font-family: 'Monaco', monospace;
}

.row-actions {
  display: flex;
  gap: 8px;
}

.mini-btn {
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
  color: #334155;
  border: 1px solid #dbe4f0;
  font-size: 0.78rem;
  font-weight: 700;
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

@media (max-width: 1180px) {
  .meta-grid,
  .screener-layout,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .apply-btn {
    grid-column: span 1;
  }
}

@media (max-width: 760px) {
  .screener-shell {
    padding: 18px;
  }

  .screener-header,
  .panel-head,
  .result-head,
  .pager {
    display: grid;
  }

  .row-actions {
    flex-direction: column;
  }
}
</style>

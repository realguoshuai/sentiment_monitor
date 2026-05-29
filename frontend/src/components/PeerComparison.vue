<template>
  <section class="section peer-section" v-if="peerComparison">
    <div class="peer-header">
      <div>
        <p class="section-kicker">Peer Anchor</p>
        <h2>行业与同行对比</h2>
        <p class="subtitle">先看同行中位数，再判断当前这家公司到底是"便宜"还是"基本面更弱"。</p>
      </div>
      <div class="peer-badge-stack">
        <span class="peer-badge" v-if="peerComparison.industry">行业 {{ peerComparison.industry }}</span>
        <span class="peer-badge" v-if="peerComparison.source_label">{{ peerComparison.source_label }}</span>
        <span class="peer-badge">{{ peerComparison.peer_count }} 家同行</span>
      </div>
    </div>

    <template v-if="peerComparison.enabled && relativeView && medians && rows.length">
      <div class="peer-overview-grid">
        <article class="peer-metric-card">
          <span class="metric-title">PB 相对同行</span>
          <strong :class="gapTone(relativeView.pb_vs_peer_median_pct, true)">
            {{ signedPct(relativeView.pb_vs_peer_median_pct) }}
          </strong>
          <p>同行中位 {{ metric(medians.pb, 'pb') }}x</p>
        </article>
        <article class="peer-metric-card">
          <span class="metric-title">PE 相对同行</span>
          <strong :class="gapTone(relativeView.pe_vs_peer_median_pct, true)">
            {{ signedPct(relativeView.pe_vs_peer_median_pct) }}
          </strong>
          <p>同行中位 {{ metric(medians.pe, 'pe') }}x</p>
        </article>
        <article class="peer-metric-card">
          <span class="metric-title">前瞻 ROE</span>
          <strong :class="gapTone(relativeView.expected_roe_vs_peer_median_pct)">
            {{ signedPct(relativeView.expected_roe_vs_peer_median_pct) }}
          </strong>
          <p>同行中位 {{ pct(medians.expected_roe) }}</p>
        </article>
        <article class="peer-metric-card">
          <span class="metric-title">股息率</span>
          <strong :class="gapTone(relativeView.dividend_yield_vs_peer_median_pct)">
            {{ signedDiff(relativeView.dividend_yield_vs_peer_median_pct) }}
          </strong>
          <p>同行中位 {{ pct(medians.dividend_yield) }} | 展示为差值</p>
        </article>
      </div>

      <div class="peer-summary-strip">{{ peerComparison.summary }}</div>

      <div class="peer-table-shell">
        <table class="peer-table">
          <thead>
            <tr>
              <th>公司</th>
              <th>价格</th>
              <th>PE</th>
              <th>PB</th>
              <th>股息率</th>
              <th>前瞻 ROE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.symbol" :class="{ 'row-target': row.is_target }">
              <td>
                <div class="peer-name-cell">
                  <strong>{{ row.name }}</strong>
                  <span>{{ row.symbol }}</span>
                </div>
              </td>
              <td>{{ price(row.price) }}</td>
              <td>{{ metric(row.pe, 'pe') }}</td>
              <td>{{ metric(row.pb, 'pb') }}</td>
              <td>{{ pct(row.dividend_yield) }}</td>
              <td>{{ pct(row.expected_roe) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="peer-empty-state">
      <strong>同行锚点还没配置好</strong>
      <p>{{ peerComparison.reason || '先在标的管理里补上行业或同行代码，这里才会生成横向估值矩阵。' }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  peerComparison: any
}>()

const relativeView = computed(() => props.peerComparison?.relative_view ?? null)
const medians = computed(() => props.peerComparison?.medians ?? null)
const rows = computed(() => props.peerComparison?.rows ?? [])

const pct = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  return `${Number(v).toFixed(1)}%`
}
const signedPct = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`
}
const signedDiff = (v?: number) => signedPct(v)
const price = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v) || v <= 0) return '--'
  return Number(v).toFixed(2)
}
const metric = (v?: number, m = 'pe') => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  const digits = m === 'dy' || m === 'roi' ? 1 : 2
  return Number(v).toFixed(digits)
}
const gapTone = (v?: number, reverse = false) => {
  const n = Number(v ?? 0)
  if (n === 0) return 'gap-neutral'
  return (reverse ? n < 0 : n > 0) ? 'gap-positive' : 'gap-negative'
}
</script>

<style scoped>
.section {
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 8px 32px -12px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.03);
  margin-bottom: 24px;
}
.peer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.peer-header h2 {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px;
}
.subtitle {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  margin: 0;
}
.section-kicker {
  margin: 0 0 6px;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}
.peer-badge-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.peer-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 700;
  background: #f1f5f9;
  color: #475569;
  white-space: nowrap;
}
.peer-overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.peer-metric-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.metric-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  font-weight: 700;
}
.peer-metric-card strong {
  font-size: 1.3rem;
  font-weight: 900;
  font-family: Monaco, monospace;
}
.peer-metric-card p {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0;
}
.gap-positive { color: #10b981; }
.gap-negative { color: #ef4444; }
.gap-neutral { color: #64748b; }
.peer-summary-strip {
  padding: 12px 16px;
  background: #f1f5f9;
  border-radius: 10px;
  font-size: 0.85rem;
  color: #475569;
  margin-bottom: 16px;
}
.peer-table-shell {
  overflow-x: auto;
}
.peer-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.peer-table th {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.72rem;
  text-transform: uppercase;
  color: #64748b;
  font-weight: 700;
}
.peer-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}
.row-target {
  background: #eff6ff;
}
.peer-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.peer-name-cell strong { font-size: 0.85rem; }
.peer-name-cell span { font-size: 0.72rem; color: #94a3b8; }
.peer-empty-state {
  padding: 40px 20px;
  text-align: center;
  color: #94a3b8;
}
.peer-empty-state strong { display: block; margin-bottom: 8px; font-size: 1rem; color: #64748b; }
.peer-empty-state p { margin: 0; font-size: 0.85rem; }
@media (max-width: 768px) {
  .peer-overview-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

<template>
  <section class="section thesis-section" v-if="investmentThesis">
    <div class="thesis-header">
      <div>
        <p class="section-kicker">Investment Thesis</p>
        <h2>投资 Thesis 跟踪</h2>
        <p class="thesis-headline">{{ investmentThesis.headline }}</p>
      </div>
      <div class="valuation-summary thesis-stance" :class="`summary-${investmentThesis.stance_color}`">
        <span class="summary-label">{{ investmentThesis.stance }}</span>
        <strong>{{ investmentThesis.confidence_score }}/100</strong>
        <span class="thesis-meta">综合置信度</span>
      </div>
    </div>

    <div class="thesis-scoreboard">
      <article class="thesis-score-card">
        <span class="mini-label">估值</span>
        <strong>{{ investmentThesis.scorecard.valuation }}</strong>
      </article>
      <article class="thesis-score-card">
        <span class="mini-label">质量</span>
        <strong>{{ investmentThesis.scorecard.quality }}</strong>
      </article>
      <article class="thesis-score-card">
        <span class="mini-label">现金流</span>
        <strong>{{ investmentThesis.scorecard.cashflow }}</strong>
      </article>
      <article class="thesis-score-card">
        <span class="mini-label">稳定性</span>
        <strong>{{ investmentThesis.scorecard.stability }}</strong>
      </article>
    </div>

    <div class="thesis-grid">
      <article class="thesis-column">
        <div class="column-header">
          <span class="mini-label">Why Now</span>
          <h3>买入理由</h3>
        </div>
        <div class="thesis-stack">
          <div v-for="item in investmentThesis.buy_case" :key="item" class="thesis-item">
            <p>{{ item }}</p>
          </div>
        </div>
      </article>

      <article class="thesis-column">
        <div class="column-header">
          <span class="mini-label">Assumptions</span>
          <h3>核心假设</h3>
        </div>
        <div class="thesis-stack">
          <div v-for="item in investmentThesis.key_assumptions" :key="item.label" class="thesis-item">
            <div class="thesis-item-head">
              <strong>{{ item.label }}</strong>
              <span class="thesis-badge" :class="item.status">{{ item.status_label }}</span>
            </div>
            <p>{{ item.detail }}</p>
          </div>
        </div>
      </article>

      <article class="thesis-column">
        <div class="column-header">
          <span class="mini-label">Risk Check</span>
          <h3>风险清单</h3>
        </div>
        <div class="thesis-stack">
          <div v-for="item in investmentThesis.risk_checklist" :key="item.label" class="thesis-item">
            <div class="thesis-item-head">
              <strong>{{ item.label }}</strong>
              <span class="thesis-badge" :class="item.level">{{ item.level_label }}风险</span>
            </div>
            <p>{{ item.detail }}</p>
          </div>
        </div>
      </article>
    </div>

    <div class="trigger-panel">
      <div class="column-header">
        <span class="mini-label">Review Triggers</span>
        <h3>财报后复核项</h3>
      </div>
      <div class="trigger-grid">
        <div v-for="item in investmentThesis.review_triggers" :key="item" class="trigger-chip">
          {{ item }}
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  investmentThesis: {
    stance: string
    stance_color: string
    confidence_score: number
    headline: string
    scorecard: {
      valuation: string
      quality: string
      cashflow: string
      stability: string
    }
    buy_case: string[]
    key_assumptions: Array<{
      label: string
      detail: string
      status: string
      status_label: string
    }>
    risk_checklist: Array<{
      label: string
      detail: string
      level: string
      level_label: string
    }>
    review_triggers: string[]
  } | null
}>()
</script>

<style scoped>
.section {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  border: 1px solid #f1f5f9;
  margin-bottom: 24px;
}
.section-kicker, .mini-label {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #0f766e;
}
.thesis-section {
  display: grid;
  gap: 18px;
}
.thesis-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.thesis-header h2 {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
  margin: 6px 0 0;
}
.thesis-headline {
  color: #64748b;
  line-height: 1.6;
  margin: 12px 0 0;
}
.thesis-stance {
  min-width: 140px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: right;
}
.thesis-stance.summary-emerald {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #065f46;
}
.thesis-stance.summary-amber {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}
.thesis-stance.summary-rose {
  background: #fff1f2;
  border-color: #fecdd3;
  color: #9f1239;
}
.thesis-stance.summary-slate {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #334155;
}
.summary-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
}
.thesis-scoreboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.thesis-score-card {
  padding: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 20px;
}
.thesis-score-card strong {
  display: block;
  margin-top: 10px;
  color: #0f172a;
  font-size: 1.2rem;
  font-weight: 900;
}
.thesis-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.thesis-column, .trigger-panel {
  padding: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 20px;
}
.column-header h3 {
  margin: 6px 0 0;
  color: #0f172a;
}
.thesis-stack {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.thesis-item {
  padding: 14px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.thesis-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.thesis-item p {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}
.thesis-meta {
  color: #64748b;
  line-height: 1.6;
  font-size: 0.78rem;
}
.thesis-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 800;
  white-space: nowrap;
}
.thesis-badge.on_track,
.thesis-badge.low {
  background: #dcfce7;
  color: #166534;
}
.thesis-badge.watch,
.thesis-badge.medium {
  background: #fef3c7;
  color: #92400e;
}
.thesis-badge.at_risk,
.thesis-badge.high {
  background: #fee2e2;
  color: #b91c1c;
}
.trigger-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 16px;
}
.trigger-chip {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
  line-height: 1.6;
}
@media (max-width: 1180px) {
  .thesis-grid,
  .thesis-scoreboard,
  .trigger-grid {
    grid-template-columns: 1fr;
  }
  .thesis-header {
    flex-direction: column;
  }
  .thesis-stance {
    text-align: left;
  }
}
</style>

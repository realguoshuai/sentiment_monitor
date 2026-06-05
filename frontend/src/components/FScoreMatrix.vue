<template>
  <section class="section safety-section">
    <div class="section-header compact-header">
      <div>
        <p class="section-kicker">Safety Screen</p>
        <h2>
          F-Score 排雷
          <InfoTooltip>
            <template #content>
              <strong>财务安全性评分（0~10 分）</strong><br/>
              检查 9 项财务健康指标，按通过比例折算：<br/>
              <div class="formula">得分 = (通过数 ÷ 总数) × 10</div>
              <span class="threshold threshold-green">≥7 分：健康</span>
              <span class="threshold threshold-yellow">4~6 分：关注</span>
              <span class="threshold threshold-red">≤3 分：风险</span>
            </template>
          </InfoTooltip>
        </h2>
        <p class="subtitle">把九项财务信号压缩到一屏，快速剔除价值陷阱。</p>
      </div>
      <div class="score-pill" :class="scoreClass">
        {{ score }}/10
      </div>
    </div>
    <div class="f-score-matrix">
      <div v-for="item in details" :key="item.name" class="matrix-item">
        <div class="matrix-copy">
          <span class="matrix-name">
            {{ item.name }}
            <InfoTooltip :text="getItemExplanation(item.name)" placement="right" />
          </span>
          <span class="matrix-val">{{ item.val }}</span>
        </div>
        <span class="matrix-status" :class="{ passed: item.passed, failed: !item.passed }">
          {{ item.passed ? '通过' : '警惕' }}
        </span>
      </div>
    </div>
    <p class="section-footer">7 分以上通常代表财务结构扎实，3 分以下需要高度警惕"便宜但不安全"。后四项（杠杆/流动性/毛利率/周转率）需要原始财报数据，缺失时自动跳过。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import InfoTooltip from '@/components/InfoTooltip.vue'

const props = defineProps<{
  score: number
  details: Array<{ name: string; val: string; passed: boolean }>
}>()

const itemExplanations: Record<string, string> = {
  'ROA > 0': '<strong>总资产收益率为正</strong><br/>ROA = 净利润 ÷ 总资产<br/>反映公司运用全部资产赚钱的能力',
  '净利润 > 0': '<strong>归母净利润为正</strong><br/>最基本的盈利能力检查',
  '经营性现金流 > 0': '<strong>经营活动现金流为正</strong><br/>确认利润有真金白银支撑，不是纸面富贵',
  '现金流 > 净利润': '<strong>现金流覆盖净利润</strong><br/>CFO ÷ 净利润 ≥ 100%<br/>利润含金量高，没有大量应收挂账',
  'ROA同比提升': '<strong>ROA 同比改善</strong><br/>对比去年同期，盈利能力在好转',
  '杠杆改善': '<strong>资产负债率同比下降</strong><br/>有息负债占总资产比例在降低<br/>财务风险正在收敛',
  '流动性改善': '<strong>流动比率同比提升</strong><br/>流动资产 ÷ 流动负债<br/>短期偿债能力在增强',
  '毛利率提升': '<strong>毛利率同比提升</strong><br/>(营收-成本) ÷ 营收<br/>定价权或成本控制在改善',
  '资产周转率提升': '<strong>资产周转率同比提升</strong><br/>营收 ÷ 总资产<br/>运营效率在提高'
}

function getItemExplanation(name: string): string {
  return itemExplanations[name] || name
}

const scoreClass = computed(() => {
  if (props.score >= 7) return 'score-high'
  if (props.score <= 3) return 'score-low'
  return 'score-mid'
})
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
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.section-header h2 {
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
.f-score-matrix {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.matrix-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}
.matrix-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.matrix-name {
  font-size: 0.82rem;
  font-weight: 700;
  color: #334155;
}
.matrix-val {
  font-size: 0.78rem;
  color: #64748b;
  font-family: monospace;
}
.matrix-status {
  font-size: 0.72rem;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 6px;
}
.matrix-status.passed {
  background: #dcfce7;
  color: #166534;
}
.matrix-status.failed {
  background: #fee2e2;
  color: #991b1b;
}
.score-pill {
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 900;
  white-space: nowrap;
}
.score-high { background: #d1fae5; color: #065f46; }
.score-mid { background: #f1f5f9; color: #475569; }
.score-low { background: #fee2e2; color: #991b1b; }
.section-footer {
  margin: 16px 0 0;
  font-size: 0.78rem;
  color: #94a3b8;
}
@media (max-width: 768px) {
  .f-score-matrix { grid-template-columns: 1fr; }
}
</style>

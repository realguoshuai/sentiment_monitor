<template>
  <section class="section fair-value-section" v-if="valuationConclusion && valuationRange && expectedReturn">
    <div class="valuation-header">
      <div>
        <h2>估值分析结论层</h2>
        <p class="section-footer section-footer-tight">综合 ROE-PB、盈利能力与股东自由现金流三种口径，给出加权估值区间。</p>
      </div>
      <div class="valuation-summary" :class="valuationSummaryClass">
        <span class="summary-label">综合判断</span>
        <strong>{{ valuationConclusion.summary }}</strong>
      </div>
    </div>

    <div class="valuation-grid">
      <div class="valuation-card valuation-card-primary">
        <span class="valuation-card-title">综合合理价值区间</span>
        <div class="valuation-main">{{ formatPrice(valuationRange.price_low) }} - {{ formatPrice(valuationRange.price_high) }}</div>
        <div class="valuation-sub">基准价 {{ formatPrice(valuationRange.price_base) }}</div>
        <div class="valuation-note">
          {{ valuationModelCount }} 个模型加权 | 模型分歧 {{ formatPct(valuationBlend?.spread_pct) }}
        </div>
      </div>
      <div class="valuation-card">
        <span class="valuation-card-title">折价 / 溢价</span>
        <div class="valuation-main">{{ valuationConclusion.discount_premium.label }}</div>
        <div class="valuation-sub">{{ formatPct(valuationConclusion.discount_premium.pct) }}</div>
        <div class="valuation-note">相对综合基准价值</div>
      </div>
      <div class="valuation-card">
        <span class="valuation-card-title">安全边际</span>
        <div class="valuation-main">{{ valuationConclusion.margin_of_safety.label }}</div>
        <div class="valuation-sub">{{ formatPct(valuationConclusion.margin_of_safety.pct) }}</div>
        <div class="valuation-note">保守估值线 {{ formatPrice(valuationConclusion.margin_of_safety.floor_price) }}</div>
      </div>
      <div class="valuation-card">
        <span class="valuation-card-title">预期年化回报</span>
        <div class="valuation-main">{{ formatPct(expectedReturn.total_annual_return_pct) }}</div>
        <div class="valuation-sub">{{ expectedReturn.holding_years }} 年视角</div>
        <div class="valuation-note">经营回报 + 股息 + 估值回归</div>
      </div>
    </div>

    <div class="valuation-grid valuation-grid-secondary">
      <div class="valuation-card">
        <span class="valuation-card-title">预期收益拆解</span>
        <div class="valuation-row">
          <span>经营回报</span>
          <strong>{{ formatPct(expectedReturn.business_return_pct) }}</strong>
        </div>
        <div class="valuation-row">
          <span>股息收益</span>
          <strong>{{ formatPct(expectedReturn.dividend_yield_pct) }}</strong>
        </div>
        <div class="valuation-row">
          <span>估值回归</span>
          <strong>{{ formatPct(expectedReturn.re_rating_annual_pct) }}</strong>
        </div>
      </div>
      <div class="valuation-card">
        <span class="valuation-card-title">信号与假设</span>
        <div class="valuation-row">
          <span>PB 分位</span>
          <strong>{{ valuationConclusion.signals.pb_percentile_zone }}</strong>
        </div>
        <div class="valuation-row">
          <span>股息率分位</span>
          <strong>{{ valuationConclusion.signals.dy_percentile_zone }}</strong>
        </div>
        <div class="valuation-row">
          <span>前瞻 ROE</span>
          <strong>{{ formatPct(valuationConclusion.assumptions.expected_roe) }}</strong>
        </div>
        <div class="valuation-row">
          <span>模型一致性</span>
          <strong>{{ valuationConclusion.signals.model_alignment_label }}</strong>
        </div>
      </div>
      <div class="valuation-card">
        <span class="valuation-card-title">敏感度演算</span>
        <div class="calculator">
          <div class="input-group">
            <label>预期 ROE (%)</label>
            <input type="number" v-model.number="calcParams.expectedRoe" step="0.5" />
          </div>
          <div class="input-group">
            <label>要求回报率 (%)</label>
            <input type="number" v-model.number="calcParams.requiredReturn" step="1" />
          </div>
          <div class="result-box compact-result">
            <div class="res-item">
              <span class="res-label">公允 PB</span>
              <span class="res-val">{{ manualFairPb.toFixed(2) }}</span>
            </div>
            <div class="res-item">
              <span class="res-label">公允价格</span>
              <span class="res-val">{{ formatPrice(manualFairPrice) }}</span>
            </div>
            <div class="res-item main-res">
              <span class="res-label">结论</span>
              <span class="res-val">{{ manualValuationLabel }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- DDM 股息折现动态沙盘 -->
    <div class="ddm-sandbox-panel">
      <div class="ddm-sandbox-header">
        <div>
          <span class="valuation-card-title">DDM 股息折现动态沙盘</span>
          <strong>调节长期增长假设与折现率，演算多阶段红利内在价值。</strong>
        </div>
        <div class="ddm-badge" :class="{ 'ddm-badge-warning': ddmParams.discountRate <= ddmParams.terminalGrowthRate }">
          {{ ddmValuationLabel }}
        </div>
      </div>
      <div class="ddm-sandbox-grid">
        <div class="ddm-sliders">
          <div class="ddm-slider-group">
            <div class="slider-header">
              <label>超额增长期 (年)</label>
              <span class="slider-value">{{ ddmParams.growthYears }} 年</span>
            </div>
            <input type="range" v-model.number="ddmParams.growthYears" min="3" max="10" step="1" />
          </div>
          <div class="ddm-slider-group">
            <div class="slider-header">
              <label>超额股息增长率 g₁ (%)</label>
              <span class="slider-value">{{ ddmParams.growthRate }}%</span>
            </div>
            <input type="range" v-model.number="ddmParams.growthRate" min="-10" max="30" step="0.5" />
          </div>
          <div class="ddm-slider-group">
            <div class="slider-header">
              <label>永续股息增长率 g₂ (%)</label>
              <span class="slider-value">{{ ddmParams.terminalGrowthRate }}%</span>
            </div>
            <input type="range" v-model.number="ddmParams.terminalGrowthRate" min="0" max="5" step="0.1" />
          </div>
          <div class="ddm-slider-group">
            <div class="slider-header">
              <label>折现要求回报率 r (%)</label>
              <span class="slider-value">{{ ddmParams.discountRate }}%</span>
            </div>
            <input type="range" v-model.number="ddmParams.discountRate" min="3" max="15" step="0.5" />
          </div>
        </div>
        <div class="ddm-results">
          <div class="ddm-result-cards">
            <div class="ddm-res-card">
              <span>每股派息基准 D₀</span>
              <strong>{{ formatPrice(ddmD0) }}</strong>
            </div>
            <div class="ddm-res-card ddm-res-card-highlight">
              <span>理论公允价值</span>
              <strong v-if="ddmParams.discountRate > ddmParams.terminalGrowthRate" class="glow-value">{{ formatPrice(ddmFairValue) }}</strong>
              <strong v-else class="glow-value text-error">--.--</strong>
            </div>
            <div class="ddm-res-card">
              <span>当前股价比对</span>
              <strong>{{ formatPrice(valuationConclusion.current.price || 0) }}</strong>
            </div>
          </div>
          <div class="ddm-mos-meter" v-if="ddmParams.discountRate > ddmParams.terminalGrowthRate">
            <div class="mos-meter-header">
              <span>安全边际 (MOS)</span>
              <strong :class="ddmMos >= 0 ? 'text-success' : 'text-error'">
                {{ ddmMos >= 0 ? '+' : '' }}{{ formatPct(ddmMos) }}
              </strong>
            </div>
            <div class="mos-track">
              <div class="mos-bar" :style="{ width: Math.max(0, Math.min(100, (ddmMos + 0.5) * 100)) + '%', backgroundColor: ddmMos >= 0 ? '#10b981' : '#f43f5e' }"></div>
              <div class="mos-marker" style="left: 50%;"></div>
            </div>
            <div class="mos-labels">
              <span>溢价 50%</span>
              <span>合理中枢</span>
              <span>折价 50%</span>
            </div>
          </div>
          <div class="ddm-warning-block" v-else>
            ⚠️ 要求回报率 ({{ ddmParams.discountRate }}%) 必须大于永续增长率 ({{ ddmParams.terminalGrowthRate }}%)，否则无法收敛。请调整滑块。
          </div>
        </div>
      </div>
    </div>

    <div class="normalized-panel" v-if="normalizedEarnings?.enabled">
      <div class="normalized-header">
        <div>
          <span class="valuation-card-title">归一化口径</span>
          <strong>先看利润是否偏离中枢，再决定该信哪种盈利口径。</strong>
        </div>
        <span class="normalized-badge" :class="getNormalizedTone(normalizedEarnings.cycle_position_label)">
          {{ normalizedEarnings.cycle_position_label }}
        </span>
      </div>
      <div class="normalized-grid">
        <article class="normalized-card">
          <span>当前 EPS</span>
          <strong>{{ formatPrice(normalizedEarnings.current_eps) }}</strong>
          <p>近 {{ normalizedEarnings.window_years }} 年归一 EPS {{ formatPrice(normalizedEarnings.normalized_eps) }}</p>
        </article>
        <article class="normalized-card">
          <span>EPS 偏离中枢</span>
          <strong>{{ formatSignedPct(normalizedEarnings.eps_deviation_pct) }}</strong>
          <p>盈利能力估值当前采用 {{ normalizedEarnings.basis_label }}</p>
        </article>
        <article class="normalized-card">
          <span>FCF / 股</span>
          <strong>{{ formatPrice(normalizedEarnings.current_fcf_per_share) }}</strong>
          <p>归一口径 {{ formatPrice(normalizedEarnings.normalized_fcf_per_share) }}</p>
        </article>
        <article class="normalized-card">
          <span>净利率</span>
          <strong>{{ formatPct(normalizedEarnings.current_net_margin_pct) }}</strong>
          <p>归一口径 {{ formatPct(normalizedEarnings.normalized_net_margin_pct) }}</p>
        </article>
      </div>
      <p class="normalized-note">{{ normalizedEarnings.explanation }}</p>
    </div>

    <div class="model-grid" v-if="valuationModels.length">
      <article
        v-for="model in valuationModels"
        :key="model.key"
        class="model-card"
        :class="{ 'model-card-muted': model.status !== 'available' }"
      >
        <div class="model-card-head">
          <div>
            <span class="valuation-card-title">{{ model.label }}</span>
            <p class="model-desc">{{ model.description || model.reason }}</p>
            <p v-if="model.basis_label" class="model-basis">{{ model.basis_label }}</p>
          </div>
          <span class="model-badge" :class="model.status === 'available' ? 'badge-ready' : 'badge-muted'">
            {{ model.status === 'available' ? Number(model.effective_weight_pct || 0).toFixed(0) + '% 权重' : '待补数' }}
          </span>
        </div>
        <template v-if="model.status === 'available'">
          <div class="valuation-main">{{ formatPrice(model.fair_value_range.price_base) }}</div>
          <div class="valuation-sub">区间 {{ formatPrice(model.fair_value_range.price_low) }} - {{ formatPrice(model.fair_value_range.price_high) }}</div>
          <div class="valuation-row">
            <span>模型结论</span>
            <strong>{{ model.summary }}</strong>
          </div>
          <div class="valuation-row">
            <span>折价 / 溢价</span>
            <strong>{{ model.discount_premium.label }} {{ formatPct(model.discount_premium.pct) }}</strong>
          </div>
          <div class="valuation-row">
            <span>经营回报</span>
            <strong>{{ formatPct(model.business_return_pct) }}</strong>
          </div>
          <div class="model-highlight-list">
            <span v-for="item in model.highlights" :key="item" class="model-highlight">{{ item }}</span>
          </div>
        </template>
        <div v-else class="model-state">{{ model.reason }}</div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  valuationConclusion: any
  valuationRange: any
  expectedReturn: any
  valuationModels: any[]
  valuationModelCount: number
  valuationBlend: any
  normalizedEarnings: any
  valuationSummaryClass: string
}>()

const calcParams = ref({
  expectedRoe: props.valuationConclusion?.assumptions?.expected_roe ?? 15,
  requiredReturn: 10
})

const ddmParams = ref({
  growthYears: 5,
  growthRate: 6.0,
  terminalGrowthRate: 2.0,
  discountRate: 8.0
})

const ddmD0 = computed(() => {
  const current = props.valuationConclusion?.current
  if (!current) return 0
  const price = current.price || 0
  const dy = current.dividend_yield || 0
  return price * dy
})

const ddmPv1 = computed(() => {
  const d0 = ddmD0.value
  const g1 = ddmParams.value.growthRate / 100
  const r = ddmParams.value.discountRate / 100
  const n = ddmParams.value.growthYears

  let pv = 0
  for (let t = 1; t <= n; t++) {
    pv += (d0 * Math.pow(1 + g1, t)) / Math.pow(1 + r, t)
  }
  return pv
})

const ddmPv2 = computed(() => {
  const d0 = ddmD0.value
  const g1 = ddmParams.value.growthRate / 100
  const g2 = ddmParams.value.terminalGrowthRate / 100
  const r = ddmParams.value.discountRate / 100
  const n = ddmParams.value.growthYears

  if (r <= g2) return 0
  const dn = d0 * Math.pow(1 + g1, n)
  const vn = (dn * (1 + g2)) / (r - g2)
  return vn / Math.pow(1 + r, n)
})

const ddmFairValue = computed(() => {
  if (ddmParams.value.discountRate <= ddmParams.value.terminalGrowthRate) return 0
  const val = ddmPv1.value + ddmPv2.value
  return isNaN(val) || val < 0 ? 0 : val
})

const ddmMos = computed(() => {
  const currentPrice = props.valuationConclusion?.current?.price || 0
  const fair = ddmFairValue.value
  if (fair <= 0) return 0
  return (fair - currentPrice) / fair
})

const ddmValuationLabel = computed(() => {
  const r = ddmParams.value.discountRate
  const g2 = ddmParams.value.terminalGrowthRate
  if (r <= g2) return '折现不足（要求回报率需大于永续增长率）'

  const mos = ddmMos.value
  if (mos >= 0.25) return '极度低估（黄金坑）'
  if (mos >= 0.05) return '偏低估（安全边际充足）'
  if (mos <= -0.15) return '严重高估（情绪泡沫）'
  return '合理中枢（估值对齐）'
})

const manualFairPb = computed(() => {
  const expectedRoe = Number(calcParams.value.expectedRoe || 0)
  const requiredReturn = Number(calcParams.value.requiredReturn || 0)
  if (expectedRoe <= 0 || requiredReturn <= 0) return 0
  return expectedRoe / requiredReturn
})

const manualFairPrice = computed(() => {
  const current = props.valuationConclusion?.current
  if (!current || current.pb <= 0) return 0
  return (current.price / current.pb) * manualFairPb.value
})

const manualValuationLabel = computed(() => {
  const currentPrice = props.valuationConclusion?.current?.price || 0
  if (currentPrice <= 0 || manualFairPrice.value <= 0) return '数据不足'
  const ratio = manualFairPrice.value / currentPrice
  if (ratio >= 1.2) return '偏低估'
  if (ratio <= 0.85) return '偏贵'
  return '合理'
})

const formatPct = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  return `${Number(v).toFixed(1)}%`
}

const formatSignedPct = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '--'
  const numeric = Number(v)
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toFixed(1)}%`
}

const formatPrice = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v) || v <= 0) return '--'
  return Number(v).toFixed(2)
}

const getNormalizedTone = (label?: string) => {
  if (label === '低于中枢') return 'normalized-positive'
  if (label === '高于中枢') return 'normalized-warning'
  return 'normalized-neutral'
}
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
.valuation-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}
.valuation-header h2 {
  font-size: 1.1rem;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px;
}
.valuation-summary {
  min-width: 140px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: right;
}
.summary-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
}
.summary-emerald {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #065f46;
}
.summary-amber {
  background: #fffbeb;
  border-color: #fde68a;
  color: #92400e;
}
.summary-rose {
  background: #fff1f2;
  border-color: #fecdd3;
  color: #9f1239;
}
.summary-slate {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #334155;
}
.valuation-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.valuation-grid-secondary {
  margin-top: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.valuation-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.valuation-card-primary {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border-color: #bfdbfe;
}
.valuation-card-title {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
  font-weight: 700;
}
.valuation-main {
  font-size: 1.5rem;
  line-height: 1.1;
  font-weight: 900;
  color: #0f172a;
  font-family: 'Monaco', monospace;
}
.valuation-sub {
  font-size: 0.95rem;
  font-weight: 700;
  color: #2563eb;
}
.valuation-note {
  font-size: 0.78rem;
  color: #64748b;
}
.valuation-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.88rem;
  color: #334155;
}
.section-footer-tight {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 6px;
  font-style: italic;
}
.section-footer {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 16px;
  font-style: italic;
}

/* 敏感度计算器 */
.calculator {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.input-group {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.input-group label { font-size: 0.9rem; font-weight: 600; color: #475569; }
.input-group input {
  width: 100px;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 700;
  color: #3b82f6;
  background: #f8fafc;
  text-align: center;
}
.result-box {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}
.compact-result {
  padding: 16px;
}
.res-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.res-label { font-size: 0.85rem; color: #64748b; font-weight: 600; }
.res-val { font-weight: 800; font-family: 'Monaco', monospace; }
.main-res {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #cbd5e1;
  font-size: 1.2rem;
}
.main-res .res-val { color: #3b82f6; }

/* DDM 股息折现动态沙盘 */
.ddm-sandbox-panel {
  margin-top: 18px;
  padding: 24px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.75) 0%, rgba(248, 250, 252, 0.75) 100%);
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 24px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.03);
}
.ddm-sandbox-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  border-bottom: 1px dashed rgba(226, 232, 240, 0.8);
  padding-bottom: 16px;
}
.ddm-sandbox-header strong {
  display: block;
  font-size: 0.9rem;
  color: #64748b;
  font-weight: 500;
  margin-top: 4px;
}
.ddm-badge {
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 800;
  background: #dcfce7;
  color: #15803d;
  box-shadow: 0 2px 8px rgba(22, 163, 74, 0.1);
  transition: all 0.2s ease;
}
.ddm-badge.ddm-badge-warning {
  background: #fef3c7;
  color: #b45309;
  box-shadow: 0 2px 8px rgba(217, 119, 6, 0.1);
}
.ddm-sandbox-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 32px;
  align-items: start;
}
.ddm-sliders {
  display: grid;
  gap: 20px;
}
.ddm-slider-group {
  display: grid;
  gap: 8px;
}
.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.88rem;
  font-weight: 700;
  color: #475569;
}
.slider-value {
  color: #0f172a;
  font-family: 'Monaco', monospace;
  font-size: 0.95rem;
  font-weight: 800;
}
.ddm-sliders input[type="range"] {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 99px;
  background: #e2e8f0;
  outline: none;
}
.ddm-sliders input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #0f172a;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  transition: all 0.1s ease;
}
.ddm-sliders input[type="range"]::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  background: #3b82f6;
  box-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
}
.ddm-results {
  display: grid;
  gap: 24px;
}
.ddm-result-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.ddm-res-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
}
.ddm-res-card span {
  font-size: 0.74rem;
  color: #64748b;
  font-weight: 600;
  text-align: center;
}
.ddm-res-card strong {
  font-size: 1.15rem;
  font-weight: 800;
  color: #0f172a;
}
.ddm-res-card-highlight {
  background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
  border-color: #a7f3d0;
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.05);
}
.ddm-res-card-highlight span {
  color: #047857;
}
.ddm-res-card .glow-value {
  font-size: 1.4rem;
  color: #10b981;
  text-shadow: 0 0 10px rgba(16, 185, 129, 0.1);
}
.ddm-res-card .text-error {
  color: #ef4444;
  text-shadow: none;
}
.ddm-mos-meter {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 16px;
  display: grid;
  gap: 12px;
}
.mos-meter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.84rem;
  font-weight: 700;
  color: #475569;
}
.mos-meter-header strong {
  font-size: 1.1rem;
  font-weight: 800;
}
.text-success { color: #10b981; }
.text-error { color: #f43f5e; }
.mos-track {
  position: relative;
  height: 8px;
  background: #e2e8f0;
  border-radius: 99px;
  overflow: visible;
}
.mos-bar {
  height: 100%;
  border-radius: 99px;
  transition: width 0.15s ease, background-color 0.15s ease;
}
.mos-marker {
  position: absolute;
  top: -4px;
  width: 2px;
  height: 16px;
  background: #64748b;
}
.mos-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: #94a3b8;
  font-weight: 600;
}
.ddm-warning-block {
  padding: 16px;
  border-radius: 16px;
  background: #fffbeb;
  border: 1px solid #fef3c7;
  color: #b45309;
  font-size: 0.84rem;
  line-height: 1.6;
  font-weight: 700;
}

/* 归一化口径 */
.normalized-panel {
  margin-top: 16px;
  padding: 20px;
  border-radius: 20px;
  border: 1px solid #dbe4f0;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
  display: grid;
  gap: 16px;
}
.normalized-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.normalized-header strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 1rem;
}
.normalized-badge {
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 800;
  border: 1px solid transparent;
  white-space: nowrap;
}
.normalized-badge.normalized-positive {
  background: #dcfce7;
  border-color: #86efac;
  color: #166534;
}
.normalized-badge.normalized-warning {
  background: #fff7ed;
  border-color: #fdba74;
  color: #c2410c;
}
.normalized-badge.normalized-neutral {
  background: #e2e8f0;
  border-color: #cbd5e1;
  color: #475569;
}
.normalized-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.normalized-card {
  padding: 16px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}
.normalized-card span {
  display: block;
  font-size: 0.76rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.normalized-card strong {
  display: block;
  margin-top: 10px;
  color: #0f172a;
  font-size: 1.35rem;
  font-weight: 900;
  font-family: 'Monaco', monospace;
}
.normalized-card p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 0.82rem;
  line-height: 1.6;
}
.normalized-note {
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

/* 多模型估值 */
.model-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.model-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbe4f0;
  border-radius: 16px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.model-card-muted {
  opacity: 0.72;
}
.model-card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.model-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
}
.badge-ready {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge-muted {
  background: #e2e8f0;
  color: #475569;
}
.model-desc {
  margin: 6px 0 0;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #64748b;
}
.model-state {
  font-size: 0.86rem;
  color: #64748b;
}
.model-highlight-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}
.model-highlight {
  padding: 6px 10px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 0.72rem;
  font-weight: 700;
}
.model-basis {
  margin: 8px 0 0;
  color: #2563eb;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
@media (max-width: 1180px) {
  .valuation-grid,
  .valuation-grid-secondary,
  .model-grid,
  .normalized-grid {
    grid-template-columns: 1fr;
  }
  .valuation-header {
    flex-direction: column;
    align-items: stretch;
  }
  .valuation-summary {
    text-align: left;
  }
  .ddm-sandbox-grid {
    grid-template-columns: 1fr;
    gap: 24px;
  }
}
</style>

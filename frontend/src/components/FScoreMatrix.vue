<template>
  <section class="section safety-section">
    <div class="section-header compact-header">
      <div>
        <p class="section-kicker">Safety Screen</p>
        <h2>F-Score 排雷</h2>
        <p class="subtitle">把九项财务信号压缩到一屏，快速剔除价值陷阱。</p>
      </div>
      <div class="score-pill" :class="scoreClass">
        {{ score }}/10
      </div>
    </div>
    <div class="f-score-matrix">
      <div v-for="item in details" :key="item.name" class="matrix-item">
        <div class="matrix-copy">
          <span class="matrix-name">{{ item.name }}</span>
          <span class="matrix-val">{{ item.val }}</span>
        </div>
        <span class="matrix-status" :class="{ passed: item.passed, failed: !item.passed }">
          {{ item.passed ? '通过' : '警惕' }}
        </span>
      </div>
    </div>
    <p class="section-footer">7 分以上通常代表财务结构扎实，3 分以下需要高度警惕"便宜但不安全"。</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  details: Array<{ name: string; val: string; passed: boolean }>
}>()

const scoreClass = computed(() => {
  if (props.score >= 7) return 'score-high'
  if (props.score <= 3) return 'score-low'
  return 'score-mid'
})
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
  grid-template-columns: repeat(3, 1fr);
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

<template>
  <details class="algo-explainer" :open="defaultOpen" @toggle="isOpen = ($event.target as HTMLDetailsElement).open">
    <summary class="algo-summary">
      <span class="algo-icon">?</span>
      <span class="algo-title">{{ title }}</span>
      <span class="algo-hint">click to {{ isOpen ? 'fold' : 'expand' }}</span>
    </summary>
    <div class="algo-content">
      <slot />
    </div>
  </details>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  title: string;
  defaultOpen?: boolean;
}>();

const isOpen = ref(props.defaultOpen ?? false)
</script>

<style scoped>
.algo-explainer {
  background: rgba(241, 245, 249, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  padding: 16px 20px;
  margin-bottom: 20px;
}

.algo-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  color: #334155;
  font-size: 0.95rem;
}

.algo-summary::-webkit-details-marker {
  display: none;
}

.algo-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 800;
  flex-shrink: 0;
}

.algo-title {
  flex: 1;
}

.algo-hint {
  font-size: 0.7rem;
  font-family: monospace;
  color: #94a3b8;
  font-weight: 600;
}

.algo-content {
  margin-top: 16px;
  font-size: 0.85rem;
  line-height: 1.8;
  color: #475569;
}

.algo-content :deep(h4) {
  font-size: 0.85rem;
  font-weight: 800;
  color: #1e293b;
  margin: 16px 0 8px;
}

.algo-content :deep(h4:first-child) {
  margin-top: 0;
}

.algo-content :deep(.formula) {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 16px;
  margin: 8px 0;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 0.8rem;
  color: #1e293b;
  line-height: 1.6;
  overflow-x: auto;
}

.algo-content :deep(.thresholds) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0;
}

.algo-content :deep(.threshold) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 0.78rem;
  font-weight: 600;
}

.algo-content :deep(.threshold-green) {
  background: #dcfce7;
  color: #166534;
}

.algo-content :deep(.threshold-yellow) {
  background: #fef9c3;
  color: #854d0e;
}

.algo-content :deep(.threshold-red) {
  background: #fee2e2;
  color: #991b1b;
}

.algo-content :deep(.threshold-gray) {
  background: #f1f5f9;
  color: #475569;
}

.algo-content :deep(ul) {
  margin: 4px 0;
  padding-left: 20px;
}

.algo-content :deep(li) {
  margin: 4px 0;
}

.algo-content :deep(.note) {
  font-size: 0.78rem;
  color: #94a3b8;
  font-style: italic;
  margin-top: 8px;
}
</style>

<template>
  <div class="space-y-3">
    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">合理估值（元/股）</label>
      <input v-model.number="intrinsic" type="number" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-mono text-cyan-600 outline-none focus:border-cyan-400" />
    </div>
    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">当前价格（元/股）</label>
      <input v-model.number="current" type="number" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-mono text-cyan-600 outline-none focus:border-cyan-400" />
    </div>

    <!-- Auto-fill from stock selector -->
    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">从监控股票填充</label>
      <select
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-cyan-400"
        @change="fillFromStock($event)"
      >
        <option value="">选择股票...</option>
        <option v-for="s in store.dashboardStocks" :key="s.stock_symbol" :value="s.stock_symbol">
          {{ s.stock_name }} ({{ s.stock_symbol }})
        </option>
      </select>
    </div>

    <!-- Results -->
    <div class="rounded-lg border p-3 space-y-2" :class="resultBorderClass">
      <div class="grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">折价/溢价率</div>
          <div class="text-sm font-mono font-bold" :class="discountPct < 0 ? 'text-emerald-600' : 'text-rose-500'">
            {{ discountPct > 0 ? '+' : '' }}{{ discountPct.toFixed(1) }}%
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">安全边际</div>
          <div class="text-sm font-mono font-bold" :class="marginClass">
            {{ marginPct.toFixed(1) }}%
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">建议买入价（7折）</div>
          <div class="text-sm font-mono font-bold text-cyan-600">
            ¥{{ buyPrice.toFixed(2) }}
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">估值状态</div>
          <div class="text-sm font-bold" :class="statusClass">
            {{ statusLabel }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

const store = useSentimentStore()

const intrinsic = ref(0)
const current = ref(0)

function fillFromStock(e: Event) {
  const symbol = (e.target as HTMLSelectElement).value
  if (!symbol) return
  const price = store.realtimePrices?.[symbol]
  if (price?.price) current.value = price.price
}

const discountPct = computed(() => {
  if (intrinsic.value <= 0) return 0
  return ((current.value / intrinsic.value) - 1) * 100
})

const marginPct = computed(() => {
  if (intrinsic.value <= 0) return 0
  return Math.max(0, ((intrinsic.value - current.value) / intrinsic.value) * 100)
})

const buyPrice = computed(() => intrinsic.value * 0.7)

const marginClass = computed(() => {
  if (marginPct.value >= 30) return 'text-emerald-400'
  if (marginPct.value >= 15) return 'text-amber-400'
  return 'text-rose-400'
})

const statusLabel = computed(() => {
  if (intrinsic.value <= 0) return '请输入估值'
  if (current.value <= intrinsic.value * 0.7) return '显著低估'
  if (current.value <= intrinsic.value * 0.9) return '低估'
  if (current.value <= intrinsic.value * 1.1) return '合理'
  if (current.value <= intrinsic.value * 1.3) return '偏贵'
  return '高估'
})

const statusClass = computed(() => {
  if (['显著低估', '低估'].includes(statusLabel.value)) return 'text-emerald-400'
  if (statusLabel.value === '合理') return 'text-amber-400'
  return 'text-rose-400'
})

const resultBorderClass = computed(() => {
  if (marginPct.value >= 30) return 'border-emerald-500/30 bg-emerald-500/5'
  if (marginPct.value >= 15) return 'border-amber-500/30 bg-amber-500/5'
  return 'border-slate-700/50 bg-slate-900/30'
})
</script>

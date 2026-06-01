<template>
  <div class="space-y-3">
    <div class="grid grid-cols-2 gap-2">
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">总资金</label>
        <input v-model.number="totalCapital" type="number" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">单笔最大亏损 %</label>
        <input v-model.number="maxLossPct" type="number" min="0.5" max="10" step="0.5" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
    </div>

    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">选择股票</label>
      <select
        v-model="selectedSymbol"
        class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-500"
      >
        <option value="">选择...</option>
        <option v-for="s in store.dashboardStocks" :key="s.stock_symbol" :value="s.stock_symbol">
          {{ s.stock_name }} — ¥{{ getPrice(s.stock_symbol) }}
        </option>
      </select>
    </div>

    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">止损幅度 %</label>
      <input v-model.number="stopLossPct" type="number" min="1" max="50" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
    </div>

    <!-- Results -->
    <div v-if="currentPrice > 0" class="rounded-lg border border-slate-700/50 bg-slate-900/30 p-3 space-y-2">
      <div class="grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">当前价</div>
          <div class="text-sm font-mono font-bold text-slate-200">¥{{ currentPrice.toFixed(2) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">止损价</div>
          <div class="text-sm font-mono font-bold text-rose-400">¥{{ stopPrice.toFixed(2) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">最大仓位金额</div>
          <div class="text-sm font-mono font-bold text-cyan-400">{{ formatMoney(maxPosition) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">可买股数</div>
          <div class="text-sm font-mono font-bold text-emerald-400">{{ shares }} 股</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">实际投入</div>
          <div class="text-sm font-mono font-bold text-slate-200">{{ formatMoney(actualCost) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">最大亏损</div>
          <div class="text-sm font-mono font-bold text-rose-400">{{ formatMoney(maxLossAmount) }}</div>
        </div>
      </div>
      <div class="border-t border-slate-700/50 pt-2">
        <div class="text-[10px] text-slate-500">仓位占比</div>
        <div class="mt-1 h-2 w-full rounded-full bg-slate-800">
          <div class="h-full rounded-full bg-cyan-500" :style="{ width: Math.min(100, positionPct) + '%' }"></div>
        </div>
        <div class="mt-1 text-[10px] font-mono text-slate-400">{{ positionPct.toFixed(1) }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

const store = useSentimentStore()

const totalCapital = ref(1000000)
const maxLossPct = ref(2)
const selectedSymbol = ref('')
const stopLossPct = ref(10)

function getPrice(symbol: string): string {
  const p = store.realtimePrices?.[symbol]?.price
  return p ? p.toFixed(2) : '--'
}

const currentPrice = computed(() => {
  if (!selectedSymbol.value) return 0
  return store.realtimePrices?.[selectedSymbol.value]?.price ?? 0
})

const stopPrice = computed(() => currentPrice.value * (1 - stopLossPct.value / 100))

const maxLossAmount = computed(() => totalCapital.value * maxLossPct.value / 100)

const maxPosition = computed(() => {
  const riskPerShare = currentPrice.value - stopPrice.value
  if (riskPerShare <= 0) return 0
  const maxShares = Math.floor(maxLossAmount.value / riskPerShare)
  return maxShares * currentPrice.value
})

const shares = computed(() => {
  if (currentPrice.value <= 0) return 0
  return Math.floor(maxPosition.value / currentPrice.value / 100) * 100 // 整手
})

const actualCost = computed(() => shares.value * currentPrice.value)

const positionPct = computed(() => {
  if (totalCapital.value <= 0) return 0
  return (actualCost.value / totalCapital.value) * 100
})

function formatMoney(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万'
  return v.toFixed(0)
}
</script>

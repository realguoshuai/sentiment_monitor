<template>
  <div class="space-y-3">
    <!-- Total Capital Input -->
    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500 uppercase">总资金（元）</label>
      <input
        v-model.number="totalCapital"
        type="number"
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-cyan-600 outline-none focus:border-cyan-400"
        placeholder="1000000"
      />
    </div>

    <!-- Stock Allocations -->
    <div>
      <div class="mb-2 flex items-center justify-between">
        <span class="text-[10px] font-bold text-slate-500 uppercase">持仓分配</span>
        <button
          class="text-[10px] text-cyan-600 hover:text-cyan-300"
          @click="equalWeight"
        >
          等权分配
        </button>
      </div>
      <div class="space-y-1.5 max-h-[240px] overflow-y-auto">
        <div
          v-for="s in store.dashboardStocks"
          :key="s.stock_symbol"
          class="flex items-center gap-2 rounded-lg bg-slate-50 px-2.5 py-1.5"
        >
          <span class="w-16 truncate text-[10px] text-slate-400">{{ s.stock_name }}</span>
          <input
            v-model.number="allocations[s.stock_symbol]"
            type="number"
            min="0"
            max="100"
            class="w-16 rounded border border-slate-300 bg-slate-900/50 px-2 py-0.5 text-right text-xs font-mono text-slate-700 outline-none focus:border-cyan-500"
            placeholder="0"
          />
          <span class="text-[10px] text-slate-500">%</span>
          <div class="flex-1 text-right">
            <span class="text-[10px] font-mono text-slate-500">
              {{ formatMoney(totalCapital * (allocations[s.stock_symbol] || 0) / 100) }}
            </span>
          </div>
        </div>
      </div>
      <div v-if="totalPct !== 100" class="mt-1 text-[10px]" :class="totalPct > 100 ? 'text-rose-500' : 'text-amber-600'">
        合计 {{ totalPct }}%{{ totalPct > 100 ? '（超额）' : '（未满仓）' }}
      </div>
    </div>

    <!-- Results -->
    <div class="rounded-lg border border-slate-300/50 bg-slate-900/30 p-3 space-y-2">
      <div class="text-[10px] font-bold text-slate-500 uppercase mb-2">组合指标</div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">年分红总额</div>
          <div class="text-sm font-mono font-bold text-emerald-600">
            {{ formatMoney(annualDividend) }}
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权股息率</div>
          <div class="text-sm font-mono font-bold text-cyan-600">
            {{ weightedDY.toFixed(2) }}%
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权 PE</div>
          <div class="text-sm font-mono font-bold text-slate-700">
            {{ weightedPE.toFixed(1) }}
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权 PB</div>
          <div class="text-sm font-mono font-bold text-slate-700">
            {{ weightedPB.toFixed(2) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

const store = useSentimentStore()

const totalCapital = ref(1000000)
const allocations = reactive<Record<string, number>>({})

// init with equal weight
const stocks = computed(() => store.dashboardStocks)
function equalWeight() {
  const n = stocks.value.length
  if (n === 0) return
  const pct = Math.floor(100 / n)
  for (const s of stocks.value) {
    allocations[s.stock_symbol] = pct
  }
  // distribute remainder to first
  const remainder = 100 - pct * n
  if (remainder > 0 && stocks.value.length > 0) {
    allocations[stocks.value[0].stock_symbol] += remainder
  }
}

const totalPct = computed(() => {
  return Object.values(allocations).reduce((sum, v) => sum + (v || 0), 0)
})

function getDY(symbol: string): number {
  const price = store.realtimePrices?.[symbol]
  return price?.dividend_yield ?? 0
}

function getPE(symbol: string): number {
  const price = store.realtimePrices?.[symbol]
  return price?.pe ?? 0
}

function getPB(symbol: string): number {
  const price = store.realtimePrices?.[symbol]
  return price?.pb ?? 0
}

const weightedDY = computed(() => {
  let wSum = 0
  let totalW = 0
  for (const s of stocks.value) {
    const pct = allocations[s.stock_symbol] || 0
    if (pct <= 0) continue
    const dy = getDY(s.stock_symbol)
    wSum += pct * dy
    totalW += pct
  }
  return totalW > 0 ? wSum / totalW : 0
})

const weightedPE = computed(() => {
  let wSum = 0
  let totalW = 0
  for (const s of stocks.value) {
    const pct = allocations[s.stock_symbol] || 0
    if (pct <= 0) continue
    const pe = getPE(s.stock_symbol)
    if (pe > 0) {
      wSum += pct * pe
      totalW += pct
    }
  }
  return totalW > 0 ? wSum / totalW : 0
})

const weightedPB = computed(() => {
  let wSum = 0
  let totalW = 0
  for (const s of stocks.value) {
    const pct = allocations[s.stock_symbol] || 0
    if (pct <= 0) continue
    const pb = getPB(s.stock_symbol)
    if (pb > 0) {
      wSum += pct * pb
      totalW += pct
    }
  }
  return totalW > 0 ? wSum / totalW : 0
})

const annualDividend = computed(() => {
  return totalCapital.value * weightedDY.value / 100
})

function formatMoney(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return v.toFixed(0)
}
</script>

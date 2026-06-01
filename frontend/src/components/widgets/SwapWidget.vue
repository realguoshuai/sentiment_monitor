<template>
  <div class="space-y-3">
    <!-- Stock A -->
    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div class="mb-2 text-[10px] font-bold text-slate-500 uppercase">股票 A（卖出）</div>
      <select
        v-model="symbolA"
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-rose-400"
      >
        <option value="">选择股票...</option>
        <option v-for="s in store.dashboardStocks" :key="s.stock_symbol" :value="s.stock_symbol">
          {{ s.stock_name }} — ¥{{ getPrice(s.stock_symbol) }}
        </option>
      </select>
      <div v-if="priceA > 0" class="mt-2 flex items-center justify-between text-[10px]">
        <span class="text-slate-400">当前价</span>
        <span class="font-mono font-bold text-slate-700">¥{{ priceA.toFixed(2) }}</span>
      </div>
    </div>

    <!-- Swap Arrow -->
    <div class="flex items-center justify-center">
      <button
        class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition-all hover:border-rose-300 hover:text-rose-500 hover:rotate-180"
        @click="swapStocks"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      </button>
    </div>

    <!-- Stock B -->
    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div class="mb-2 text-[10px] font-bold text-slate-500 uppercase">股票 B（买入）</div>
      <select
        v-model="symbolB"
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-emerald-400"
      >
        <option value="">选择股票...</option>
        <option v-for="s in store.dashboardStocks" :key="s.stock_symbol" :value="s.stock_symbol">
          {{ s.stock_name }} — ¥{{ getPrice(s.stock_symbol) }}
        </option>
      </select>
      <div v-if="priceB > 0" class="mt-2 flex items-center justify-between text-[10px]">
        <span class="text-slate-400">当前价</span>
        <span class="font-mono font-bold text-slate-700">¥{{ priceB.toFixed(2) }}</span>
      </div>
    </div>

    <!-- Ratio Input -->
    <div>
      <label class="mb-1 block text-[10px] font-bold text-slate-500">换股比例（1 股 A = ? 股 B）</label>
      <div class="flex items-center gap-2">
        <input
          v-model.number="ratio"
          type="number"
          step="0.01"
          min="0"
          class="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-mono text-cyan-600 outline-none focus:border-cyan-400"
          placeholder="1.0"
        />
        <button
          class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] text-slate-500 hover:bg-slate-50"
          @click="ratio = impliedRatio"
          title="使用市场隐含比例"
        >
          用市价比
        </button>
      </div>
    </div>

    <!-- Results -->
    <div v-if="priceA > 0 && priceB > 0 && ratio > 0" class="rounded-lg border border-slate-200 bg-slate-50/80 p-3 space-y-2">
      <div class="text-[10px] font-bold text-slate-500 uppercase mb-2">换股分析</div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">市场隐含比例</div>
          <div class="text-sm font-mono font-bold text-slate-700">{{ impliedRatio.toFixed(4) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">你设的比例</div>
          <div class="text-sm font-mono font-bold text-cyan-600">{{ ratio.toFixed(4) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">换股溢价率</div>
          <div class="text-sm font-mono font-bold" :class="swapPremium > 0 ? 'text-rose-500' : 'text-emerald-600'">
            {{ swapPremium > 0 ? '+' : '' }}{{ swapPremium.toFixed(2) }}%
          </div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">换股折价率</div>
          <div class="text-sm font-mono font-bold" :class="swapDiscount > 0 ? 'text-emerald-600' : 'text-slate-700'">
            {{ swapDiscount > 0 ? swapDiscount.toFixed(2) + '%' : '—' }}
          </div>
        </div>
      </div>

      <!-- Verdict -->
      <div class="border-t border-slate-200 pt-2">
        <div class="rounded-lg px-3 py-2 text-[10px]" :class="verdictClass">
          <span class="font-bold">{{ verdictLabel }}</span>
          <span class="ml-1">{{ verdictDesc }}</span>
        </div>
      </div>

      <!-- Target Prices -->
      <div class="border-t border-slate-200 pt-2 space-y-1">
        <div class="text-[10px] font-bold text-slate-500 uppercase">目标价参考</div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <div class="text-[10px] text-slate-400">A 跌到此价时换股无差异</div>
            <div class="text-xs font-mono font-bold text-rose-500">¥{{ breakEvenPriceA.toFixed(2) }}</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-400">B 涨到此价时换股无差异</div>
            <div class="text-xs font-mono font-bold text-emerald-600">¥{{ breakEvenPriceB.toFixed(2) }}</div>
          </div>
        </div>
      </div>

      <!-- DY comparison -->
      <div class="border-t border-slate-200 pt-2">
        <div class="text-[10px] font-bold text-slate-500 uppercase mb-1">股息率对比</div>
        <div class="flex items-center gap-3 text-[10px]">
          <span class="text-slate-400">A: <span class="font-mono font-bold" :class="dyA > dyB ? 'text-emerald-600' : 'text-slate-700'">{{ dyA.toFixed(2) }}%</span></span>
          <span class="text-slate-400">B: <span class="font-mono font-bold" :class="dyB > dyA ? 'text-emerald-600' : 'text-slate-700'">{{ dyB.toFixed(2) }}%</span></span>
          <span class="text-slate-400">差: <span class="font-mono font-bold text-cyan-600">{{ (dyB - dyA).toFixed(2) }}%</span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

const store = useSentimentStore()

const symbolA = ref('')
const symbolB = ref('')
const ratio = ref(0)

function getPrice(symbol: string): number {
  return store.realtimePrices?.[symbol]?.price ?? 0
}

const priceA = computed(() => getPrice(symbolA.value))
const priceB = computed(() => getPrice(symbolB.value))
const dyA = computed(() => store.realtimePrices?.[symbolA.value]?.dividend_yield ?? 0)
const dyB = computed(() => store.realtimePrices?.[symbolB.value]?.dividend_yield ?? 0)

// Market implied ratio: how many shares of B you get for 1 share of A at current prices
const impliedRatio = computed(() => {
  if (priceA.value <= 0 || priceB.value <= 0) return 0
  return priceA.value / priceB.value
})

// Swap premium: positive means you're paying more than market (bad), negative means discount (good)
const swapPremium = computed(() => {
  if (impliedRatio.value <= 0 || ratio.value <= 0) return 0
  return ((ratio.value / impliedRatio.value) - 1) * 100
})

const swapDiscount = computed(() => swapPremium.value < 0 ? Math.abs(swapPremium.value) : 0)

// Break-even prices
const breakEvenPriceA = computed(() => {
  if (ratio.value <= 0) return 0
  return priceB.value * ratio.value
})

const breakEvenPriceB = computed(() => {
  if (ratio.value <= 0) return 0
  return priceA.value / ratio.value
})

const verdictLabel = computed(() => {
  if (swapPremium.value <= -5) return '✅ 有利换股'
  if (swapPremium.value <= 0) return '✅ 略有折价'
  if (swapPremium.value <= 5) return '⚠️ 略有溢价'
  return '❌ 溢价过高'
})

const verdictDesc = computed(() => {
  if (swapPremium.value <= -5) return '你用低于市价的比例换到了 B 股，占便宜了。'
  if (swapPremium.value <= 0) return '换股比例低于市价，略有折价。'
  if (swapPremium.value <= 5) return '换股比例略高于市价，溢价在合理范围。'
  return '换股比例远高于市价，你亏了，建议等比例降低。'
})

const verdictClass = computed(() => {
  if (swapPremium.value <= 0) return 'bg-emerald-50 border border-emerald-200 text-emerald-700'
  if (swapPremium.value <= 5) return 'bg-amber-50 border border-amber-200 text-amber-700'
  return 'bg-rose-50 border border-rose-200 text-rose-700'
})

function swapStocks() {
  const tmp = symbolA.value
  symbolA.value = symbolB.value
  symbolB.value = tmp
  if (ratio.value > 0) ratio.value = 1 / ratio.value
}
</script>

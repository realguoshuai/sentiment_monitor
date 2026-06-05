<template>
  <div class="space-y-3">
    <!-- Mode Toggle & Save -->
    <div class="flex items-center gap-2">
      <div class="flex-1 flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
        <button
          class="flex-1 rounded-md px-3 py-1 text-[10px] font-bold transition-all"
          :class="mode === 'pct' ? 'bg-white text-cyan-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'"
          @click="mode = 'pct'"
        >
          📊 百分比分配
        </button>
        <button
          class="flex-1 rounded-md px-3 py-1 text-[10px] font-bold transition-all"
          :class="mode === 'shares' ? 'bg-white text-emerald-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'"
          @click="mode = 'shares'"
        >
          🔢 指定股数
        </button>
      </div>
      <button
        @click="savePortfolio"
        :disabled="isSaving"
        class="px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-400 text-white rounded text-[10px] font-bold transition-colors"
      >
        {{ isSaving ? '保存中...' : '💾 保存' }}
      </button>
    </div>
    <div v-if="saveMessage" class="text-[10px]" :class="saveSuccess ? 'text-emerald-600' : 'text-rose-500'">
      {{ saveMessage }}
    </div>

    <!-- Mode A: Percentage -->
    <template v-if="mode === 'pct'">
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500 uppercase">总资金（元）</label>
        <input
          v-model.number="totalCapital"
          type="number"
          class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-cyan-600 outline-none focus:border-cyan-400"
          placeholder="1000000"
        />
      </div>
      <div>
        <div class="mb-2 flex items-center justify-between">
          <span class="text-[10px] font-bold text-slate-500 uppercase">持仓分配</span>
          <button class="text-[10px] text-cyan-600 hover:text-cyan-500" @click="equalWeight">等权分配</button>
        </div>
        <div class="space-y-1 max-h-[220px] overflow-y-auto">
          <div
            v-for="s in store.dashboardStocks"
            :key="s.stock_symbol"
            class="flex items-center gap-2 rounded-lg bg-slate-50 px-2.5 py-1.5"
          >
            <span class="w-14 truncate text-[10px] text-slate-500">{{ s.stock_name }}</span>
            <input
              v-model.number="pctAlloc[s.stock_symbol]"
              type="number" min="0" max="100"
              class="w-14 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-700 outline-none focus:border-cyan-400"
              placeholder="0"
            />
            <span class="text-[10px] text-slate-400">%</span>
            <span class="flex-1 text-right text-[10px] font-mono text-slate-400">
              {{ fmtMoney(totalCapital * (pctAlloc[s.stock_symbol] || 0) / 100) }}
            </span>
          </div>
        </div>
        <div v-if="pctTotal !== 100" class="mt-1 text-[10px]" :class="pctTotal > 100 ? 'text-rose-500' : 'text-amber-600'">
          合计 {{ pctTotal }}%{{ pctTotal > 100 ? '（超额）' : '（未满仓）' }}
        </div>
      </div>
    </template>

    <!-- Mode B: Share Count -->
    <template v-else>
      <div class="space-y-1 max-h-[300px] overflow-y-auto">
        <div
          v-for="s in store.dashboardStocks"
          :key="s.stock_symbol"
          class="rounded-lg bg-slate-50 px-2.5 py-2"
        >
          <div class="mb-1 flex items-center justify-between">
            <span class="text-[10px] font-bold text-slate-600">{{ s.stock_name }}</span>
            <span class="text-[10px] font-mono text-slate-400">¥{{ getPrice(s.stock_symbol) }}</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="shareCounts[s.stock_symbol]"
              type="number" min="0" step="100"
              class="w-20 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-700 outline-none focus:border-emerald-400"
              placeholder="0"
            />
            <span class="text-[10px] text-slate-400">股</span>
            <span class="flex-1 text-right text-[10px] font-mono text-emerald-600">
              {{ fmtMoney(getCost(s.stock_symbol)) }}
            </span>
          </div>
        </div>
      </div>
      <div class="text-[10px] text-slate-500">
        总投入: <span class="font-mono font-bold text-slate-700">{{ fmtMoney(sharesTotalCost) }}</span>
      </div>
    </template>

    <!-- Results (both modes) -->
    <div class="rounded-lg border border-slate-200 bg-slate-50/80 p-3 space-y-2">
      <div class="text-[10px] font-bold text-slate-500 uppercase mb-2">组合指标</div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">年分红总额</div>
          <div class="text-sm font-mono font-bold text-emerald-600">{{ fmtMoney(annualDividend) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权股息率</div>
          <div class="text-sm font-mono font-bold text-cyan-600">{{ weightedDY.toFixed(2) }}%</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权 PE</div>
          <div class="text-sm font-mono font-bold text-slate-700">{{ weightedPE.toFixed(1) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">加权 PB</div>
          <div class="text-sm font-mono font-bold text-slate-700">{{ weightedPB.toFixed(2) }}</div>
        </div>
      </div>
      <div v-if="mode === 'shares'" class="border-t border-slate-200 pt-2 grid grid-cols-2 gap-2">
        <div>
          <div class="text-[10px] text-slate-500">总投入</div>
          <div class="text-sm font-mono font-bold text-slate-700">{{ fmtMoney(sharesTotalCost) }}</div>
        </div>
        <div>
          <div class="text-[10px] text-slate-500">年化分红/投入</div>
          <div class="text-sm font-mono font-bold text-emerald-600">
            {{ sharesTotalCost > 0 ? (annualDividend / sharesTotalCost * 100).toFixed(2) : '0.00' }}%
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import { portfolioApi } from '@/api'

const store = useSentimentStore()

const mode = ref<'pct' | 'shares'>('pct')
const totalCapital = ref(1000000)
const pctAlloc = reactive<Record<string, number>>({})
const shareCounts = reactive<Record<string, number>>({})
const isSaving = ref(false)
const saveMessage = ref('')
const saveSuccess = ref(false)

// 从后端加载组合
onMounted(async () => {
  try {
    const { data } = await portfolioApi.getPortfolio()
    if (data) {
      totalCapital.value = data.total_capital || 1000000
      // 恢复持仓数据
      for (const h of data.holdings || []) {
        pctAlloc[h.symbol] = h.allocation_pct || 0
        shareCounts[h.symbol] = h.share_count || 0
      }
    }
  } catch (e) {
    console.warn('加载组合失败，使用默认值', e)
  }
})

// 保存组合到后端
async function savePortfolio() {
  isSaving.value = true
  saveMessage.value = ''

  try {
    const holdings = store.dashboardStocks
      .filter(s => (pctAlloc[s.stock_symbol] || 0) > 0 || (shareCounts[s.stock_symbol] || 0) > 0)
      .map(s => ({
        symbol: s.stock_symbol,
        allocation_pct: pctAlloc[s.stock_symbol] || 0,
        share_count: shareCounts[s.stock_symbol] || 0,
      }))

    await portfolioApi.savePortfolio({
      total_capital: totalCapital.value,
      holdings,
    })

    saveSuccess.value = true
    saveMessage.value = '保存成功'
  } catch (e) {
    saveSuccess.value = false
    saveMessage.value = '保存失败'
    console.error('保存组合失败', e)
  } finally {
    isSaving.value = false
    // 3秒后清除消息
    setTimeout(() => { saveMessage.value = '' }, 3000)
  }
}

const stocks = computed(() => store.dashboardStocks)

function getPrice(symbol: string): string {
  return (store.realtimePrices?.[symbol]?.price ?? 0).toFixed(2)
}

function getDY(symbol: string): number { return store.realtimePrices?.[symbol]?.dividend_yield ?? 0 }
function getPE(symbol: string): number { return store.realtimePrices?.[symbol]?.pe ?? 0 }
function getPB(symbol: string): number { return store.realtimePrices?.[symbol]?.pb ?? 0 }

// Mode A helpers
function equalWeight() {
  const n = stocks.value.length
  if (n === 0) return
  const pct = Math.floor(100 / n)
  for (const s of stocks.value) pctAlloc[s.stock_symbol] = pct
  const remainder = 100 - pct * n
  if (remainder > 0) pctAlloc[stocks.value[0].stock_symbol] += remainder
}

const pctTotal = computed(() => Object.values(pctAlloc).reduce((s, v) => s + (v || 0), 0))

// Mode B helpers
function getCost(symbol: string): number {
  const shares = shareCounts[symbol] || 0
  const price = store.realtimePrices?.[symbol]?.price ?? 0
  return shares * price
}

const sharesTotalCost = computed(() =>
  stocks.value.reduce((sum, s) => sum + getCost(s.stock_symbol), 0)
)

// Unified computation — works for both modes via value weights
interface WeightedItem { value: number; dy: number; pe: number; pb: number }

const weightedItems = computed<WeightedItem[]>(() => {
  if (mode.value === 'pct') {
    return stocks.value
      .map((s) => {
        const pct = pctAlloc[s.stock_symbol] || 0
        if (pct <= 0) return null
        return { value: pct, dy: getDY(s.stock_symbol), pe: getPE(s.stock_symbol), pb: getPB(s.stock_symbol) }
      })
      .filter(Boolean) as WeightedItem[]
  }
  // shares mode
  return stocks.value
    .map((s) => {
      const cost = getCost(s.stock_symbol)
      if (cost <= 0) return null
      return { value: cost, dy: getDY(s.stock_symbol), pe: getPE(s.stock_symbol), pb: getPB(s.stock_symbol) }
    })
    .filter(Boolean) as WeightedItem[]
})

function weightedAvg(field: 'dy' | 'pe' | 'pb', filterPositive = false): number {
  let wSum = 0, totalW = 0
  for (const item of weightedItems.value) {
    const v = item[field]
    if (filterPositive && v <= 0) continue
    wSum += item.value * v
    totalW += item.value
  }
  return totalW > 0 ? wSum / totalW : 0
}

const weightedDY = computed(() => weightedAvg('dy'))
const weightedPE = computed(() => weightedAvg('pe', true))
const weightedPB = computed(() => weightedAvg('pb', true))

const annualDividend = computed(() => {
  if (mode.value === 'pct') return totalCapital.value * weightedDY.value / 100
  // shares mode: sum each stock's dividend
  return stocks.value.reduce((sum, s) => {
    const cost = getCost(s.stock_symbol)
    return sum + cost * getDY(s.stock_symbol) / 100
  }, 0)
})

function fmtMoney(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return v.toFixed(0)
}
</script>

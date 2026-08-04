<template>
  <div class="space-y-3 text-slate-800">
    <!-- Mode Toggle & Save -->
    <div class="flex items-center gap-2">
      <div class="flex-1 flex rounded-lg border border-slate-300 bg-slate-100 p-0.5">
        <button
          class="flex-1 rounded-md px-3 py-1 text-[10px] font-bold transition-all"
          :class="mode === 'pct' ? 'bg-white text-cyan-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
          @click="mode = 'pct'"
        >
          百分比分配
        </button>
        <button
          class="flex-1 rounded-md px-3 py-1 text-[10px] font-bold transition-all"
          :class="mode === 'shares' ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'"
          @click="mode = 'shares'"
        >
          指定股数
        </button>
      </div>
      <button
        @click="savePortfolio"
        :disabled="isSaving"
        class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-400 text-white rounded text-[10px] font-bold transition-colors"
      >
        {{ isSaving ? '保存中...' : '保存' }}
      </button>
    </div>
    <div v-if="saveMessage" class="text-[10px]" :class="saveSuccess ? 'text-emerald-600' : 'text-rose-600'">
      {{ saveMessage }}
    </div>

    <!-- 添加持仓：直接输入 + 从自选添加 -->
    <div class="space-y-1.5">
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="text-[10px] text-cyan-600 hover:text-cyan-700"
          @click="pickerOpen = !pickerOpen"
        >
          {{ pickerOpen ? '收起自选列表' : '+ 从自选添加持仓' }}
        </button>
        <button
          class="text-[10px] text-emerald-600 hover:text-emerald-700"
          @click="customOpen = !customOpen"
        >
          {{ customOpen ? '收起手动添加' : '+ 添加持仓' }}
        </button>
      </div>

      <!-- 自选列表 -->
      <div v-if="pickerOpen" class="max-h-[160px] overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-1">
        <div v-if="!availableWatchlist.length" class="px-2 py-1.5 text-[10px] text-slate-400">
          自选股已全部在持仓中
        </div>
        <button
          v-for="s in availableWatchlist"
          :key="s.stock_symbol"
          class="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[10px] hover:bg-white"
          @click="addHolding(s)"
        >
          <span class="truncate text-slate-700">{{ s.stock_name }}</span>
          <span class="font-mono text-slate-400">{{ s.stock_symbol }}</span>
        </button>
      </div>

      <!-- 手动添加 -->
      <div v-if="customOpen" class="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 p-1.5">
        <input
          v-model="newSymbol"
          type="text"
          class="w-20 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-mono text-slate-800 outline-none focus:border-emerald-500"
          placeholder="代码"
        />
        <input
          v-model="newName"
          type="text"
          class="w-20 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 outline-none focus:border-emerald-500"
          placeholder="名称"
        />
        <button
          class="rounded bg-emerald-600 px-2 py-1 text-[10px] font-bold text-white hover:bg-emerald-500 disabled:bg-slate-400"
          :disabled="!newSymbol.trim()"
          @click="addCustomHolding"
        >
          添加
        </button>
      </div>
    </div>

    <!-- Mode A: Percentage -->
    <template v-if="mode === 'pct'">
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500 uppercase">总资金（参考，元）</label>
        <input
          v-model.number="totalCapital"
          type="number"
          class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-slate-800 outline-none focus:border-cyan-500"
          placeholder="1000000"
        />
      </div>
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500 uppercase">现金余额（元）</label>
        <input
          v-model.number="cashBalance"
          type="number"
          class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-slate-800 outline-none focus:border-emerald-500"
          placeholder="0"
        />
      </div>
      <div>
        <div class="mb-2 flex items-center justify-between">
          <span class="text-[10px] font-bold text-slate-500 uppercase">持仓分配</span>
          <button class="text-[10px] text-cyan-600 hover:text-cyan-700" @click="equalWeight">等权分配</button>
        </div>
        <div v-if="!holdingsList.length" class="rounded-lg bg-slate-50 px-2.5 py-3 text-center text-[10px] text-slate-400">
          暂无持仓，点上方「从自选添加持仓」
        </div>
        <div v-else class="space-y-1 max-h-[200px] overflow-y-auto">
          <div
            v-for="h in holdingsList"
            :key="h.symbol"
            class="flex items-center gap-2 rounded-lg bg-slate-50 px-2.5 py-1.5"
          >
            <span class="w-14 truncate text-[10px] text-slate-700">{{ h.name }}</span>
            <input
              v-model.number="h.allocation_pct"
              type="number" min="0" max="100"
              class="w-14 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-800 outline-none focus:border-cyan-500"
              placeholder="0"
            />
            <span class="text-[10px] text-slate-400">%</span>
            <span class="flex-1 text-right text-[10px] font-mono text-slate-500">
              {{ fmtMoney(totalCapital * (h.allocation_pct || 0) / 100) }}
            </span>
            <button class="text-[10px] text-rose-500 hover:text-rose-600" @click="removeHolding(h.symbol)">移除</button>
          </div>
        </div>
        <div v-if="pctTotal !== 100" class="mt-1 text-[10px]" :class="pctTotal > 100 ? 'text-rose-600' : 'text-amber-600'">
          持仓合计 {{ pctTotal }}%（剩余 {{ (100 - pctTotal).toFixed(1) }}% 为现金）
        </div>
        <div v-else class="mt-1 text-[10px] text-emerald-600">持仓 100%，已满仓</div>
      </div>
    </template>

    <!-- Mode B: Share Count -->
    <template v-else>
      <div v-if="!holdingsList.length" class="rounded-lg bg-slate-50 px-2.5 py-3 text-center text-[10px] text-slate-400">
        暂无持仓，点上方「从自选添加持仓」
      </div>
      <div v-else class="space-y-1 max-h-[260px] overflow-y-auto">
        <div
          v-for="h in holdingsList"
          :key="h.symbol"
          class="rounded-lg bg-slate-50 px-2.5 py-2"
        >
          <div class="mb-1 flex items-center justify-between">
            <span class="text-[10px] font-bold text-slate-700">{{ h.name }}</span>
            <button class="text-[10px] text-rose-500 hover:text-rose-600" @click="removeHolding(h.symbol)">移除</button>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="h.share_count"
              type="number" min="0" step="100"
              class="w-20 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-800 outline-none focus:border-emerald-500"
              placeholder="0"
            />
            <span class="text-[10px] text-slate-400">股</span>
            <input
              v-model.number="h.buy_price"
              type="number" min="0" step="0.01"
              class="w-20 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-800 outline-none focus:border-emerald-500"
              placeholder="买入价"
            />
            <span class="flex-1 text-right text-[10px] font-mono text-emerald-600">
              {{ fmtMoney(hMarketValue(h)) }}
            </span>
          </div>
        </div>
      </div>
      <!-- 指定股数模式：现金余额输入（红框位置） -->
      <div class="flex items-center justify-between rounded-lg border border-dashed border-slate-300 bg-slate-50 px-2.5 py-1.5">
        <span class="text-[10px] font-bold text-emerald-700">现金余额</span>
        <div class="flex items-center gap-1.5">
          <input
            v-model.number="cashBalance"
            type="number"
            min="0"
            step="100"
            class="w-24 rounded border border-slate-300 bg-white px-2 py-0.5 text-right text-xs font-mono text-slate-800 outline-none focus:border-emerald-500"
            placeholder="0"
          />
          <span class="text-[10px] text-slate-400">元</span>
        </div>
      </div>

      <div v-if="holdingsList.length" class="flex items-center justify-between text-[10px] text-slate-500">
        <span>总成本(买入): <span class="font-mono font-bold text-slate-800">{{ fmtMoney(sharesTotalCost) }}</span></span>
        <span>总市值: <span class="font-mono font-bold text-slate-800">{{ fmtMoney(sharesTotalMV) }}</span></span>
      </div>
    </template>

    <!-- 组合概览（实时市值/盈亏/权重/再平衡，来自后端） -->
    <div class="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-bold text-slate-500 uppercase">组合概览</span>
        <button
          @click="refresh"
          :disabled="loadingSummary"
          class="text-[10px] text-cyan-600 hover:text-cyan-700 disabled:text-slate-400"
        >
          {{ loadingSummary ? '刷新中...' : '↻ 刷新' }}
        </button>
      </div>

      <div class="flex items-end justify-between">
        <div>
          <div class="text-[10px] text-slate-500">总资产（持仓市值+现金）</div>
          <div class="text-base font-mono font-bold text-slate-900">{{ fmtMoney(summary.total_assets) }}</div>
          <div class="text-[9px] text-slate-400">持仓市值 {{ fmtMoney(summary.total_market_value) }} · 现金 {{ fmtMoney(summary.cash_balance) }}</div>
        </div>
        <div class="text-right">
          <div class="text-[10px] text-slate-500">总浮盈亏</div>
          <div class="text-sm font-mono font-bold" :class="pnlClass(summary.total_pnl)">
            {{ summary.total_pnl >= 0 ? '+' : '' }}{{ fmtMoney(summary.total_pnl) }}
            ({{ summary.total_pnl_pct >= 0 ? '+' : '' }}{{ summary.total_pnl_pct }}%)
          </div>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-1.5">
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">收益率</div>
          <div class="text-xs font-mono font-bold" :class="pnlClass(summary.total_pnl_pct)">{{ summary.total_pnl_pct }}%</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">年分红</div>
          <div class="text-xs font-mono font-bold text-emerald-600">{{ fmtMoney(annualDividend) }}</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">集中度</div>
          <div class="text-xs font-mono font-bold text-slate-800">{{ summary.concentration_hhi }}</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">加权DY</div>
          <div class="text-xs font-mono font-bold text-cyan-700">{{ summary.weighted_dividend_yield }}%</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">加权PE</div>
          <div class="text-xs font-mono font-bold text-slate-800">{{ summary.weighted_pe }}</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">加权PB</div>
          <div class="text-xs font-mono font-bold text-slate-800">{{ summary.weighted_pb }}</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">现金余额</div>
          <div class="text-xs font-mono font-bold text-emerald-600">{{ fmtMoney(summary.cash_balance) }}</div>
        </div>
        <div class="rounded border border-slate-200 bg-white px-2 py-1">
          <div class="text-[9px] text-slate-400">现金占比</div>
          <div class="text-xs font-mono font-bold text-emerald-600">{{ summary.cash_ratio }}%</div>
        </div>
      </div>

      <div v-if="!summary.price_available" class="text-[10px] text-amber-600">
        行情暂不可用（可能被代理拦截），市值为 0，请关闭 Clash TUN 后刷新
      </div>

      <!-- 每持仓：市值 / 盈亏 / 权重 -->
      <div v-if="summary.holdings.length" class="space-y-1.5 pt-1">
        <div
          v-for="h in summary.holdings"
          :key="h.symbol"
          class="rounded border border-slate-200 bg-white px-2 py-1.5"
        >
          <div class="flex items-center justify-between text-[10px]">
            <span class="font-bold text-slate-800">{{ h.name }}</span>
            <span class="font-mono text-slate-400">{{ h.symbol }}</span>
          </div>
          <div class="mt-0.5 flex items-center justify-between text-[10px] font-mono">
            <span class="text-slate-500">¥{{ h.current_price }} · 市值 {{ fmtMoney(h.market_value) }}</span>
            <span :class="pnlClass(h.pnl)">
              {{ h.pnl >= 0 ? '+' : '' }}{{ fmtMoney(h.pnl) }} ({{ h.pnl_pct >= 0 ? '+' : '' }}{{ h.pnl_pct }}%)
            </span>
          </div>
          <div class="mt-1 flex items-center gap-2">
            <div class="relative h-1.5 flex-1 rounded bg-slate-200">
              <div class="absolute left-0 top-0 h-1.5 rounded bg-cyan-600" :style="{ width: Math.min(h.current_weight, 100) + '%' }"></div>
              <div class="absolute top-[-2px] h-2.5 w-0.5 bg-slate-700" :style="{ left: Math.min(h.target_weight, 100) + '%' }"></div>
            </div>
            <span class="w-10 text-right text-[9px] font-mono text-slate-500">{{ h.current_weight }}%</span>
            <span class="w-8 text-right text-[9px]" :class="driftInfo(h.drift).c">{{ driftInfo(h.drift).t }}</span>
          </div>
        </div>
        <!-- 现金伪持仓：展示其权重，使权重条凑满 100% -->
        <div class="rounded border border-dashed border-slate-300 bg-white px-2 py-1.5">
          <div class="flex items-center justify-between text-[10px]">
            <span class="font-bold text-emerald-700">现金</span>
            <span class="font-mono text-slate-400">idle cash</span>
          </div>
          <div class="mt-1 flex items-center gap-2">
            <div class="relative h-1.5 flex-1 rounded bg-slate-200">
              <div class="absolute left-0 top-0 h-1.5 rounded bg-emerald-500" :style="{ width: Math.min(summary.cash_ratio, 100) + '%' }"></div>
            </div>
            <span class="w-10 text-right text-[9px] font-mono text-emerald-600">{{ summary.cash_ratio }}%</span>
            <span class="w-8 text-right text-[9px] text-slate-400">—</span>
          </div>
        </div>
      </div>

      <!-- 再平衡建议 -->
      <div v-if="rebalanceList.length" class="border-t border-slate-200 pt-1.5">
        <div class="mb-1 text-[10px] text-slate-500">再平衡：<span class="text-rose-600">{{ rebalanceList.length }} 项偏离</span></div>
        <div class="space-y-0.5">
          <div v-for="r in rebalanceList" :key="r.symbol" class="flex items-center justify-between text-[10px] font-mono">
            <span class="text-slate-700">{{ r.name }}</span>
            <span :class="r.action === 'sell' ? 'text-rose-600' : 'text-emerald-600'">
              {{ r.action === 'sell' ? '卖出' : '买入' }} {{ Math.abs(r.shares_to_trade) }} 股
            </span>
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
const cashBalance = ref(0)
const holdingsList = reactive<any[]>([])
const pickerOpen = ref(false)
const customOpen = ref(false)
const newSymbol = ref('')
const newName = ref('')
const isSaving = ref(false)
const saveMessage = ref('')
const saveSuccess = ref(false)

// 组合概览（后端计算）
const summary = ref<any>(emptySummary())
const loadingSummary = ref(false)

function emptySummary() {
  return {
    name: '默认组合',
    total_capital: 0,
    cash_balance: 0,
    total_assets: 0,
    total_market_value: 0,
    cash_ratio: 0,
    total_cost: 0,
    total_pnl: 0,
    total_pnl_pct: 0,
    weighted_dividend_yield: 0,
    weighted_pe: 0,
    weighted_pb: 0,
    concentration_hhi: 0,
    top1_weight: 0,
    holdings_count: 0,
    price_available: false,
    holdings: [] as any[],
    rebalance: [] as any[],
  }
}

onMounted(async () => {
  try {
    const { data } = await portfolioApi.getPortfolio()
    if (data) {
      totalCapital.value = data.total_capital || 1000000
      cashBalance.value = data.cash_balance || 0
      holdingsList.splice(0, holdingsList.length, ...(data.holdings || []).map((h: any) => ({
        symbol: h.symbol,
        name: h.name,
        industry: h.industry || '',
        allocation_pct: h.allocation_pct || 0,
        share_count: h.share_count || 0,
        buy_price: h.buy_price || 0,
      })))
    }
  } catch (e) {
    console.warn('加载组合失败，使用默认值', e)
  }
  await fetchSummary()
})

async function fetchSummary() {
  loadingSummary.value = true
  try {
    const { data } = await portfolioApi.getPortfolioSummary()
    if (data) summary.value = data
  } catch (e) {
    console.warn('加载组合概览失败', e)
  } finally {
    loadingSummary.value = false
  }
}

async function savePortfolio() {
  isSaving.value = true
  saveMessage.value = ''
  try {
    // 仅保存有配置（分配>0 或 股数>0）的持仓
    const holdings = holdingsList
      .filter(h => (h.allocation_pct || 0) > 0 || (h.share_count || 0) > 0)
      .map(h => ({
        symbol: h.symbol,
        allocation_pct: h.allocation_pct || 0,
        share_count: h.share_count || 0,
        buy_price: h.buy_price || 0,
      }))

    await portfolioApi.savePortfolio({
      total_capital: totalCapital.value,
      cash_balance: cashBalance.value,
      holdings,
    })

    saveSuccess.value = true
    saveMessage.value = '保存成功'
    await fetchSummary()
  } catch (e) {
    saveSuccess.value = false
    saveMessage.value = '保存失败'
    console.error('保存组合失败', e)
  } finally {
    isSaving.value = false
    setTimeout(() => { saveMessage.value = '' }, 3000)
  }
}

// 手动刷新：先拉实时行情，再算概览（不自动轮询，省 CPU）
async function refresh() {
  try {
    await store.fetchRealtimePrices()
  } catch (e) {
    console.warn('刷新实时行情失败', e)
  }
  await fetchSummary()
}

// 自选（dashboardStocks）中尚未加入持仓的股票
const availableWatchlist = computed(() => {
  const held = new Set(holdingsList.map(h => h.symbol))
  return store.dashboardStocks.filter(s => !held.has(s.stock_symbol) && !s.is_pending)
})

function addHolding(s: any) {
  if (holdingsList.some(h => h.symbol === s.stock_symbol)) return
  holdingsList.push({
    symbol: s.stock_symbol,
    name: s.stock_name,
    industry: s.industry || '',
    allocation_pct: 0,
    share_count: 0,
    buy_price: 0,
  })
}

function addCustomHolding() {
  const symbol = newSymbol.value.trim().toUpperCase()
  const name = newName.value.trim() || symbol
  if (!symbol || holdingsList.some(h => h.symbol === symbol)) return
  holdingsList.push({
    symbol,
    name,
    industry: '',
    allocation_pct: 0,
    share_count: 0,
    buy_price: 0,
  })
  newSymbol.value = ''
  newName.value = ''
  customOpen.value = false
}

function removeHolding(symbol: string) {
  const i = holdingsList.findIndex(h => h.symbol === symbol)
  if (i >= 0) holdingsList.splice(i, 1)
}

const pctTotal = computed(() => holdingsList.reduce((s, h) => s + (h.allocation_pct || 0), 0))

function equalWeight() {
  const n = holdingsList.length
  if (n === 0) return
  const pct = Math.floor(100 / n)
  for (const h of holdingsList) h.allocation_pct = pct
  const remainder = 100 - pct * n
  if (remainder > 0 && holdingsList[0]) holdingsList[0].allocation_pct += remainder
}

// Mode B 实时市值 / 买入成本
function hMarketValue(h: any): number {
  return (h.share_count || 0) * (store.realtimePrices?.[h.symbol]?.price ?? 0)
}
function hBookCost(h: any): number {
  return (h.share_count || 0) * (h.buy_price || 0)
}
const sharesTotalCost = computed(() =>
  holdingsList.reduce((sum, h) => sum + hBookCost(h), 0)
)
const sharesTotalMV = computed(() =>
  holdingsList.reduce((sum, h) => sum + hMarketValue(h), 0)
)

// 年分红（按后端概览的市值×股息率估算）
const annualDividend = computed(() =>
  (summary.value.holdings || []).reduce(
    (s: number, h: any) => s + (h.market_value || 0) * (h.dividend_yield || 0) / 100,
    0,
  )
)

// A 股惯例：涨/盈 红(rose)，跌/亏 绿(emerald)；浅色背景用 600 更清晰
function pnlClass(v: number): string {
  if (v > 0) return 'text-rose-600'
  if (v < 0) return 'text-emerald-600'
  return 'text-slate-500'
}
function driftInfo(d: number): { t: string; c: string } {
  if (d > 0.5) return { t: '超配', c: 'text-rose-600' }
  if (d < -0.5) return { t: '低配', c: 'text-emerald-600' }
  return { t: '持平', c: 'text-slate-500' }
}
const rebalanceList = computed(() =>
  (summary.value.rebalance || []).filter((r: any) => r.action !== 'hold')
)

function fmtMoney(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万'
  return v.toFixed(0)
}
</script>

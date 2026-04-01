<template>
  <div v-if="show" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
    <div class="glass-card w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden border-white/10 shadow-2xl">
      <div class="p-6 border-b border-white/5 flex items-center justify-between">
        <h2 class="text-xl font-bold text-white flex items-center gap-2">
          <svg class="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          管理监控标的
        </h2>
        <button @click="$emit('close')" class="p-2 hover:bg-white/10 rounded-lg transition-colors text-slate-400">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="p-6 bg-white/5 border-b border-white/5">
        <div class="relative mb-4">
          <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">搜索并添加公司</label>
          <div class="flex gap-3">
            <div class="relative flex-1">
              <input
                v-model="searchQuery"
                @input="handleSearch"
                @keyup.enter="handleAdd"
                type="text"
                placeholder="输入公司名称或代码，例如：茅台 / 600519"
                class="w-full bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-cyan-500/50 outline-none transition-all placeholder:text-slate-600"
              />

              <div v-if="suggestions.length > 0" class="absolute left-0 right-0 top-full mt-2 bg-slate-900/95 border border-white/20 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-[110] overflow-hidden backdrop-blur-xl">
                <div
                  v-for="item in suggestions"
                  :key="item.symbol"
                  @click="selectSuggestion(item)"
                  class="px-4 py-3 hover:bg-cyan-500/10 cursor-pointer flex justify-between items-center transition-colors border-b border-white/5 last:border-0"
                >
                  <div class="flex items-center gap-3">
                    <div class="w-8 h-8 bg-slate-800 rounded-lg flex items-center justify-center text-[10px] font-bold text-cyan-400 border border-white/10">
                      {{ item.symbol.substring(2) }}
                    </div>
                    <div class="flex flex-col">
                      <span class="text-sm font-bold text-white">{{ item.name }}</span>
                      <span class="text-[10px] font-mono text-slate-500">{{ item.symbol }}</span>
                    </div>
                  </div>
                  <div class="text-right">
                    <span class="text-xs text-emerald-400 font-bold">￥{{ Number(item.price || 0).toFixed(2) }}</span>
                    <div class="text-[8px] text-slate-600">最新价</div>
                  </div>
                </div>
              </div>

              <div v-else-if="searchLoading" class="absolute left-0 right-0 top-full mt-2 rounded-xl border border-white/10 bg-slate-900/95 px-4 py-3 text-xs text-slate-400">
                搜索中...
              </div>
            </div>

            <button
              @click="handleAdd"
              :disabled="!newStock.symbol || loading"
              class="px-6 bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold text-white shadow-lg shadow-cyan-500/20 transition-all flex items-center justify-center gap-2 whitespace-nowrap"
            >
              <svg v-if="loading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span v-else>确认添加</span>
            </button>
          </div>

          <p v-if="newStock.symbol" class="mt-2 text-[10px] text-cyan-400/70">
            已选中: <span class="font-bold">{{ newStock.name }}</span> ({{ newStock.symbol }})
          </p>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-white/10">
        <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4">当前监控标的 ({{ store.stocks.length }})</h3>
        <div class="space-y-3">
          <div
            v-for="stock in store.stocks"
            :key="stock.id"
            class="group flex items-center justify-between p-4 bg-white/[0.02] border border-white/5 rounded-2xl hover:bg-white/[0.05] hover:border-cyan-500/30 transition-all"
          >
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 bg-slate-800 rounded-xl flex items-center justify-center text-cyan-400 font-bold border border-white/5">
                {{ stock.name.charAt(0) }}
              </div>
              <div>
                <div class="text-sm font-bold text-white">{{ stock.name }}</div>
                <div class="text-[10px] font-mono text-slate-500">{{ stock.symbol }}</div>
              </div>
            </div>
            <button
              @click="handleRemove(stock.symbol)"
              class="p-2 text-slate-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
              title="删除标的"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { stockApi } from '@/api'
import { useSentimentStore } from '@/stores/sentiment'

type StockSearchResult = {
  name: string
  symbol: string
  price: number
}

defineProps<{
  show: boolean
}>()

defineEmits(['close'])

const store = useSentimentStore()
const loading = ref(false)
const searchLoading = ref(false)
const searchQuery = ref('')
const suggestions = ref<StockSearchResult[]>([])

const newStock = reactive({
  name: '',
  symbol: '',
  keywords: [] as string[],
})

onMounted(() => {
  store.fetchStocks()
})

let searchTimer: ReturnType<typeof setTimeout> | null = null

function resetSelection() {
  newStock.name = ''
  newStock.symbol = ''
  newStock.keywords = []
}

async function handleSearch() {
  if (searchTimer) clearTimeout(searchTimer)

  const keyword = searchQuery.value.trim()
  if (!keyword) {
    suggestions.value = []
    searchLoading.value = false
    resetSelection()
    return
  }

  const normalized = keyword.toUpperCase()
  const rawCode = normalized.replace(/^(SH|SZ)/, '')
  if (/^\d{6}$/.test(rawCode)) {
    newStock.symbol = rawCode.startsWith('6') ? `SH${rawCode}` : `SZ${rawCode}`
    if (!newStock.name) {
      newStock.keywords = [rawCode]
    }
  } else {
    newStock.symbol = ''
    newStock.keywords = []
  }

  searchLoading.value = true
  searchTimer = setTimeout(async () => {
    try {
      const res = await stockApi.searchStocks(keyword)
      suggestions.value = Array.isArray(res.data) ? res.data : []
    } catch (error) {
      console.error('Search failed:', error)
      suggestions.value = []
    } finally {
      searchLoading.value = false
    }
  }, 250)
}

function selectSuggestion(item: StockSearchResult) {
  newStock.name = item.name
  newStock.symbol = item.symbol
  newStock.keywords = [item.name]
  searchQuery.value = `${item.name} (${item.symbol})`
  suggestions.value = []
}

async function handleAdd() {
  if (!newStock.symbol) return

  if (!newStock.name) {
    newStock.keywords = newStock.keywords.length > 0 ? newStock.keywords : [newStock.symbol.slice(2)]
  }

  const exists = store.stocks.find((item) => item.symbol === newStock.symbol)
  if (exists) {
    alert(`标的 ${newStock.name} (${newStock.symbol}) 已在监控列表中。`)
    return
  }

  loading.value = true
  try {
    const success = await store.addStock({ ...newStock })
    if (!success) return

    resetSelection()
    searchQuery.value = ''
    suggestions.value = []

    await Promise.all([
      store.fetchLatestSentiment(),
      store.fetchRealtimePrices(),
    ])
  } catch (error) {
    console.error('Add stock failed:', error)
  } finally {
    loading.value = false
  }
}

async function handleRemove(symbol: string) {
  if (!confirm(`确定要停止监控 ${symbol} 吗？相关采集数据将不再显示。`)) return

  const success = await store.removeStock(symbol)
  if (success) {
    await store.fetchLatestSentiment()
  }
}
</script>

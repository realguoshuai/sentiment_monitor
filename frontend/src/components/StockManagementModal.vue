<template>
  <div v-if="show" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
    <div class="glass-card w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden border-white/10 shadow-2xl">
      <!-- Header -->
      <div class="p-6 border-b border-white/5 flex items-center justify-between">
        <h2 class="text-xl font-bold text-white flex items-center gap-2">
          <svg class="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
          管理监控标的
        </h2>
        <button @click="$emit('close')" class="p-2 hover:bg-white/10 rounded-lg transition-colors text-slate-400">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Add Form -->
      <div class="p-6 bg-white/5 border-b border-white/5">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">股票名称</label>
            <input 
              v-model="newStock.name" 
              type="text" 
              placeholder="例如：贵州茅台"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-cyan-500/50 outline-none transition-all placeholder:text-slate-600"
            >
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">股票代码</label>
            <input 
              v-model="newStock.symbol" 
              type="text" 
              placeholder="例如：SH600519"
              class="w-full bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-white focus:border-cyan-500/50 outline-none transition-all placeholder:text-slate-600 font-mono"
            >
          </div>
        </div>
        <button 
          @click="handleAdd" 
          :disabled="!newStock.name || !newStock.symbol || loading"
          class="w-full py-3 bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold text-white shadow-lg shadow-cyan-500/20 transition-all flex items-center justify-center gap-2"
        >
          <svg v-if="loading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
          </svg>
          <span v-else>确认添加</span>
        </button>
      </div>

      <!-- List -->
      <div class="flex-1 overflow-y-auto p-6">
        <div class="space-y-3">
          <div 
            v-for="stock in store.stocks" 
            :key="stock.id"
            class="group flex items-center justify-between p-4 glass bg-white/5 border border-white/5 rounded-2xl hover:border-cyan-500/30 transition-all"
          >
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 bg-slate-800 rounded-xl flex items-center justify-center text-cyan-400 font-bold">
                {{ stock.name.charAt(0) }}
              </div>
              <div>
                <div class="text-sm font-bold text-white">{{ stock.name }}</div>
                <div class="text-xs font-mono text-slate-500">{{ stock.symbol }}</div>
              </div>
            </div>
            <button 
              @click="handleRemove(stock.symbol)" 
              class="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
              title="删除"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'

defineProps<{
  show: boolean
}>()

const emit = defineEmits(['close'])
const store = useSentimentStore()
const loading = ref(false)

const newStock = reactive({
  name: '',
  symbol: '',
  keywords: []
})

async function handleAdd() {
  loading.value = true
  // 处理代码格式，确保大写
  newStock.symbol = newStock.symbol.toUpperCase()
  const success = await store.addStock({...newStock})
  loading.value = false
  if (success) {
    newStock.name = ''
    newStock.symbol = ''
  }
}

async function handleRemove(symbol: string) {
  if (confirm(`确定要停止监控 ${symbol} 吗？相关历史数据将不再显示。`)) {
    await store.removeStock(symbol)
  }
}
</script>

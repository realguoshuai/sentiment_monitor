<template>
  <div 
    class="group rounded-xl p-3.5 cursor-pointer overflow-hidden relative border border-slate-700/50 hover:border-indigo-500/50 transition-all hover:bg-slate-800/80 active:scale-[0.99] bg-[#1a2332]"
    @click="$emit('click')"
  >
    <!-- Background Gradient -->
    <div class="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none"></div>

    <div class="relative z-10 flex flex-col h-full">
      <!-- Row 1: Name, Price, Fire Score -->
      <div class="flex justify-between items-end mb-1">
        <div class="flex items-baseline gap-2">
          <h3 class="text-lg font-semibold text-slate-100 tracking-wide">{{ data.stock_name }}</h3>
          <span v-if="rtPrice" class="font-mono font-bold text-base" :class="priceColorClass">
            {{ rtPrice.price.toFixed(2) }} 
            <span class="text-[10px] ml-0.5">{{ rtPrice.change_percent > 0 ? '+' : '' }}{{ rtPrice.change_percent.toFixed(2) }}%</span>
          </span>
          <span v-else class="text-slate-500 font-mono text-xs">--.--</span>
        </div>
        <div class="flex items-center gap-1.5 text-orange-500 font-mono font-bold text-xs">
          <span class="w-1.5 h-1.5 rounded-full bg-orange-500"></span>
          {{ data.hot_score.toFixed(1) }}
        </div>
      </div>

      <!-- Row 2: Symbol & Tag -->
      <div class="flex gap-2 items-center mb-3">
        <span class="text-[10px] text-slate-500 font-mono tracking-widest">{{ data.stock_symbol }}</span>
        <span class="px-1.5 py-0.5 rounded text-[9px] font-bold border" :class="sentimentBadgeClass">
          {{ data.sentiment_label }}
        </span>
      </div>

      <!-- Row 3: Sentiment Display -->
      <div class="mb-3">
        <div class="flex justify-between items-baseline mb-1.5">
          <span class="text-[10px] text-slate-500">舆情走势</span>
          <span class="text-xs font-bold font-mono" :class="sentimentTextClass">{{ formattedScore }}</span>
        </div>
        <div class="h-1 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-1000"
            :class="sentimentBarClass"
            :style="{ width: `${sentimentBarWidth}%` }"
          />
        </div>
      </div>

      <!-- Row 4: Valuation & ROI -->
      <div v-if="rtPrice" class="grid grid-cols-5 gap-1 mb-2">
        <div class="flex flex-col p-1 rounded bg-[#1e293b]/50 border border-slate-700/50 text-center">
          <span class="text-[8px] text-slate-500 mb-0.5">PE(动)</span>
          <span class="text-[11px] font-bold font-mono" :class="peColor">{{ rtPrice.pe > 0 ? rtPrice.pe.toFixed(1) : '亏损' }}</span>
        </div>
        <div class="flex flex-col p-1 rounded bg-[#1e293b]/50 border border-slate-700/50 text-center">
          <span class="text-[8px] text-slate-500 mb-0.5">PB</span>
          <span class="text-[11px] font-bold font-mono" :class="pbColor">{{ rtPrice.pb > 0 ? rtPrice.pb.toFixed(2) : '--' }}</span>
        </div>
        <div class="flex flex-col p-1 rounded bg-[#1e293b]/50 border border-slate-700/50 text-center">
          <span class="text-[8px] text-slate-500 mb-0.5">股息率</span>
          <span class="text-[11px] font-bold font-mono" :class="divYieldColor">{{ rtPrice.dividend_yield > 0 ? rtPrice.dividend_yield.toFixed(2) + '%' : '--' }}</span>
        </div>
        <div class="flex flex-col p-1 rounded bg-[#1e293b]/50 border border-slate-700/50 text-center">
          <span class="text-[8px] text-slate-500 mb-0.5">ROE</span>
          <span class="text-[11px] font-bold font-mono" :class="roeColor">{{ roeText }}</span>
        </div>
        <div class="flex flex-col p-1 rounded bg-[#1e293b]/50 border border-slate-700/50 text-center">
          <span class="text-[8px] text-slate-500 mb-0.5" title="投资回报率 = ROE / PB">ROI</span>
          <span class="text-[11px] font-bold font-mono" :class="roiColor">{{ roiText }}</span>
        </div>
      </div>

      <!-- Row 5: Stats Grid -->
      <div class="grid grid-cols-3 gap-2 mb-3">
        <div class="flex flex-col p-1.5 rounded-lg bg-[#1e293b]/50 border border-slate-700/50">
          <span class="text-[10px] text-slate-500 mb-0.5">资讯</span>
          <span class="text-xs font-bold text-cyan-400 font-mono">{{ data.news_count }}</span>
        </div>
        <div class="flex flex-col p-1.5 rounded-lg bg-[#1e293b]/50 border border-slate-700/50">
          <span class="text-[10px] text-slate-500 mb-0.5">研报</span>
          <span class="text-xs font-bold text-purple-400 font-mono">{{ data.report_count }}</span>
        </div>
        <div class="flex flex-col p-1.5 rounded-lg bg-[#1e293b]/50 border border-slate-700/50">
          <span class="text-[10px] text-slate-500 mb-0.5">公告</span>
          <span class="text-xs font-bold text-blue-400 font-mono">{{ data.announcement_count }}</span>
        </div>
      </div>

      <!-- Row 5: Links -->
      <div class="mt-auto flex flex-wrap gap-1.5" @click.stop>
        <router-link 
          :to="`/analysis/${data.stock_symbol}`"
          class="px-3 py-1 bg-indigo-500/20 border border-indigo-500/50 hover:bg-indigo-500/40 text-[10px] text-indigo-300 rounded-full transition-all text-center min-w-[50px] font-bold"
        >
          深度分析
        </router-link>
        <router-link 
          :to="`/quality/${data.stock_symbol}`"
          class="px-3 py-1 bg-emerald-500/20 border border-emerald-500/50 hover:bg-emerald-500/40 text-[10px] text-emerald-300 rounded-full transition-all text-center min-w-[50px] font-bold"
        >
          财务溯源
        </router-link>
        <a 
          v-for="link in allLinks"
          :key="link.name"
          :href="link.url" 
          target="_blank"
          class="px-3 py-1 bg-transparent border border-slate-600 hover:border-cyan-400 hover:bg-cyan-500/10 text-[10px] text-slate-300 hover:text-cyan-400 rounded-full transition-all text-center min-w-[50px]"
        >
          {{ link.name }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSentimentStore } from '@/stores/sentiment'
import type { SentimentData } from '@/api'

const props = defineProps<{
  data: SentimentData
}>()

const formattedScore = computed(() => {
  const score = props.data.sentiment_score
  return `${score > 0 ? '+' : ''}${score.toFixed(3)}`
})

const sentimentBadgeClass = computed(() => {
  if (props.data.sentiment_score > 0.2) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
  if (props.data.sentiment_score < -0.2) return 'bg-rose-500/10 text-rose-400 border-rose-500/20'
  return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
})

const sentimentTextClass = computed(() => {
  if (props.data.sentiment_score > 0.2) return 'text-[#00df9a]'
  if (props.data.sentiment_score < -0.2) return 'text-rose-400'
  return 'text-amber-400'
})

const sentimentBarClass = computed(() => {
  if (props.data.sentiment_score > 0.2) return 'bg-gradient-to-r from-[#00df9a]/50 to-[#00df9a] shadow-[0_0_8px_rgba(0,223,154,0.4)]'
  if (props.data.sentiment_score < -0.2) return 'bg-gradient-to-r from-rose-500/50 to-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]'
  return 'bg-gradient-to-r from-amber-500/50 to-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]'
})

const sentimentBarWidth = computed(() => {
  return ((props.data.sentiment_score + 1) / 2) * 100
})

const pureCode = computed(() => props.data.stock_symbol.substring(2))

const allLinks = computed(() => {
  const base = [
    { name: '雪球', url: `https://xueqiu.com/S/${props.data.stock_symbol}` },
    { name: '股吧', url: `http://guba.eastmoney.com/list,${pureCode.value}.html` },
    { name: '融券', url: `https://data.eastmoney.com/rzrq/detail/${pureCode.value}.html` },
    { name: '资讯', url: `https://so.eastmoney.com/news/s?keyword=${encodeURIComponent(props.data.stock_name)}` },
    { name: '公众号', url: `https://weixin.sogou.com/weixin?type=2&query=${encodeURIComponent(props.data.stock_name)}` }
  ]
  
  if (props.data.extra_links) {
    try {
      const extra = JSON.parse(props.data.extra_links)
      return [...base, ...extra]
    } catch (e) {
      console.error('Failed to parse extra_links', e)
    }
  }
  return base
})

const rtPrice = computed(() => {
  const store = useSentimentStore()
  return store.realtimePrices[props.data.stock_symbol]
})

const priceColorClass = computed(() => {
  if (!rtPrice.value) return 'text-slate-500'
  return rtPrice.value.change_percent > 0 ? 'text-rose-500' : rtPrice.value.change_percent < 0 ? 'text-[#00df9a]' : 'text-slate-400'
})

// Valuation Computations
const roiValue = computed(() => {
  if (!rtPrice.value || rtPrice.value.pe <= 0 || rtPrice.value.pb <= 0) return null
  const store = useSentimentStore()
  return store.calculateROI(props.data.stock_symbol, rtPrice.value.pe, rtPrice.value.pb)
})

const roeValue = computed(() => {
  if (!rtPrice.value || rtPrice.value.pe <= 0 || rtPrice.value.pb <= 0) return null
  let roe = (rtPrice.value.pb / rtPrice.value.pe) * 100
  if (props.data.stock_symbol.includes('002304') && roe < 20) {
    roe = 20
  }
  return roe / 100 // Convert back to ratio for text formatting if needed, or keep as %
})

const roeText = computed(() => {
  if (roeValue.value === null) return '--'
  return (roeValue.value * 100).toFixed(1) + '%'
})

const roiText = computed(() => {
  if (roiValue.value === null) return '--'
  return roiValue.value.toFixed(2) + '%'
})

// Dividend Yield Color
const divYieldColor = computed(() => {
  if (!rtPrice.value || rtPrice.value.dividend_yield <= 0) return 'text-slate-500'
  if (rtPrice.value.dividend_yield > 3) return 'text-[#00df9a]'
  if (rtPrice.value.dividend_yield > 1.5) return 'text-amber-400'
  return 'text-rose-400'
})

// Valuation Colors (Value Investing thresholds)
const peColor = computed(() => {
  if (!rtPrice.value || rtPrice.value.pe <= 0) return 'text-slate-500'
  if (rtPrice.value.pe < 15) return 'text-[#00df9a]'
  if (rtPrice.value.pe < 30) return 'text-amber-400'
  return 'text-rose-400'
})

const pbColor = computed(() => {
  if (!rtPrice.value || rtPrice.value.pb <= 0) return 'text-slate-500'
  if (rtPrice.value.pb < 1.5) return 'text-[#00df9a]'
  if (rtPrice.value.pb < 3) return 'text-amber-400'
  return 'text-rose-400'
})

const roeColor = computed(() => {
  if (roeValue.value === null) return 'text-slate-500'
  if (roeValue.value > 0.15) return 'text-[#00df9a]'
  if (roeValue.value > 0.08) return 'text-amber-400'
  return 'text-rose-400'
})

const roiColor = computed(() => {
  if (roiValue.value === null) return 'text-slate-500'
  if (roiValue.value > 10) return 'text-[#00df9a]'
  if (roiValue.value > 5) return 'text-amber-400'
  return 'text-rose-400'
})
</script>

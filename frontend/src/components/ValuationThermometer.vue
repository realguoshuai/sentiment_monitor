<template>
  <div class="flex flex-col h-full">
    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex flex-col items-center justify-center gap-2">
      <div class="w-6 h-6 border-2 border-slate-700 border-t-cyan-400 rounded-full animate-spin"></div>
      <span class="text-[10px] text-slate-500">正在计算十年 PB 水位...</span>
    </div>

    <div v-else-if="error" class="flex-1 flex items-center justify-center text-xs text-slate-500">
      {{ error }}
    </div>

    <div v-else-if="!stocks.length" class="flex-1 flex items-center justify-center text-xs text-slate-500">
      暂无监控股票
    </div>

    <!-- Card Grid -->
    <div v-else class="flex-1 overflow-y-auto custom-scrollbar pr-1">
      <div class="grid grid-cols-2 xl:grid-cols-3 gap-2">
        <div
          v-for="s in stocks"
          :key="s.symbol"
          class="bg-slate-800/60 rounded-lg p-2.5 border border-slate-700/50 hover:border-slate-500/50 transition-colors"
        >
          <!-- Header: Name + PB -->
          <div class="flex items-baseline justify-between mb-1.5">
            <span class="text-[11px] font-bold text-slate-200 truncate">{{ s.name }}</span>
            <span class="text-[10px] text-slate-400 ml-1">PB {{ s.current_pb }}</span>
          </div>

          <!-- Gauge Ring -->
          <div class="flex items-center gap-2.5">
            <div class="relative w-10 h-10 shrink-0">
              <svg viewBox="0 0 36 36" class="w-full h-full -rotate-90">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1e293b" stroke-width="3.5" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none"
                  :stroke="ringColor(s.percentile)"
                  stroke-width="3.5"
                  stroke-linecap="round"
                  :stroke-dasharray="`${s.percentile * 0.974} 97.4`"
                  class="transition-all duration-700"
                  :style="{ filter: `drop-shadow(0 0 3px ${ringColor(s.percentile)}60)` }"
                />
              </svg>
              <div class="absolute inset-0 flex items-center justify-center">
                <span class="text-[10px] font-black" :style="{ color: ringColor(s.percentile) }">
                  {{ s.percentile }}
                </span>
              </div>
            </div>

            <!-- 区间条 -->
            <div class="flex-1 min-w-0">
              <div class="flex justify-between text-[8px] text-slate-400 mb-0.5">
                <span>{{ s.pb_min }}</span>
                <span>{{ s.pb_max }}</span>
              </div>
              <div class="h-3 bg-slate-900 rounded-full relative overflow-hidden">
                <!-- P10-P90 区间 -->
                <div
                  class="absolute top-0 bottom-0 bg-slate-600/60 rounded-full"
                  :style="{ left: p10Pos(s) + '%', width: (p90Pos(s) - p10Pos(s)) + '%' }"
                ></div>
                <!-- P25-P75 区间 -->
                <div
                  class="absolute top-0 bottom-0 bg-slate-500/50 rounded-full"
                  :style="{ left: p25Pos(s) + '%', width: (p75Pos(s) - p25Pos(s)) + '%' }"
                ></div>
                <!-- 当前位置 -->
                <div
                  class="absolute top-0 bottom-0 w-1.5 rounded-full transition-all duration-500"
                  :style="{
                    left: `calc(${currentPos(s)}% - 3px)`,
                    background: ringColor(s.percentile),
                    boxShadow: `0 0 6px ${ringColor(s.percentile)}80`
                  }"
                ></div>
              </div>
              <div class="flex justify-between text-[8px] text-slate-500 mt-0.5">
                <span>低估 {{ s.p10 }}</span>
                <span class="text-slate-400">中位 {{ s.p50 }}</span>
                <span>高估 {{ s.p90 }}</span>
              </div>
            </div>
          </div>

          <!-- Label -->
          <div class="mt-1.5 text-center">
            <span
              class="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
              :style="{ color: ringColor(s.percentile), background: ringBg(s.percentile) }"
            >
              {{ waterLabel(s.percentile) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { stockApi } from '@/api'

interface StockWaterLevel {
  symbol: string; name: string; percentile: number; current_pb: number
  p10: number; p25: number; p50: number; p75: number; p90: number
  pb_min: number; pb_max: number; data_points: number
}

const loading = ref(true)
const error = ref('')
const stocks = ref<StockWaterLevel[]>([])

function ringColor(pct: number): string {
  if (pct <= 10) return '#22d3ee'   // bright cyan
  if (pct <= 25) return '#67e8f9'   // light cyan
  if (pct <= 50) return '#4ade80'   // bright green
  if (pct <= 75) return '#facc15'   // bright yellow
  if (pct <= 90) return '#fb923c'   // bright orange
  return '#f87171'                   // bright red
}

function ringBg(pct: number): string {
  if (pct <= 25) return 'rgba(34,211,238,0.18)'
  if (pct <= 50) return 'rgba(74,222,128,0.18)'
  if (pct <= 75) return 'rgba(250,204,21,0.18)'
  return 'rgba(248,113,113,0.18)'
}

function waterLabel(pct: number): string {
  if (pct <= 10) return '极度低估'
  if (pct <= 25) return '低估区间'
  if (pct <= 50) return '合理偏低'
  if (pct <= 75) return '合理偏高'
  if (pct <= 90) return '高估区间'
  return '极度高估'
}

// 将 PB 值映射到 0-100% 的位置
function pbToPos(val: number, s: StockWaterLevel): number {
  if (s.pb_max <= s.pb_min) return 50
  return Math.max(0, Math.min(100, ((val - s.pb_min) / (s.pb_max - s.pb_min)) * 100))
}
function currentPos(s: StockWaterLevel) { return pbToPos(s.current_pb, s) }
function p10Pos(s: StockWaterLevel) { return pbToPos(s.p10, s) }
function p25Pos(s: StockWaterLevel) { return pbToPos(s.p25, s) }
function p75Pos(s: StockWaterLevel) { return pbToPos(s.p75, s) }
function p90Pos(s: StockWaterLevel) { return pbToPos(s.p90, s) }

async function loadData() {
  loading.value = true; error.value = ''
  try {
    const res = await stockApi.getValuationThermometer()
    stocks.value = res.data?.stocks || []
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally { loading.value = false }
}

onMounted(() => { loadData() })
</script>

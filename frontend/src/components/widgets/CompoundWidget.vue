<template>
  <div class="space-y-3">
    <div class="grid grid-cols-2 gap-2">
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">初始资金</label>
        <input v-model.number="initial" type="number" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">年化收益率 %</label>
        <input v-model.number="annualReturn" type="number" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">每月追加</label>
        <input v-model.number="monthly" type="number" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
      <div>
        <label class="mb-1 block text-[10px] font-bold text-slate-500">年限</label>
        <input v-model.number="years" type="number" min="1" max="50" class="w-full rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-1.5 text-xs font-mono text-cyan-400 outline-none focus:border-cyan-500" />
      </div>
    </div>

    <label class="flex items-center gap-2 text-[10px] text-slate-400">
      <input v-model="reinvest" type="checkbox" class="h-3.5 w-3.5 rounded border-slate-600 bg-slate-900 text-cyan-400" />
      分红再投资（复利）
    </label>

    <!-- Summary -->
    <div class="grid grid-cols-2 gap-2 rounded-lg border border-slate-700/50 bg-slate-900/30 p-3">
      <div>
        <div class="text-[10px] text-slate-500">总投入</div>
        <div class="text-sm font-mono font-bold text-slate-200">{{ fmt(totalInvested) }}</div>
      </div>
      <div>
        <div class="text-[10px] text-slate-500">终值</div>
        <div class="text-sm font-mono font-bold text-emerald-400">{{ fmt(finalValue) }}</div>
      </div>
      <div>
        <div class="text-[10px] text-slate-500">总收益</div>
        <div class="text-sm font-mono font-bold" :class="gain >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ fmt(gain) }}</div>
      </div>
      <div>
        <div class="text-[10px] text-slate-500">收益率</div>
        <div class="text-sm font-mono font-bold" :class="gainPct >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ gainPct.toFixed(1) }}%</div>
      </div>
    </div>

    <!-- Year-by-year mini table -->
    <div class="max-h-[180px] overflow-y-auto">
      <table class="w-full text-[10px]">
        <thead>
          <tr class="text-slate-500">
            <th class="text-left py-1">年</th>
            <th class="text-right py-1">投入</th>
            <th class="text-right py-1">终值</th>
            <th class="text-right py-1">收益</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in table" :key="row.year" class="border-t border-slate-800">
            <td class="py-1 text-slate-400">第{{ row.year }}年</td>
            <td class="py-1 text-right font-mono text-slate-300">{{ fmt(row.invested) }}</td>
            <td class="py-1 text-right font-mono text-cyan-400">{{ fmt(row.value) }}</td>
            <td class="py-1 text-right font-mono" :class="row.gain >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{ fmt(row.gain) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const initial = ref(100000)
const annualReturn = ref(8)
const monthly = ref(5000)
const years = ref(20)
const reinvest = ref(true)

const table = computed(() => {
  const r = annualReturn.value / 100
  const rows = []
  let value = initial.value
  let totalIn = initial.value

  for (let y = 1; y <= years.value; y++) {
    const contributions = monthly.value * 12
    totalIn += contributions
    if (reinvest.value) {
      value = (value + contributions) * (1 + r)
    } else {
      value = value * (1 + r) + contributions
    }
    rows.push({ year: y, invested: totalIn, value: Math.round(value), gain: Math.round(value - totalIn) })
  }
  return rows
})

const totalInvested = computed(() => initial.value + monthly.value * 12 * years.value)
const finalValue = computed(() => table.value.length > 0 ? table.value[table.value.length - 1].value : initial.value)
const gain = computed(() => finalValue.value - totalInvested.value)
const gainPct = computed(() => totalInvested.value > 0 ? (gain.value / totalInvested.value) * 100 : 0)

function fmt(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}
</script>

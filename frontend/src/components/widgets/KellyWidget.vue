<template>
  <div class="space-y-3">
    <!-- 顶部说明区 -->
    <button
      class="flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left transition-all"
      :class="showHelp
        ? 'border-teal-400/40 bg-teal-500/10'
        : 'border-slate-200 bg-slate-50/80 hover:border-slate-300'"
      @click="showHelp = !showHelp"
    >
      <span class="text-base">{{ showHelp ? '📖' : '💡' }}</span>
      <span class="flex-1 text-[11px] font-bold" :class="showHelp ? 'text-teal-600' : 'text-slate-500'">
        {{ showHelp ? '收起说明' : '什么是凯利公式？点击展开' }}
      </span>
      <span class="text-[10px] text-slate-400 transition-transform" :class="showHelp ? 'rotate-180' : ''">▼</span>
    </button>

    <Transition name="expand">
      <div v-if="showHelp" class="space-y-2 overflow-hidden">
        <!-- 三步理解 -->
        <div class="rounded-lg border border-teal-200 bg-teal-50/50 p-3 space-y-2">
          <div class="flex items-start gap-2">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-500 text-[10px] font-black text-white">1</span>
            <div>
              <div class="text-[11px] font-bold text-teal-700">核心问题：每次下注多少钱？</div>
              <div class="text-[10px] text-teal-600 leading-relaxed">
                假设你有一个"赢面大于输面"的机会，凯利公式告诉你<strong>每次应该投入总资金的多大比例</strong>，才能让长期收益最大化。
              </div>
            </div>
          </div>
          <div class="flex items-start gap-2">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-500 text-[10px] font-black text-white">2</span>
            <div>
              <div class="text-[11px] font-bold text-teal-700">两个关键输入</div>
              <div class="text-[10px] text-teal-600 leading-relaxed">
                <strong>胜率 W</strong>：你判断这笔交易盈利的概率<br/>
                <strong>盈亏比 R</strong>：赚的时候平均赚多少 ÷ 亏的时候平均亏多少
              </div>
            </div>
          </div>
          <div class="flex items-start gap-2">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-500 text-[10px] font-black text-white">3</span>
            <div>
              <div class="text-[11px] font-bold text-teal-700">公式</div>
              <div class="mt-1 rounded-md bg-white border border-teal-200 px-3 py-2 font-mono text-xs text-center text-teal-700">
                f* = W − (1−W) / R
              </div>
              <div class="mt-1.5 text-[10px] text-teal-600 leading-relaxed">
                <strong>举例</strong>：胜率 60%，盈亏比 2:1 → f* = 0.6 − 0.4/2 = <strong>40%</strong><br/>
                意思是每次应该拿总资金的 40% 去下注。
              </div>
            </div>
          </div>
        </div>

        <!-- 为什么不用全凯利 -->
        <div class="rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2">
          <div class="text-[10px] text-amber-700 leading-relaxed">
            ⚠️ <strong>实战中几乎没人用全凯利</strong>——波动太大，连亏几把心态就崩了。<br/>
            一般用<strong>半凯利（f*/2）</strong>或<strong>1/4 凯利（f*/4）</strong>，牺牲一点收益换更平稳的曲线。
          </div>
        </div>
      </div>
    </Transition>

    <!-- 输入区 -->
    <div class="grid grid-cols-2 gap-2">
      <div>
        <label class="mb-1 flex items-center gap-1">
          <span class="text-[10px] font-bold text-slate-500">胜率</span>
          <span class="text-[9px] text-slate-400">你判断盈利的概率</span>
        </label>
        <div class="relative">
          <input
            v-model.number="winRate"
            type="number"
            min="1"
            max="99"
            step="1"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 pr-8 text-xs font-mono text-cyan-600 outline-none focus:border-cyan-400"
          />
          <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">%</span>
        </div>
      </div>
      <div>
        <label class="mb-1 flex items-center gap-1">
          <span class="text-[10px] font-bold text-slate-500">盈亏比</span>
          <span class="text-[9px] text-slate-400">赚/亏的倍数</span>
        </label>
        <div class="relative">
          <input
            v-model.number="winLossRatio"
            type="number"
            min="0.1"
            step="0.1"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 pr-10 text-xs font-mono text-cyan-600 outline-none focus:border-cyan-400"
          />
          <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">: 1</span>
        </div>
      </div>
    </div>

    <div>
      <label class="mb-1 flex items-center gap-1">
        <span class="text-[10px] font-bold text-slate-500">总资金</span>
        <span class="text-[9px] text-slate-400">用于计算具体金额</span>
      </label>
      <input
        v-model.number="bankroll"
        type="number"
        min="0"
        step="10000"
        class="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-mono text-cyan-600 outline-none focus:border-cyan-400"
      />
    </div>

    <!-- 快捷盈亏比 -->
    <div class="flex flex-wrap gap-1">
      <span class="text-[10px] text-slate-400 mr-1 leading-5">常用：</span>
      <button
        v-for="r in presetRatios"
        :key="r"
        class="rounded-md border px-2 py-0.5 text-[10px] font-bold transition-all"
        :class="winLossRatio === r
          ? 'border-teal-400 bg-teal-500/20 text-teal-300'
          : 'border-slate-600 text-slate-400 hover:border-slate-500 hover:text-slate-300'"
        @click="winLossRatio = r"
      >
        {{ r }}:1
      </button>
    </div>

    <!-- 结果 -->
    <div v-if="isValid" class="rounded-lg border border-slate-200 bg-slate-50/80 p-3 space-y-3">
      <!-- 公式代入 -->
      <div class="rounded-md bg-white border border-slate-200 px-3 py-2">
        <div class="text-[10px] text-slate-400 mb-1">代入公式</div>
        <div class="font-mono text-xs text-slate-600">
          f* = {{ (winRate/100).toFixed(2) }} − {{ (1 - winRate/100).toFixed(2) }} ÷ {{ winLossRatio.toFixed(1) }}
          <span class="text-teal-600 font-bold">= {{ (fullKelly * 100).toFixed(1) }}%</span>
        </div>
      </div>

      <!-- 三档凯利 - 条形图 -->
      <div>
        <div class="text-[10px] font-bold text-slate-500 mb-2">建议仓位比例</div>
        <div class="space-y-2">
          <div v-for="item in kellyBars" :key="item.label" class="flex items-center gap-2">
            <div class="w-14 text-right">
              <div class="text-[10px] font-bold" :class="item.labelColor">{{ item.label }}</div>
            </div>
            <div class="flex-1 h-5 rounded-full bg-slate-100 overflow-hidden relative">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="item.barColor"
                :style="{ width: Math.min(100, item.pct / maxBarPct * 100) + '%' }"
              />
              <span class="absolute inset-0 flex items-center pl-2 text-[10px] font-mono font-bold" :class="item.textColor">
                {{ item.pct.toFixed(1) }}%
              </span>
            </div>
            <div v-if="bankroll > 0" class="w-16 text-right">
              <div class="text-[10px] font-mono font-bold" :class="item.amountColor">
                {{ formatMoney(bankroll * item.value) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 辅助指标 -->
      <div class="border-t border-slate-200 pt-2">
        <div class="grid grid-cols-3 gap-2">
          <div class="text-center">
            <div class="text-[10px] text-slate-500">期望值</div>
            <div class="text-sm font-mono font-bold" :class="ev >= 0 ? 'text-emerald-600' : 'text-rose-500'">
              {{ ev >= 0 ? '+' : '' }}{{ (ev * 100).toFixed(1) }}%
            </div>
            <div class="text-[9px] text-slate-400 mt-0.5">
              {{ ev > 0 ? '正期望 ✓' : ev === 0 ? '零和' : '负期望 ✗' }}
            </div>
          </div>
          <div class="text-center">
            <div class="text-[10px] text-slate-500">期望盈亏比</div>
            <div class="text-sm font-mono font-bold text-slate-700">
              {{ edgeRatio.toFixed(2) }}
            </div>
            <div class="text-[9px] text-slate-400 mt-0.5">
              {{ edgeRatio > 1 ? '大于1才有优势' : '无优势' }}
            </div>
          </div>
          <div class="text-center">
            <div class="text-[10px] text-slate-500">破产概率</div>
            <div class="text-sm font-mono font-bold" :class="ruinProb > 0.5 ? 'text-rose-500' : ruinProb > 0.2 ? 'text-amber-500' : 'text-emerald-600'">
              {{ (ruinProb * 100).toFixed(1) }}%
            </div>
            <div class="text-[9px] text-slate-400 mt-0.5">
              半凯利下更低
            </div>
          </div>
        </div>
      </div>

      <!-- 实战建议 -->
      <div class="rounded-md border px-2.5 py-2" :class="adviceBoxClass">
        <div class="text-[10px] leading-relaxed" :class="adviceTextClass">
          <span class="font-bold">{{ adviceIcon }} </span>{{ advice }}
        </div>
      </div>
    </div>

    <!-- 无效输入 -->
    <div v-else class="rounded-lg border border-slate-200 bg-slate-50/80 p-4">
      <div class="text-center text-[11px] text-slate-400">
        <div class="text-lg mb-1">📊</div>
        输入胜率和盈亏比，计算最优下注比例
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const showHelp = ref(false)
const winRate = ref(55)
const winLossRatio = ref(2)
const bankroll = ref(100000)

const presetRatios = [1, 1.5, 2, 3, 5]

const isValid = computed(() => {
  const w = winRate.value
  const r = winLossRatio.value
  return w > 0 && w < 100 && r > 0
})

// 凯利公式: f* = W - (1-W)/R
const fullKelly = computed(() => {
  const w = winRate.value / 100
  const r = winLossRatio.value
  return Math.max(0, w - (1 - w) / r)
})

const halfKelly = computed(() => fullKelly.value / 2)
const quarterKelly = computed(() => fullKelly.value / 4)

// 条形图数据
const kellyBars = computed(() => [
  {
    label: '全凯利',
    value: fullKelly.value,
    pct: fullKelly.value * 100,
    barColor: 'bg-rose-400',
    labelColor: 'text-rose-500',
    textColor: 'text-rose-700',
    amountColor: 'text-rose-500',
  },
  {
    label: '半凯利',
    value: halfKelly.value,
    pct: halfKelly.value * 100,
    barColor: 'bg-teal-400',
    labelColor: 'text-teal-600',
    textColor: 'text-teal-700',
    amountColor: 'text-teal-600',
  },
  {
    label: '1/4凯利',
    value: quarterKelly.value,
    pct: quarterKelly.value * 100,
    barColor: 'bg-emerald-400',
    labelColor: 'text-emerald-600',
    textColor: 'text-emerald-700',
    amountColor: 'text-emerald-600',
  },
])

const maxBarPct = computed(() => Math.max(fullKelly.value * 100, 1))

// 期望值: E = W * R - (1-W)
const ev = computed(() => {
  const w = winRate.value / 100
  const r = winLossRatio.value
  return w * r - (1 - w)
})

// 期望盈亏比
const edgeRatio = computed(() => {
  const w = winRate.value / 100
  const r = winLossRatio.value
  return w * r / (1 - w)
})

// 破产概率近似
const ruinProb = computed(() => {
  const w = winRate.value / 100
  const f = fullKelly.value
  if (f <= 0) return 1
  if (ev.value <= 0) return 0.95
  const ratio = (1 - w) / w
  const ruin = Math.pow(ratio, Math.min(50, 1 / f))
  return Math.min(0.99, ruin)
})

const advice = computed(() => {
  const f = fullKelly.value
  const e = ev.value
  if (e <= 0) return '期望值为负，凯利公式告诉你：不该出手。再好的"感觉"也抵不过负期望。'
  if (f >= 0.4) return '信号极强！但全凯利波动巨大，建议用半凯利甚至更低，保命第一。'
  if (f >= 0.2) return '信号较强，半凯利是比较稳健的选择，兼顾收益和回撤。'
  if (f >= 0.1) return '信号适中，建议半凯利。如果你对胜率没把握，用 1/4 凯利更安全。'
  if (f >= 0.05) return '信号偏弱，1/4 凯利更稳妥。或者等更好的机会。'
  return '信号很弱，凯利公式建议极小仓位。不妨观望，等赢面更大再出手。'
})

const adviceIcon = computed(() => {
  const e = ev.value
  if (e <= 0) return '🚫'
  if (fullKelly.value >= 0.2) return '💪'
  if (fullKelly.value >= 0.05) return '👍'
  return '🤔'
})

const adviceBoxClass = computed(() => {
  const e = ev.value
  if (e <= 0) return 'border-rose-200 bg-rose-50/50'
  if (fullKelly.value >= 0.2) return 'border-teal-200 bg-teal-50/50'
  return 'border-amber-200 bg-amber-50/50'
})

const adviceTextClass = computed(() => {
  const e = ev.value
  if (e <= 0) return 'text-rose-700'
  if (fullKelly.value >= 0.2) return 'text-teal-700'
  return 'text-amber-700'
})

function formatMoney(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}
</script>

<style scoped>
.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  max-height: 400px;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>

<template>
  <div class="relative" ref="dockRef">
    <button
      class="flex items-center gap-1.5 rounded-lg bg-indigo-500/20 border border-indigo-500/30 px-3 py-1.5 text-[10px] font-bold text-indigo-300 transition-all hover:bg-indigo-500/30 active:scale-95"
      @click="open = !open"
    >
      <span>🧰</span>
      <span>工具箱</span>
      <span v-if="openCount > 0" class="ml-0.5 rounded-full bg-indigo-400 px-1.5 py-0.5 text-[9px] font-black text-slate-950">
        {{ openCount }}
      </span>
    </button>

    <!-- Dropdown picker -->
    <Transition name="fade">
      <div
        v-if="open"
        class="absolute right-0 top-full z-[60] mt-2 w-72 rounded-xl border border-slate-600/50 bg-[#1e293b] p-2 shadow-[0_8px_32px_rgba(0,0,0,0.5)]"
      >
        <div class="mb-2 px-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
          可用工具
        </div>
        <button
          v-for="tool in tools"
          :key="tool.id"
          class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all"
          :class="[
            tool.bg, tool.border,
            isWidgetOpen(tool.id) ? 'ring-1 ' + tool.ring : 'hover:brightness-125'
          ]"
          @click="toggle(tool.id)"
        >
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-base" :class="tool.iconBg">
            {{ tool.icon }}
          </span>
          <div class="min-w-0 flex-1">
            <div class="text-xs font-bold" :class="tool.nameColor">{{ tool.name }}</div>
            <div class="text-[10px] text-slate-400 truncate">{{ tool.desc }}</div>
          </div>
          <span v-if="isWidgetOpen(tool.id)" class="text-[10px] font-black" :class="tool.checkColor">✓</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWidgetStore } from '@/stores/widget'

const widgetStore = useWidgetStore()
const open = ref(false)
const dockRef = ref<HTMLElement>()

const openCount = computed(() => widgetStore.openCount())

const tools = [
  { id: 'portfolio', name: '组合仓位 + 分红', icon: '📊', desc: '拖拽分配比例，计算年分红总额和加权估值',
    bg: 'bg-emerald-500/8', border: 'border border-emerald-500/20', ring: 'ring-emerald-500/40',
    iconBg: 'bg-emerald-500/15', nameColor: 'text-emerald-300', checkColor: 'text-emerald-400' },
  { id: 'compound', name: '复利计算器', icon: '📈', desc: '分红再投，模拟 5/10/20 年收益',
    bg: 'bg-cyan-500/8', border: 'border border-cyan-500/20', ring: 'ring-cyan-500/40',
    iconBg: 'bg-cyan-500/15', nameColor: 'text-cyan-300', checkColor: 'text-cyan-400' },
  { id: 'margin', name: '安全边际', icon: '🛡️', desc: '输入合理估值，计算折价率和买入建议',
    bg: 'bg-amber-500/8', border: 'border border-amber-500/20', ring: 'ring-amber-500/40',
    iconBg: 'bg-amber-500/15', nameColor: 'text-amber-300', checkColor: 'text-amber-400' },
  { id: 'position', name: '仓位管理', icon: '🎯', desc: '根据风控规则计算每笔交易的仓位大小',
    bg: 'bg-rose-500/8', border: 'border border-rose-500/20', ring: 'ring-rose-500/40',
    iconBg: 'bg-rose-500/15', nameColor: 'text-rose-300', checkColor: 'text-rose-400' },
  { id: 'dividendCal', name: '分红日历', icon: '📅', desc: '月历视图展示持仓分红到账时间',
    bg: 'bg-violet-500/8', border: 'border border-violet-500/20', ring: 'ring-violet-500/40',
    iconBg: 'bg-violet-500/15', nameColor: 'text-violet-300', checkColor: 'text-violet-400' },
  { id: 'swap', name: '换股计算器', icon: '🔄', desc: '设置换股比例，计算溢价/折价和目标价',
    bg: 'bg-pink-500/8', border: 'border border-pink-500/20', ring: 'ring-pink-500/40',
    iconBg: 'bg-pink-500/15', nameColor: 'text-pink-300', checkColor: 'text-pink-400' },
  { id: 'kelly', name: '凯利仓位', icon: '🎲', desc: '输入胜率和盈亏比，计算最优仓位比例',
    bg: 'bg-teal-500/8', border: 'border border-teal-500/20', ring: 'ring-teal-500/40',
    iconBg: 'bg-teal-500/15', nameColor: 'text-teal-300', checkColor: 'text-teal-400' },
]

function isWidgetOpen(id: string) {
  return widgetStore.widgets[id]?.visible ?? false
}

function toggle(id: string) {
  widgetStore.toggleWidget(id)
}

// close dropdown on outside click
function onClickOutside(e: MouseEvent) {
  if (dockRef.value && !dockRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>

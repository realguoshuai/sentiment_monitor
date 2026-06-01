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
        class="absolute right-0 top-full z-[60] mt-2 w-64 rounded-xl border border-slate-700/50 bg-[#1a2332] p-2 shadow-2xl"
      >
        <div class="mb-2 px-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">
          可用工具
        </div>
        <button
          v-for="tool in tools"
          :key="tool.id"
          class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-white/5"
          :class="{ 'bg-cyan-500/10 border border-cyan-500/20': isWidgetOpen(tool.id) }"
          @click="toggle(tool.id)"
        >
          <span class="text-lg">{{ tool.icon }}</span>
          <div class="min-w-0 flex-1">
            <div class="text-xs font-bold text-slate-200">{{ tool.name }}</div>
            <div class="text-[10px] text-slate-500 truncate">{{ tool.desc }}</div>
          </div>
          <span v-if="isWidgetOpen(tool.id)" class="text-[10px] font-bold text-cyan-400">✓</span>
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
  { id: 'portfolio', name: '组合仓位 + 分红', icon: '📊', desc: '拖拽分配比例，计算年分红总额和加权估值' },
  { id: 'compound', name: '复利计算器', icon: '📈', desc: '分红再投，模拟 5/10/20 年收益' },
  { id: 'margin', name: '安全边际', icon: '🛡️', desc: '输入合理估值，计算折价率和买入建议' },
  { id: 'position', name: '仓位管理', icon: '🎯', desc: '根据风控规则计算每笔交易的仓位大小' },
  { id: 'dividendCal', name: '分红日历', icon: '📅', desc: '月历视图展示持仓分红到账时间' },
  { id: 'heatmap', name: '集中度热力图', icon: '🔥', desc: 'Treemap 展示持仓分布和行业集中度' },
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

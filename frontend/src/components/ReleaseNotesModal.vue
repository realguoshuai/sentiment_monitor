<template>
  <div v-if="show" class="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-md">
    <div class="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-cyan-400/20 bg-[#101a2b] shadow-[0_30px_90px_rgba(0,0,0,0.55)]">
      <div class="flex items-start justify-between gap-5 border-b border-white/10 bg-white/[0.03] px-6 py-5">
        <div>
          <div class="mb-2 flex items-center gap-2">
            <span class="rounded border border-cyan-400/30 bg-cyan-400/10 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-cyan-300">v{{ version }}</span>
            <span class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Release Notes</span>
          </div>
          <h2 class="text-2xl font-black tracking-wide text-white">更新与快速开始</h2>
          <p class="mt-2 text-sm leading-6 text-slate-400">了解本版变化，并用最短路径开始监控、刷新、分析和对比。</p>
        </div>
        <button
          class="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
          title="关闭"
          @click="close(false)"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="grid flex-1 gap-0 overflow-y-auto md:grid-cols-[1.05fr_0.95fr]">
        <section class="border-b border-white/10 p-6 md:border-b-0 md:border-r">
          <div class="mb-5 flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-300">
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h3 class="text-base font-black text-white">本版更新</h3>
              <p class="text-xs text-slate-500">启动体验、数据稳定性和打包链路</p>
            </div>
          </div>

          <div class="space-y-3">
            <div v-for="item in updates" :key="item.title" class="rounded-xl border border-white/10 bg-slate-950/35 p-4">
              <div class="mb-1 text-sm font-bold text-slate-100">{{ item.title }}</div>
              <p class="text-xs leading-5 text-slate-400">{{ item.text }}</p>
            </div>
          </div>
        </section>

        <section class="p-6">
          <div class="mb-5 flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <div>
              <h3 class="text-base font-black text-white">快速开始</h3>
              <p class="text-xs text-slate-500">四步跑通核心工作流</p>
            </div>
          </div>

          <div class="space-y-4">
            <div v-for="step in steps" :key="step.title" class="flex gap-3">
              <div class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-cyan-400 text-xs font-black text-slate-950">
                {{ step.index }}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-bold text-slate-100">{{ step.title }}</div>
                <p class="mt-1 text-xs leading-5 text-slate-400">{{ step.text }}</p>
              </div>
            </div>
          </div>

          <div class="mt-6 rounded-xl border border-amber-300/20 bg-amber-300/10 p-4 text-xs leading-5 text-amber-100/90">
            数据采集依赖外部财经站点，首次刷新可能需要等待。页面会先打开，后端服务和数据会在后台加载。
          </div>
        </section>
      </div>

      <div class="flex flex-col gap-3 border-t border-white/10 bg-slate-950/35 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <label class="flex items-center gap-2 text-xs text-slate-400">
          <input v-model="dontShowAgain" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-400" />
          本版本不再自动显示
        </label>
        <div class="flex items-center justify-end gap-2">
          <button class="rounded-lg border border-white/10 px-4 py-2 text-xs font-bold text-slate-300 transition-colors hover:bg-white/10" @click="close(false)">
            稍后再看
          </button>
          <button class="rounded-lg bg-cyan-400 px-4 py-2 text-xs font-black text-slate-950 shadow-[0_0_18px_rgba(34,211,238,0.25)] transition-colors hover:bg-cyan-300" @click="close(true)">
            开始使用
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  show: boolean
  version: string
}>()

const emit = defineEmits<{
  close: [remember: boolean]
}>()

const dontShowAgain = ref(true)

const updates = [
  {
    title: '桌面端先开页面，再后台加载服务',
    text: '优化启动链路，前端界面不再长时间黑屏，后端就绪后数据自动刷新。',
  },
  {
    title: '修复新增股票后旧数据消失',
    text: '最新数据接口改为每只股票各取自己的最新记录，避免新股票覆盖旧股票看板。',
  },
  {
    title: '修复股价对比页面无数据',
    text: '对比页面依赖的候选股票列表恢复稳定，新增股票后仍能选择原有标的。',
  },
  {
    title: '安装包首屏显示更稳定',
    text: '加入启动遮罩，避免 CSS 加载前出现短暂布局错乱。',
  },
]

const steps = [
  {
    index: 1,
    title: '添加监控标的',
    text: '点击右上角“监控配置”，搜索公司名称或股票代码，确认添加到看板。',
  },
  {
    index: 2,
    title: '刷新并采集数据',
    text: '点击“立即刷新”拉取最新新闻、公告、研报和情绪分析结果。',
  },
  {
    index: 3,
    title: '查看个股深度分析',
    text: '点击任意个股卡片进入详情页，查看情绪、估值、质量和历史回测。',
  },
  {
    index: 4,
    title: '进行股价对比',
    text: '进入“对比分析”，选择多只股票查看实时价格、历史走势和相对表现。',
  },
]

function close(forceRemember: boolean) {
  emit('close', forceRemember || dontShowAgain.value)
}
</script>

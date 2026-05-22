<template>
  <div class="h-full flex flex-col overflow-hidden">
    <div v-if="!data || data.length === 0" class="flex-1 flex items-center justify-center text-slate-500 text-sm">
      暂无分红数据
    </div>
    <div v-else class="flex-1 overflow-y-auto pr-1 custom-scrollbar">
      <div class="relative pl-5">
        <!-- Vertical timeline line -->
        <div class="absolute left-[7px] top-2 bottom-2 w-px bg-slate-700/60"></div>

        <div v-for="(item, idx) in data" :key="item.symbol" class="relative pb-4 last:pb-0">
          <!-- Timeline dot -->
          <div
            class="absolute left-0 top-1.5 w-[15px] h-[15px] rounded-full border-2 z-10"
            :class="dotClass(item.status)"
          ></div>

          <!-- Card -->
          <div
            class="ml-3 rounded-xl p-3 border transition-all hover:border-slate-600/80"
            :class="cardBg(item.status)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-sm font-bold text-slate-200 truncate">{{ item.name }}</span>
                  <span class="text-[10px] text-slate-500 font-mono">{{ item.symbol }}</span>
                </div>
                <div class="text-[11px] text-slate-400">{{ item.plan }}</div>
              </div>
              <div class="text-right shrink-0">
                <div class="flex items-baseline gap-1">
                  <span class="text-2xl font-black font-mono" :class="countdownColor(item.status)">
                    {{ item.days_left }}
                  </span>
                  <span class="text-[10px] text-slate-500">天</span>
                </div>
                <div class="text-[10px] text-slate-500 font-mono mt-0.5">{{ item.date }}</div>
              </div>
            </div>
            <div class="mt-1.5 flex items-center justify-between">
              <span
                class="px-1.5 py-0.5 rounded text-[9px] font-bold border"
                :class="badgeClass(item.status)"
              >
                {{ item.status_desc }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  data: any[]
}>()

const dotClass = (status: string) => ({
  'bg-emerald-400 border-emerald-400/40 shadow-[0_0_8px_rgba(52,211,153,0.4)]': status === 'confirmed',
  'bg-amber-400 border-amber-400/40 shadow-[0_0_8px_rgba(251,191,36,0.3)]': status === 'proposal',
  'bg-slate-500 border-slate-500/40': status === 'estimated',
})

const cardBg = (status: string) => ({
  'bg-slate-800/40 border-emerald-500/15': status === 'confirmed',
  'bg-slate-800/40 border-amber-500/15': status === 'proposal',
  'bg-slate-800/30 border-slate-700/40': status === 'estimated',
})

const countdownColor = (status: string) => ({
  'text-emerald-400': status === 'confirmed',
  'text-amber-400': status === 'proposal',
  'text-slate-400': status === 'estimated',
})

const badgeClass = (status: string) => ({
  'bg-emerald-950/50 text-emerald-400 border-emerald-500/30': status === 'confirmed',
  'bg-amber-950/50 text-amber-400 border-amber-500/30': status === 'proposal',
  'bg-slate-800 text-slate-400 border-slate-700': status === 'estimated',
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.15);
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.3);
}
</style>

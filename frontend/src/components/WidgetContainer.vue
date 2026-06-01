<template>
  <div
    v-if="state.visible"
    class="fixed z-[50] flex flex-col overflow-hidden rounded-xl border border-slate-700/50 bg-[#1a2332] shadow-2xl select-none"
    :style="{ left: state.x + 'px', top: state.y + 'px', width: state.w + 'px', height: state.h + 'px' }"
    @mousedown="bringToFront"
  >
    <!-- Header (drag handle) -->
    <div
      class="flex shrink-0 cursor-move items-center justify-between gap-2 border-b border-slate-700/50 bg-slate-800/80 px-3 py-2"
      @mousedown.stop="startDrag"
    >
      <div class="flex items-center gap-2">
        <span class="text-sm">{{ icon }}</span>
        <span class="text-xs font-bold text-slate-200 tracking-wide">{{ title }}</span>
      </div>
      <button
        class="flex h-5 w-5 items-center justify-center rounded text-slate-500 transition-colors hover:bg-white/10 hover:text-white"
        @click.stop="widgetStore.closeWidget(widgetId)"
      >
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-3">
      <slot />
    </div>

    <!-- Resize handle -->
    <div
      class="absolute bottom-0 right-0 h-4 w-4 cursor-se-resize"
      @mousedown.stop="startResize"
    >
      <svg class="absolute bottom-1 right-1 h-3 w-3 text-slate-600" viewBox="0 0 12 12">
        <path d="M11 1L1 11M11 5L5 11M11 9L9 11" stroke="currentColor" stroke-width="1.5" fill="none" />
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWidgetStore } from '@/stores/widget'

const props = defineProps<{
  widgetId: string
  title: string
  icon?: string
}>()

const widgetStore = useWidgetStore()

const state = computed(() => widgetStore.widgets[props.widgetId])

let zIndex = 50

function bringToFront() {
  // simple z-index bump
  const el = (event?.target as HTMLElement)?.closest('.fixed')
  if (el) {
    zIndex++
    el.style.zIndex = String(zIndex)
  }
}

// --- Drag ---
let dragOffsetX = 0
let dragOffsetY = 0

function startDrag(e: MouseEvent) {
  dragOffsetX = e.clientX - state.value.x
  dragOffsetY = e.clientY - state.value.y
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

function onDrag(e: MouseEvent) {
  const x = Math.max(0, Math.min(window.innerWidth - 100, e.clientX - dragOffsetX))
  const y = Math.max(0, Math.min(window.innerHeight - 50, e.clientY - dragOffsetY))
  widgetStore.updatePosition(props.widgetId, x, y)
}

function stopDrag() {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

// --- Resize ---
let resizeStartX = 0
let resizeStartY = 0
let resizeStartW = 0
let resizeStartH = 0

function startResize(e: MouseEvent) {
  resizeStartX = e.clientX
  resizeStartY = e.clientY
  resizeStartW = state.value.w
  resizeStartH = state.value.h
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
}

function onResize(e: MouseEvent) {
  const w = resizeStartW + (e.clientX - resizeStartX)
  const h = resizeStartH + (e.clientY - resizeStartY)
  widgetStore.updateSize(props.widgetId, w, h)
}

function stopResize() {
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
}
</script>

import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export interface WidgetState {
  id: string
  visible: boolean
  x: number
  y: number
  w: number
  h: number
}

const STORAGE_KEY = 'sm-widget-state'

const DEFAULTS: Record<string, { w: number; h: number }> = {
  portfolio: { w: 420, h: 520 },
  compound: { w: 400, h: 480 },
  margin: { w: 360, h: 400 },
  position: { w: 400, h: 460 },
  dividendCal: { w: 520, h: 440 },
  swap: { w: 380, h: 600 },
  kelly: { w: 380, h: 520 },
}

function loadState(): Record<string, WidgetState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return {}
}

function saveState(widgets: Record<string, WidgetState>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widgets))
  } catch { /* ignore */ }
}

export const useWidgetStore = defineStore('widget', () => {
  const widgets = ref<Record<string, WidgetState>>(loadState())

  // ensure all known widgets exist with defaults
  for (const [id, size] of Object.entries(DEFAULTS)) {
    if (!widgets.value[id]) {
      widgets.value[id] = {
        id,
        visible: false,
        x: 100 + Math.random() * 200,
        y: 80 + Math.random() * 100,
        w: size.w,
        h: size.h,
      }
    }
  }

  watch(widgets, (v) => saveState(v), { deep: true })

  function toggleWidget(id: string) {
    const w = widgets.value[id]
    if (w) {
      w.visible = !w.visible
    }
  }

  function closeWidget(id: string) {
    const w = widgets.value[id]
    if (w) w.visible = false
  }

  function updatePosition(id: string, x: number, y: number) {
    const w = widgets.value[id]
    if (w) {
      w.x = x
      w.y = y
    }
  }

  function updateSize(id: string, width: number, height: number) {
    const w = widgets.value[id]
    if (w) {
      w.w = Math.max(280, width)
      w.h = Math.max(200, height)
    }
  }

  const openCount = () => Object.values(widgets.value).filter((w) => w.visible).length

  return { widgets, toggleWidget, closeWidget, updatePosition, updateSize, openCount }
})

<template>
  <span class="info-tooltip-wrapper" @mouseenter="show" @mouseleave="hide">
    <slot />
    <span class="info-trigger" @click.prevent.stop="toggle">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="16" x2="12" y2="12"/>
        <line x1="12" y1="8" x2="12.01" y2="8"/>
      </svg>
    </span>
    <Teleport to="body">
      <Transition name="tooltip-fade">
        <div
          v-if="visible"
          class="info-tooltip-content"
          :style="tooltipStyle"
          @mouseenter="keepOpen"
          @mouseleave="hide"
        >
          <div class="info-tooltip-arrow" :class="`arrow-${placement}`" :style="arrowStyle" />
          <div class="info-tooltip-body">
            <slot name="content">
              <span v-html="text" />
            </slot>
          </div>
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  text?: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  maxWidth?: string
}>(), {
  text: '',
  placement: 'bottom',
  maxWidth: '280px'
})

const visible = ref(false)
const triggerRect = ref<DOMRect | null>(null)
let hideTimer: ReturnType<typeof setTimeout> | null = null

const tooltipStyle = computed(() => {
  if (!triggerRect.value) return {}
  const rect = triggerRect.value
  const gap = 8

  let top = 0
  let left = 0

  switch (props.placement) {
    case 'bottom':
      top = rect.bottom + gap
      left = rect.left + rect.width / 2
      break
    case 'top':
      top = rect.top - gap
      left = rect.left + rect.width / 2
      break
    case 'right':
      top = rect.top + rect.height / 2
      left = rect.right + gap
      break
    case 'left':
      top = rect.top + rect.height / 2
      left = rect.left - gap
      break
  }

  return {
    top: `${top}px`,
    left: `${left}px`,
    maxWidth: props.maxWidth,
    transform: props.placement === 'bottom' || props.placement === 'top'
      ? 'translateX(-50%)'
      : props.placement === 'right'
        ? 'translateY(-50%)'
        : 'translate(-100%, -50%)'
  }
})

const arrowStyle = computed(() => {
  if (!triggerRect.value) return {}
  const rect = triggerRect.value
  if (props.placement === 'bottom' || props.placement === 'top') {
    return { left: '50%', transform: 'translateX(-50%)' }
  }
  return { top: '50%', transform: 'translateY(-50%)' }
})

function show(e: MouseEvent) {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  const target = e.currentTarget as HTMLElement
  triggerRect.value = target.getBoundingClientRect()
  visible.value = true
}

function hide() {
  hideTimer = setTimeout(() => {
    visible.value = false
  }, 100)
}

function keepOpen() {
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function toggle(e: MouseEvent) {
  if (visible.value) {
    visible.value = false
  } else {
    show(e)
  }
}

onBeforeUnmount(() => {
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<style scoped>
.info-tooltip-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

.info-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.info-trigger:hover {
  color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
}

.info-tooltip-content {
  position: fixed;
  z-index: 9999;
  pointer-events: auto;
}

.info-tooltip-body {
  background: #ffffff;
  color: #334155;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.78rem;
  line-height: 1.6;
  font-weight: 500;
  border: 1px solid #e2e8f0;
  box-shadow: 0 10px 30px -10px rgba(15, 23, 42, 0.15), 0 4px 12px -6px rgba(15, 23, 42, 0.08);
  white-space: normal;
}

.info-tooltip-body :deep(.formula) {
  background: #f1f5f9;
  border-radius: 8px;
  padding: 6px 10px;
  margin: 6px 0;
  font-family: 'Monaco', monospace;
  font-size: 0.72rem;
  color: #334155;
}

.info-tooltip-body :deep(strong) {
  color: #0f172a;
  font-weight: 700;
}

.info-tooltip-body :deep(.threshold) {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.7rem;
  margin: 2px 4px 2px 0;
  font-weight: 600;
}

.info-tooltip-body :deep(.threshold-green) { background: #dcfce7; color: #166534; }
.info-tooltip-body :deep(.threshold-yellow) { background: #fef9c3; color: #854d0e; }
.info-tooltip-body :deep(.threshold-red) { background: #fee2e2; color: #991b1b; }

.info-tooltip-arrow {
  position: absolute;
  width: 8px;
  height: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  transform: rotate(45deg);
}

.arrow-bottom {
  top: -4px;
}

.arrow-top {
  bottom: -4px;
}

.arrow-right {
  left: -4px;
}

.arrow-left {
  right: -4px;
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.15s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}
</style>

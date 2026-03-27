<template>
  <div class="flex gap-2 flex-wrap">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      @click="$emit('update:modelValue', tab.key)"
      class="px-4 py-2 rounded-xl transition-all text-sm font-bold border"
      :class="modelValue === tab.key
        ? 'bg-indigo-50 text-indigo-700 border-indigo-200 shadow-sm'
        : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700'"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
  tabs: { key: string; label: string }[]
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

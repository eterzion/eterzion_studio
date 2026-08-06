<script setup lang="ts">
defineProps<{
  modelValue: string
  options: { value: string; label: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="segmented" role="radiogroup">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="radio"
      :aria-checked="modelValue === opt.value"
      class="segment"
      :class="{ active: modelValue === opt.value }"
      @click="emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<style scoped>
.segmented {
  display: inline-flex;
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  padding: 3px;
  gap: 2px;
}

.segment {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.segment:hover {
  color: var(--text-primary);
}

.segment.active {
  background: var(--surface-1);
  color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}

.segment:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
</style>

<script setup lang="ts">
// A two-column tab grid for picking one mode out of three or four.
//
// SegmentedControl is a single row that wraps, which is right for two or three
// short labels and wrong here: with four options and labels like "Não melhorar"
// or "Personalizado" it broke into a ragged 3+1, and the longest label was
// clipped. In a control where the label IS the whole affordance, a clipped one
// is a broken one.
//
// Extracted from the Imagem screen rather than reimplemented, so the two
// screens cannot drift apart: they now render the same markup and the same CSS.

defineProps<{
  modelValue: string
  options: { value: string; label: string }[]
  disabled?: boolean
}>()

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="mode-tabs" :class="{ disabled }">
    <button
      v-for="option in options"
      :key="option.value"
      class="mode-tab"
      :class="{ active: option.value === modelValue }"
      type="button"
      :disabled="disabled"
      :title="option.label"
      @click="$emit('update:modelValue', option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.mode-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  background: var(--surface-3);
  border-radius: var(--radius-sm);
  padding: 3px;
  width: 100%;
}

.mode-tabs.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.mode-tab {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  font-family: inherit;
  padding: 7px 6px;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.mode-tab:hover:not(.active):not(:disabled) {
  color: var(--text-primary);
}

.mode-tab.active {
  background: var(--surface-1);
  color: var(--text-primary);
}

.mode-tab:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
</style>

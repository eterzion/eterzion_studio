<script setup lang="ts">
import { computed } from 'vue'
import AppSpinner from './AppSpinner.vue'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: ButtonSize
    loading?: boolean
    disabled?: boolean
    iconOnly?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  {
    variant: 'outline',
    size: 'md',
    loading: false,
    disabled: false,
    iconOnly: false,
    type: 'button'
  }
)

defineEmits<{ click: [MouseEvent] }>()

// Consolidates ~20 previously independent button classes (.primary-btn, .secondary-btn,
// .btn-outline, .icon-btn, .danger-btn, etc. — see research.md Audit a). Each variant is the
// closest-matching visual role found across call sites, not a byte-identical clone of any one
// of them — some hover-state nuances specific to a single old call site are intentionally not
// preserved (e.g. one icon-button's hover-turns-red was specific to a delete action, not a
// general "ghost button" behavior).
const variantClasses = computed<string>(() => {
  switch (props.variant) {
    case 'primary':
      return 'bg-accent text-on-primary border border-transparent hover:bg-accent-hover'
    case 'secondary':
      return 'bg-surface-3 border border-surface-border text-text-primary hover:bg-surface-2'
    case 'ghost':
      return 'bg-transparent border border-transparent text-text-tertiary hover:bg-surface-2 hover:text-text-primary'
    case 'danger':
      return 'bg-state-danger-soft border border-state-danger text-state-danger hover:opacity-90'
    case 'outline':
    default:
      return 'bg-surface-2 border border-surface-border text-text-primary hover:bg-surface-3'
  }
})

const sizeClasses = computed<string>(() => {
  if (props.iconOnly) {
    if (props.size === 'sm') return 'h-6 w-6 p-0'
    if (props.size === 'lg') return 'h-9 w-9 p-0'
    return 'h-[30px] w-[30px] p-0'
  }
  if (props.size === 'sm') return 'px-2 py-1 text-xs gap-1'
  if (props.size === 'lg') return 'px-5 py-[10px] text-(length:--fs-label) gap-1.5'
  return 'px-3 py-[7px] text-(length:--fs-caption) gap-1.5'
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    class="inline-flex items-center justify-center rounded-(--radius-sm) font-(family-name:--font-sans) font-semibold cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
    :class="[variantClasses, sizeClasses]"
    @click="$emit('click', $event)"
  >
    <AppSpinner v-if="loading" :size="14" />
    <slot v-else name="icon" />
    <slot v-if="!iconOnly" />
  </button>
</template>

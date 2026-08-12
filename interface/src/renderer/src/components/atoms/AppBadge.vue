<script setup lang="ts">
import { computed } from 'vue'

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'
export type BadgeShape = 'rounded' | 'pill'

const props = withDefaults(
  defineProps<{
    tone?: BadgeTone
    shape?: BadgeShape
  }>(),
  { tone: 'neutral', shape: 'pill' }
)

// Consolidates 7 previously independent badge/pill implementations (.chip,
// .credit-license-badge, .version-badge, .license-pill, .status-badge,
// .license-error-badge — see research.md Audit a). "info" reuses the accent color since no
// distinct info token exists in theme.css.
const toneClasses = computed<string>(() => {
  switch (props.tone) {
    case 'success':
      return 'bg-state-success-soft text-state-success'
    case 'warning':
      return 'bg-state-warning-soft text-state-warning'
    case 'danger':
      return 'bg-state-danger-soft text-state-danger'
    case 'info':
      return 'bg-accent-soft text-accent'
    case 'neutral':
    default:
      return 'bg-surface-3 text-text-secondary'
  }
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 text-(length:--fs-caption) font-medium"
    :class="[toneClasses, shape === 'pill' ? 'rounded-full' : 'rounded-(--radius-sm)']"
  >
    <slot />
  </span>
</template>

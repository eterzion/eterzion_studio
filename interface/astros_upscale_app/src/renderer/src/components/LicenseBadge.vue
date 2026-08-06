<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, CircleAlert, CircleX, CircleHelp } from '@lucide/vue'
import { COMMERCIAL_USE_COPY, type CommercialUse } from '../data/modelLicenses'

const props = defineProps<{
  commercialUse: CommercialUse
  compact?: boolean
}>()

const copy = computed(() => COMMERCIAL_USE_COPY[props.commercialUse])
const icon = computed(() => {
  switch (props.commercialUse) {
    case 'allowed':
      return CircleCheck
    case 'restricted':
      return CircleAlert
    case 'not_allowed':
      return CircleX
    default:
      return CircleHelp
  }
})
</script>

<template>
  <span class="badge" :class="'tone-' + copy.tone">
    <component :is="icon" :size="compact ? 11 : 13" />
    <span v-if="!compact">{{ copy.label }}</span>
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: var(--fw-semibold);
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
  border: 1px solid transparent;
}

.tone-success {
  color: var(--color-success);
  background: var(--color-success-soft);
  border-color: var(--color-success);
}

.tone-warning {
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border-color: var(--color-warning);
}

.tone-danger {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border-color: var(--color-danger);
}

.tone-neutral {
  color: var(--text-secondary);
  background: var(--surface-3);
  border-color: var(--surface-border);
}
</style>

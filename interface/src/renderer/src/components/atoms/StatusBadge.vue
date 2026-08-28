<script setup lang="ts">
import { computed, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Clock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  ShieldAlert,
  Search
} from '@lucide/vue'

// One vocabulary for "what is this job doing", shared by every screen that
// shows one. Each state resolves to an icon AND a written label, never colour
// alone — colour is the third signal, not the only one.
export type JobState =
  | 'configuring'
  | 'detecting'
  | 'queued'
  | 'processing'
  | 'awaiting_confirmation'
  | 'done'
  | 'error'
  | 'cancelled'

const props = withDefaults(
  defineProps<{
    state: JobState
    /** Appended after the label, e.g. a percentage or queue position. */
    detail?: string | null
  }>(),
  { detail: null }
)

const { t } = useI18n()

// Icon and tone are fixed; only the label follows the language, so the map
// stays a const and the label is looked up when the badge renders.
const META: Record<JobState, { icon: Component; tone: string }> = {
  configuring: { icon: Clock, tone: 'neutral' },
  detecting: { icon: Search, tone: 'neutral' },
  queued: { icon: Clock, tone: 'neutral' },
  processing: { icon: Loader2, tone: 'primary' },
  awaiting_confirmation: { icon: ShieldAlert, tone: 'warning' },
  done: { icon: CheckCircle2, tone: 'success' },
  error: { icon: AlertCircle, tone: 'danger' },
  cancelled: { icon: XCircle, tone: 'neutral' }
}

const meta = computed(() => ({ ...META[props.state], label: t(`jobState.${props.state}`) }))
const text = computed(() =>
  props.detail ? `${meta.value.label} · ${props.detail}` : meta.value.label
)
</script>

<template>
  <span class="status-badge" :class="`tone-${meta.tone}`">
    <component
      :is="meta.icon"
      :size="13"
      :class="{ 'animate-spin': state === 'processing' }"
      aria-hidden="true"
    />
    <span>{{ text }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  font-family: var(--font-mono);
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  letter-spacing: 0.01em;
  min-width: 0;
}

.tone-neutral {
  color: var(--text-secondary);
}
.tone-primary {
  color: var(--color-primary);
}
.tone-success {
  color: var(--color-success);
}
.tone-warning {
  color: var(--color-warning);
}
.tone-danger {
  color: var(--color-danger);
}
</style>

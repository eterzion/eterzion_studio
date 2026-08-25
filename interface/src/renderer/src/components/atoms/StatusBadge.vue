<script setup lang="ts">
import { computed, type Component } from 'vue'
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

const META: Record<JobState, { label: string; icon: Component; tone: string }> = {
  configuring: { label: 'Configurando', icon: Clock, tone: 'neutral' },
  detecting: { label: 'Detectando tipo de conteúdo', icon: Search, tone: 'neutral' },
  queued: { label: 'Na fila', icon: Clock, tone: 'neutral' },
  processing: { label: 'Processando', icon: Loader2, tone: 'primary' },
  awaiting_confirmation: { label: 'Aguardando confirmação', icon: ShieldAlert, tone: 'warning' },
  done: { label: 'Concluído', icon: CheckCircle2, tone: 'success' },
  error: { label: 'Erro', icon: AlertCircle, tone: 'danger' },
  cancelled: { label: 'Cancelado', icon: XCircle, tone: 'neutral' }
}

const meta = computed(() => META[props.state])
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

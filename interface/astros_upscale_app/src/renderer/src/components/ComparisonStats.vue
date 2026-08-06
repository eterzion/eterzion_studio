<script setup lang="ts">
import { computed } from 'vue'
import type { Job } from '../store/jobs'

const props = defineProps<{ job: Job }>()

function fmtBytes(bytes: number | null | undefined): string {
  if (bytes == null) return '—'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function fmtDim(value: number | null | undefined): string {
  return value == null ? '—' : String(value)
}

const processingSeconds = computed(() => {
  const { processingStartedAt, processingEndedAt } = props.job
  if (!processingStartedAt || !processingEndedAt) return null
  return Math.round((processingEndedAt - processingStartedAt) / 1000)
})

const resolutionLabel = computed(
  () =>
    `${fmtDim(props.job.sourceMeta.width)}×${fmtDim(props.job.sourceMeta.height)} → ` +
    `${fmtDim(props.job.outputMeta?.width)}×${fmtDim(props.job.outputMeta?.height)}`
)

const modelSummary = computed(() => {
  const c = props.job.scaleConfig
  const scaleLabel = c.mode === 'preset' ? `${c.presetFactor}x` : `${c.customWidth ?? '—'}×${c.customHeight ?? '—'}px`
  return `${c.model} · ${scaleLabel} · ruído ${c.denoise}`
})
</script>

<template>
  <div class="stats-grid">
    <div class="stat">
      <span class="stat-label">Resolução</span>
      <span class="stat-value" :title="resolutionLabel">{{ resolutionLabel }}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Tamanho do arquivo</span>
      <span class="stat-value">{{ fmtBytes(job.sourceMeta.sizeBytes) }} → {{ fmtBytes(job.outputMeta?.sizeBytes) }}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Tempo de processamento</span>
      <span class="stat-value">{{ processingSeconds != null ? processingSeconds + 's' : '—' }}</span>
    </div>
    <div class="stat stat-wide">
      <span class="stat-label">Modelo e parâmetros</span>
      <span class="stat-value wrap">{{ modelSummary }}</span>
    </div>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
}

.stat-wide {
  grid-column: 1 / -1;
}

.stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-value.wrap {
  white-space: normal;
  overflow-wrap: break-word;
  word-break: break-word;
}
</style>

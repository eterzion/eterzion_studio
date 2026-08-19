<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Job } from '../store/jobs'

const props = defineProps<{ job: Job }>()

function fmtBytes(bytes: number | null | undefined): string {
  if (bytes == null) return '—'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function fmtDim(value: number | null | undefined): string {
  return value == null ? '—' : String(value)
}

// Original mode finishes in well under a second, where rounding to seconds
// reported a flat "0s" — which reads as "nothing happened" rather than "it was
// fast". Below a second the real milliseconds are shown instead.
const processingLabel = computed(() => {
  const { processingStartedAt, processingEndedAt } = props.job
  if (!processingStartedAt || !processingEndedAt) return '—'
  const ms = processingEndedAt - processingStartedAt
  return ms < 1000 ? `${Math.max(1, Math.round(ms))}ms` : `${Math.round(ms / 1000)}s`
})

const sourceResolution = computed(
  () => `${fmtDim(props.job.sourceMeta.width)}×${fmtDim(props.job.sourceMeta.height)}`
)
const outputResolution = computed(
  () => `${fmtDim(props.job.outputMeta?.width)}×${fmtDim(props.job.outputMeta?.height)}`
)

// Original mode travels as scale '1x' and resolves no model at all, so the
// profile — which only ever tunes how hard a model pass works — describes
// nothing that ran. Naming it here claimed work the job never did.
const usesModel = computed(() => props.job.scaleConfig.mode !== 'original')

// What actually ran, not what the panel offers: each of these only lands in the
// output when it was switched on, and Original mode makes them the entire
// pipeline — so "nenhum" is a real, meaningful answer here.
const adjustmentsSummary = computed(() => {
  const c = props.job.scaleConfig
  const used: string[] = []
  if (c.denoiseFilterEnabled && c.denoiseFilterStrength > 0)
    used.push(t('stats.noise', { value: c.denoiseFilterStrength }))
  if (c.sharpenEnabled && c.sharpen > 0) used.push(t('stats.sharpness', { value: c.sharpen }))
  if (c.faceRecovery) used.push(t('stats.faces', { value: c.faceRecoveryStrength }))
  // null, not 'Nenhum': the row is dropped instead of stating an absence. A
  // panel that reports the run should be short when little happened.
  return used.length ? used.join(' · ') : null
})

const modelSummary = computed(() => {
  const c = props.job.scaleConfig
  const scaleLabel =
    c.mode === 'preset'
      ? `${c.presetFactor}x`
      : `${c.customWidth ?? '—'}×${c.customHeight ?? '—'}px`
  // te() first: an unknown profile falls back to its raw value rather
  // than rendering a missing-key string at the user.
  const profile = te(`processing.profile.${c.profile}.label`)
    ? t(`processing.profile.${c.profile}.label`)
    : c.profile
  return `${profile} · ${scaleLabel}`
})

const { t, te } = useI18n()
</script>

<template>
  <div class="stats-grid">
    <div class="stat">
      <span class="stat-label">{{ t('stats.resolution') }}</span>
      <span class="stat-value">
        <span>{{ sourceResolution }}</span>
        <span class="stat-after">→ {{ outputResolution }}</span>
      </span>
    </div>
    <div class="stat">
      <span class="stat-label">{{ t('stats.fileSize') }}</span>
      <span class="stat-value">
        <span>{{ fmtBytes(job.sourceMeta.sizeBytes) }}</span>
        <span class="stat-after">→ {{ fmtBytes(job.outputMeta?.sizeBytes) }}</span>
      </span>
    </div>
    <div class="stat">
      <span class="stat-label">{{ t('stats.processingTime') }}</span>
      <span class="stat-value">{{ processingLabel }}</span>
    </div>
    <div v-if="adjustmentsSummary" class="stat">
      <span class="stat-label">{{ t('stats.adjustmentsApplied') }}</span>
      <span class="stat-value">{{ adjustmentsSummary }}</span>
    </div>
    <!-- Only when a model ran. "Sem modelo" said nothing the resolution and the
         adjustments above had not already made plain. -->
    <div v-if="usesModel" class="stat">
      <span class="stat-label">{{ t('stats.modelAndParams') }}</span>
      <span class="stat-value">{{ modelSummary }}</span>
    </div>
  </div>
</template>

<style scoped>
/* One stat per row. Side by side, a "before → after" pair had to break across
   two cramped lines in a 320px panel; full width lets each value keep its own
   line without the card getting narrower than the number it holds. */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr;
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

.stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

/* One line now that each stat has the full panel width; the two halves are
   still separate elements so the result can carry the accent colour, and so a
   very long pair wraps at the arrow instead of mid-number. */
.stat-value {
  display: flex;
  flex-wrap: wrap;
  gap: 0 0.4em;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  font-family: var(--font-mono);
  min-width: 0;
  white-space: normal;
  overflow-wrap: break-word;
  word-break: break-word;
}

.stat-after {
  color: var(--color-primary);
}
</style>

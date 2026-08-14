<script setup lang="ts">
import { computed } from 'vue'
import { ImageIcon, Expand, TrendingUp, TrendingDown, HardDrive } from '@lucide/vue'

const props = defineProps<{
  originalWidth: number | null
  originalHeight: number | null
  newWidth: number | null
  newHeight: number | null
  estimatedBytes: number | null
}>()

const scaleFactor = computed(() => {
  if (!props.originalWidth || !props.originalHeight || !props.newWidth || !props.newHeight)
    return null
  const origPixels = props.originalWidth * props.originalHeight
  const newPixels = props.newWidth * props.newHeight
  return Math.sqrt(newPixels / origPixels)
})

// Signed, and shown for reductions too: the Original mode resizes downward, so
// this reports -10% as readily as +300%. A hardcoded "+" turned the first case
// into "(+-10%)".
const percentDelta = computed(() =>
  scaleFactor.value ? Math.round((scaleFactor.value - 1) * 100) : null
)
const percentLabel = computed(() =>
  percentDelta.value == null ? null : `${percentDelta.value > 0 ? '+' : ''}${percentDelta.value}%`
)

// The factor itself stays positive — it is a multiplier, and 0.51x IS the
// reduction; a negative multiplier would mean something else entirely. What
// carries the direction is the signed percentage and this icon.
const scaleIcon = computed(() => ((percentDelta.value ?? 0) < 0 ? TrendingDown : TrendingUp))

function fmtBytes(bytes: number | null): string {
  if (bytes == null) return '—'
  return '≈ ' + (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="info-panel">
    <div class="info-row">
      <div class="info-icon icon-chip"><ImageIcon :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Resolução original</span>
        <span class="info-value">
          {{ originalWidth ?? '—' }} × {{ originalHeight ?? '—' }} px
        </span>
      </div>
    </div>

    <div class="info-row highlight">
      <div class="info-icon icon-chip primary"><Expand :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Nova resolução</span>
        <span class="info-value info-value-lg">
          {{ newWidth ?? '—' }} × {{ newHeight ?? '—' }} px
        </span>
      </div>
    </div>

    <div class="info-row highlight">
      <div class="info-icon icon-chip primary"><component :is="scaleIcon" :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Escala</span>
        <span class="info-value info-value-lg">
          {{ scaleFactor ? scaleFactor.toFixed(2) + '×' : '—' }}
          <span
            v-if="percentLabel"
            class="info-delta"
            :class="{ negative: (percentDelta ?? 0) < 0 }"
            >({{ percentLabel }})</span
          >
        </span>
      </div>
    </div>

    <div class="info-row muted">
      <div class="info-icon icon-chip"><HardDrive :size="14" /></div>
      <div class="info-body">
        <span class="info-label">Tamanho estimado</span>
        <span class="info-value">{{ fmtBytes(estimatedBytes) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.info-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.info-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px var(--space-2);
  border-radius: var(--radius-sm);
}

.info-row.highlight {
  background: var(--surface-2);
}

.info-row.muted {
  opacity: 0.8;
}

.info-icon {
  /* The neutral variant of the chip: same shape and glow, tuned down to the
     tertiary text colour so a plain info row does not read as an accent. */
  --chip-tone: var(--text-tertiary);
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
}

.info-icon.primary {
  --chip-tone: var(--color-primary);
}

.info-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.info-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  font-family: var(--font-mono);
  overflow-wrap: break-word;
}

.info-value-lg {
  font-size: 15px;
  font-weight: var(--fw-semibold);
}

.info-delta {
  font-size: var(--fs-caption);
  color: var(--color-success);
  font-weight: var(--fw-medium);
}

/* A reduction is not a failure, so this is the neutral text colour rather than
   the danger one — it just should not read as the same "gain" green. */
.info-delta.negative {
  color: var(--text-secondary);
}
</style>

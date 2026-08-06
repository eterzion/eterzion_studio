<script setup lang="ts">
import { computed } from 'vue'
import { ImageIcon, Expand, TrendingUp, HardDrive } from '@lucide/vue'

const props = defineProps<{
  originalWidth: number | null
  originalHeight: number | null
  newWidth: number | null
  newHeight: number | null
  estimatedBytes: number | null
}>()

const scaleFactor = computed(() => {
  if (!props.originalWidth || !props.originalHeight || !props.newWidth || !props.newHeight) return null
  const origPixels = props.originalWidth * props.originalHeight
  const newPixels = props.newWidth * props.newHeight
  return Math.sqrt(newPixels / origPixels)
})

const percentIncrease = computed(() => (scaleFactor.value ? Math.round((scaleFactor.value - 1) * 100) : null))

function fmtBytes(bytes: number | null): string {
  if (bytes == null) return '—'
  return '≈ ' + (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="info-panel">
    <div class="info-row">
      <div class="info-icon"><ImageIcon :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Resolução original</span>
        <span class="info-value">
          {{ originalWidth ?? '—' }} × {{ originalHeight ?? '—' }} px
        </span>
      </div>
    </div>

    <div class="info-row highlight">
      <div class="info-icon primary"><Expand :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Nova resolução</span>
        <span class="info-value info-value-lg">
          {{ newWidth ?? '—' }} × {{ newHeight ?? '—' }} px
        </span>
      </div>
    </div>

    <div class="info-row highlight">
      <div class="info-icon primary"><TrendingUp :size="15" /></div>
      <div class="info-body">
        <span class="info-label">Escala</span>
        <span class="info-value info-value-lg">
          {{ scaleFactor ? scaleFactor.toFixed(2) + '×' : '—' }}
          <span v-if="percentIncrease != null" class="info-delta">(+{{ percentIncrease }}%)</span>
        </span>
      </div>
    </div>

    <div class="info-row muted">
      <div class="info-icon"><HardDrive :size="14" /></div>
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
  gap: 6px;
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
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  background: var(--surface-3);
}

.info-icon.primary {
  color: var(--color-primary);
  background: var(--color-primary-soft);
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
</style>

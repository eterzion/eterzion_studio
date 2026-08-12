<script setup lang="ts">
import { Images, HardDrive, Clock, Sparkles } from '@lucide/vue'

defineProps<{
  fileCount: number
  totalSizeLabel: string
  statusLabel: string
  qualityLabel: string
}>()
</script>

<template>
  <div class="summary-grid">
    <div class="summary-card">
      <div class="summary-card-top">
        <div class="summary-icon tone-primary"><Images :size="16" /></div>
        <div>
          <div class="summary-value">{{ fileCount }}</div>
          <div class="summary-label">Arquivo{{ fileCount === 1 ? '' : 's' }} na fila</div>
        </div>
      </div>
      <div class="summary-bar tone-primary" />
    </div>

    <div class="summary-card">
      <div class="summary-card-top">
        <div class="summary-icon tone-success"><HardDrive :size="16" /></div>
        <div>
          <div class="summary-value">{{ totalSizeLabel }}</div>
          <div class="summary-label">Tamanho total</div>
        </div>
      </div>
      <div class="summary-bar tone-success" />
    </div>

    <div class="summary-card">
      <div class="summary-card-top">
        <div class="summary-icon tone-warning"><Clock :size="16" /></div>
        <div>
          <div class="summary-value">{{ statusLabel }}</div>
          <div class="summary-label">Status atual</div>
        </div>
      </div>
      <div class="summary-bar tone-warning" />
    </div>

    <div class="summary-card">
      <div class="summary-card-top">
        <div class="summary-icon tone-purple"><Sparkles :size="16" /></div>
        <div>
          <div class="summary-value">{{ qualityLabel }}</div>
          <div class="summary-label">Qualidade e detalhes</div>
        </div>
      </div>
      <div class="summary-bar tone-purple" />
    </div>
  </div>
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}

.summary-card-top {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.summary-bar {
  height: 3px;
  border-radius: 999px;
  background: var(--surface-3);
}

.summary-bar.tone-primary {
  background: color-mix(in srgb, var(--color-primary) 70%, transparent);
}

.summary-bar.tone-success {
  background: color-mix(in srgb, var(--color-success) 70%, transparent);
}

.summary-bar.tone-warning {
  background: color-mix(in srgb, var(--color-warning) 70%, transparent);
}

.summary-bar.tone-purple {
  background: rgba(167, 139, 250, 0.6);
}

.summary-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tone-primary {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.tone-success {
  color: var(--color-success);
  background: var(--color-success-soft);
}

.tone-warning {
  color: var(--color-warning);
  background: var(--color-warning-soft);
}

.tone-purple {
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.14);
}

.summary-value {
  font-size: var(--fs-value);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  line-height: 1.3;
}

.summary-label {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

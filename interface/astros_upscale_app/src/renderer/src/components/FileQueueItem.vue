<script setup lang="ts">
import { computed } from 'vue'
import { Clock, Loader2, CheckCircle2, AlertCircle, CircleX, X, Image } from '@lucide/vue'
import type { Job } from '../store/jobs'

const props = defineProps<{
  job: Job
}>()

defineEmits<{
  remove: [id: string]
}>()

const statusMeta = computed(() => {
  switch (props.job.status) {
    case 'configuring':
      return { label: 'Configurando', icon: Clock, tone: 'neutral' }
    case 'queued':
      return {
        label: props.job.queuePosition ? `Na fila (posição ${props.job.queuePosition})` : 'Na fila',
        icon: Clock,
        tone: 'neutral'
      }
    case 'processing':
      return { label: `Processando · ${props.job.progress}%`, icon: Loader2, tone: 'primary' }
    case 'done':
      return { label: 'Concluído', icon: CheckCircle2, tone: 'success' }
    case 'error':
      return {
        label: props.job.errorMessage || 'Falha no processamento',
        icon: AlertCircle,
        tone: 'danger'
      }
    case 'cancelled':
      return { label: 'Cancelado', icon: CircleX, tone: 'neutral' }
    default:
      return { label: '', icon: Clock, tone: 'neutral' }
  }
})

const sizeLabel = computed(
  () => (props.job.sourceMeta.sizeBytes / (1024 * 1024)).toFixed(2) + ' MB'
)
</script>

<template>
  <div class="queue-item">
    <div class="thumb">
      <img v-if="job.thumbnail" :src="job.thumbnail" alt="" />
      <Image v-else :size="20" />
    </div>

    <div class="info">
      <div class="info-top">
        <span class="file-name">{{ job.fileName }}</span>
        <button class="remove-btn" type="button" @click.stop="$emit('remove', job.id)">
          <X :size="14" />
        </button>
      </div>
      <div class="meta">
        <span>Imagem · {{ job.sourceMeta.format }}</span>
        <span v-if="job.sourceMeta.width"
          >{{ job.sourceMeta.width }} x {{ job.sourceMeta.height }}</span
        >
        <span>{{ sizeLabel }}</span>
      </div>

      <div class="status-row" :class="'tone-' + statusMeta.tone">
        <component
          :is="statusMeta.icon"
          :size="13"
          :class="{ spin: job.status === 'processing' }"
        />
        <span>{{ statusMeta.label }}</span>
      </div>

      <div v-if="job.status === 'processing' || job.status === 'queued'" class="progress-track">
        <div
          class="progress-fill"
          :class="'tone-' + statusMeta.tone"
          :style="{ width: (job.status === 'queued' ? 0 : job.progress) + '%' }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.queue-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
  animation: queue-item-in 220ms ease backwards;
}

.queue-item:hover {
  border-color: var(--surface-border);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

@keyframes queue-item-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.thumb {
  width: var(--thumb-size);
  height: var(--thumb-size);
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  background: var(--surface-3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  overflow: hidden;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.file-name {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-btn {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  flex-shrink: 0;
}

.remove-btn:hover {
  color: var(--text-primary);
  background: var(--surface-3);
}

.meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.status-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
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

.tone-danger {
  color: var(--color-danger);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.progress-track {
  height: 5px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 200ms ease;
}

.progress-fill.tone-neutral {
  background: var(--text-tertiary);
}

.progress-fill.tone-primary {
  background: var(--color-primary);
}

.progress-fill.tone-danger {
  background: var(--color-danger);
}
</style>

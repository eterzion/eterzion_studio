<script setup lang="ts">
import { computed } from 'vue'
import { X, Image } from '@lucide/vue'
import type { Job } from '../store/jobs'
import AppButton from './atoms/AppButton.vue'
import StatusBadge from './atoms/StatusBadge.vue'
import ProgressBar from './atoms/ProgressBar.vue'

const props = defineProps<{
  job: Job
}>()

defineEmits<{
  remove: [id: string]
}>()

// StatusBadge owns the label/icon/tone for each state — this only supplies what
// is specific to THIS job (queue position, progress, failure reason).
const statusDetail = computed(() => {
  switch (props.job.status) {
    case 'queued':
      return props.job.queuePosition ? `posição ${props.job.queuePosition}` : null
    case 'processing':
      return `${props.job.progress}%`
    case 'error':
      return props.job.errorMessage || 'falha no processamento'
    default:
      return null
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
        <AppButton variant="ghost" icon-only size="sm" @click.stop="$emit('remove', job.id)">
          <template #icon><X :size="14" /></template>
        </AppButton>
      </div>
      <div class="meta">
        <span>Imagem · {{ job.sourceMeta.format }}</span>
        <span v-if="job.sourceMeta.width"
          >{{ job.sourceMeta.width }} x {{ job.sourceMeta.height }}</span
        >
        <span>{{ sizeLabel }}</span>
      </div>

      <StatusBadge :state="job.status" :detail="statusDetail" />

      <ProgressBar
        v-if="job.status === 'processing' || job.status === 'queued'"
        :value="job.status === 'queued' ? 0 : job.progress"
        :tone="job.status === 'queued' ? 'neutral' : 'primary'"
      />
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
  gap: var(--space-1-5);
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

.meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}
</style>

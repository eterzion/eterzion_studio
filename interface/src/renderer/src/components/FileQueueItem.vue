<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, Image, Film, AudioLines, GripVertical } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import StatusBadge from './atoms/StatusBadge.vue'
import ProgressBar from './atoms/ProgressBar.vue'
import { canReorder, kindLabel, type QueueEntry } from '../store/mediaQueue'

// Takes a QueueEntry rather than a Job: this row now shows images, videos and
// audio, and those three keep very different state (see store/mediaQueue.ts).
// The entry is the small set of fields the queue actually needs from all three.

const props = defineProps<{ entry: QueueEntry; draggable?: boolean }>()

defineEmits<{ remove: [entry: QueueEntry] }>()

const { t } = useI18n()

const KIND_ICON = { image: Image, video: Film, audio: AudioLines }
const icon = computed(() => KIND_ICON[props.entry.kind])

const sizeLabel = computed(() => `${(props.entry.sizeBytes / (1024 * 1024)).toFixed(1)} MB`)

const reorderable = computed(() => props.draggable !== false && canReorder(props.entry))

// StatusBadge owns the label/icon/tone for each state — this only supplies what
// is specific to THIS item (queue position, progress, failure reason).
const statusDetail = computed(() => {
  switch (props.entry.status) {
    case 'queued':
      return props.entry.queuePosition
        ? t('jobState.queuePosition', { position: props.entry.queuePosition })
        : null
    case 'processing':
      return `${props.entry.progress}%`
    case 'error':
      return props.entry.errorMessage || t('jobState.error').toLowerCase()
    default:
      return null
  }
})
</script>

<template>
  <div class="queue-item" :class="{ reorderable }">
    <!-- A dedicated handle, not the whole row: the row is also a click target
         that opens the file, and a draggable row makes that click feel unsafe
         to press. The handle only appears where a drag would actually change
         the processing order. -->
    <div v-if="reorderable" class="drag-handle" :title="t('queue.dragToReorder')">
      <GripVertical :size="15" />
    </div>
    <div v-else class="drag-spacer" />

    <div class="thumb">
      <img v-if="entry.thumbnail" :src="entry.thumbnail" alt="" />
      <component :is="icon" v-else :size="20" />
    </div>

    <div class="info">
      <div class="info-top">
        <span class="file-name">{{ entry.fileName }}</span>
        <AppButton variant="ghost" icon-only size="sm" @click.stop="$emit('remove', entry)">
          <template #icon><X :size="14" /></template>
        </AppButton>
      </div>
      <div class="meta">
        <span>{{ kindLabel(entry.kind) }}</span>
        <span v-if="entry.detail">{{ entry.detail }}</span>
        <span>{{ sizeLabel }}</span>
      </div>

      <StatusBadge :state="entry.status" :detail="statusDetail" />

      <ProgressBar
        v-if="entry.status === 'processing' || entry.status === 'queued'"
        :value="entry.status === 'queued' ? 0 : entry.progress"
        :tone="entry.status === 'queued' ? 'neutral' : 'primary'"
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

/* While this row is the one being dragged. Kept faint rather than hidden so
   the list does not appear to lose an item mid-drag. */
.queue-item.dragging {
  opacity: 0.4;
}

/* Where the dragged row would land. */
.queue-item.drop-before {
  box-shadow: inset 0 2px 0 0 var(--color-primary);
}

.queue-item.drop-after {
  box-shadow: inset 0 -2px 0 0 var(--color-primary);
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

.drag-handle,
.drag-spacer {
  width: 16px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drag-handle {
  cursor: grab;
  color: var(--text-tertiary);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

/* Revealed on hover or keyboard focus. Always-on grips turn a list into a
   control panel; hidden-forever ones are undiscoverable. */
.queue-item:hover .drag-handle,
.queue-item:focus-within .drag-handle {
  opacity: 1;
}

.drag-handle:active {
  cursor: grabbing;
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

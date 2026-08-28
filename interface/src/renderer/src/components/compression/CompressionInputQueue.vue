<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { X, Plus, AlertTriangle } from '@lucide/vue'
import AppSpinner from '../atoms/AppSpinner.vue'
import type { QueueItem } from '../../composables/useCompressionQueue'

// specs/008-compression-centre — T025g: remover um, limpar todos, acrescentar mais (FR-009).
//
// Um arquivo recusado continua na lista, marcado. Sumir com ele deixaria a
// pessoa contando arquivos e concluindo que soltou de menos — e o motivo da
// recusa, que é a única coisa acionável ali, iria junto.

defineProps<{ items: QueueItem[]; activeId: string | null }>()
const emit = defineEmits<{ select: [string]; remove: [string]; add: []; clear: [] }>()

const { t } = useI18n()
</script>

<template>
  <section class="input-queue" :aria-label="t('compression.queue.title')">
    <header class="queue-header">
      <span class="queue-title">{{ t('compression.queue.count', items.length) }}</span>
      <div class="queue-actions">
        <button type="button" class="queue-action" @click="emit('add')">
          <Plus :size="14" />
          {{ t('compression.queue.add') }}
        </button>
        <button type="button" class="queue-action" :disabled="!items.length" @click="emit('clear')">
          {{ t('compression.queue.clearAll') }}
        </button>
      </div>
    </header>

    <ul class="queue-list">
      <li
        v-for="item in items"
        :key="item.id"
        class="queue-item"
        :class="{ active: item.id === activeId, rejected: item.status === 'rejected' }"
      >
        <button
          type="button"
          class="item-select"
          :disabled="item.status !== 'ready'"
          @click="emit('select', item.id)"
        >
          <AppSpinner v-if="item.status === 'importing'" :size="14" />
          <AlertTriangle v-else-if="item.status === 'rejected'" :size="14" class="item-warning" />
          <span class="item-name">{{ item.fileName }}</span>
          <span v-if="item.status === 'rejected'" class="item-reason">
            {{ t(`compression.refusal.${item.reason}`) }}
          </span>
          <span v-else-if="item.media" class="item-kind">
            {{ t(`compression.media.${item.media.media_kind}`) }}
          </span>
        </button>
        <button
          type="button"
          class="item-remove"
          :title="t('compression.queue.remove', { name: item.fileName })"
          :aria-label="t('compression.queue.remove', { name: item.fileName })"
          @click="emit('remove', item.id)"
        >
          <X :size="13" />
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.input-queue {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.queue-title {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.queue-actions {
  display: flex;
  gap: var(--space-1);
}

.queue-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.queue-action:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.queue-action:disabled {
  opacity: 0.45;
  cursor: default;
}

.queue-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  max-height: 220px;
}

.queue-item {
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
}

.queue-item.active {
  background: var(--color-primary-soft);
}

.item-select {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-1-5);
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--fs-label-sm);
  text-align: left;
  cursor: pointer;
}

.item-select:disabled {
  cursor: default;
}

.item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-kind,
.item-reason {
  flex-shrink: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.queue-item.rejected .item-name,
.item-reason {
  color: var(--color-warning);
}

.item-warning {
  color: var(--color-warning);
  flex-shrink: 0;
}

.item-remove {
  flex-shrink: 0;
  display: inline-flex;
  padding: var(--space-1);
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.item-remove:hover {
  color: var(--color-danger);
  background: var(--surface-3);
}
</style>

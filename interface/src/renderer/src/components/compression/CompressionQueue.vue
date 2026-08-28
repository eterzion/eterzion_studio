<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, RotateCcw, Check, AlertTriangle } from '@lucide/vue'
import ProgressBar from '../atoms/ProgressBar.vue'
import AppButton from '../atoms/AppButton.vue'
import { formatBytesDecimal } from '../../utils/formatBytes'
import type { BatchItem } from '../../composables/useCompressionBatch'

// specs/008-compression-centre — T081: o que está acontecendo com cada arquivo.
//
// **Cada item mostra o próprio progresso, e o geral é a média deles.** Contar
// concluídos faria a barra geral ficar parada durante o arquivo mais longo e
// depois saltar — exatamente quando a pessoa mais quer saber se algo está
// acontecendo.
//
// **Um item com erro fica na lista, com o motivo e um botão de tentar de novo.**
// Sumir com ele deixaria a pessoa contando arquivos; e o botão precisa refazer
// **só o que falhou**, porque refazer tudo desperdiça o que já deu certo e,
// pior, colide com os arquivos já exportados — obrigando a responder à pergunta
// de conflito por trabalho que ninguém pediu de novo.

const props = defineProps<{
  items: BatchItem[]
  running: boolean
  overallProgress: number
  savedBytes: number
  originalBytes: number
  failedCount: number
  finishedCount: number
}>()

const emit = defineEmits<{
  cancelItem: [string]
  cancelAll: []
  retryFailed: []
  reveal: [string]
}>()

const { t, n } = useI18n()

const percent = computed(() => {
  if (!props.originalBytes) return null
  return Math.round((props.savedBytes / props.originalBytes) * 100)
})
</script>

<template>
  <section class="queue" :aria-label="t('compression.batch.title')">
    <header class="queue-header">
      <span class="queue-title">
        {{ t('compression.batch.progress', { done: finishedCount, total: items.length }) }}
      </span>
      <AppButton v-if="running" variant="ghost" size="sm" @click="emit('cancelAll')">
        {{ t('compression.batch.cancelAll') }}
      </AppButton>
      <AppButton
        v-else-if="failedCount > 0"
        variant="outline"
        size="sm"
        @click="emit('retryFailed')"
      >
        <RotateCcw :size="13" />
        {{ t('compression.batch.retryFailed', failedCount) }}
      </AppButton>
    </header>

    <ProgressBar :value="overallProgress" />

    <!-- A economia só aparece quando há economia medida. Um "0 B economizados"
         durante o primeiro arquivo é verdadeiro e inútil. -->
    <p v-if="savedBytes > 0 && percent !== null" class="queue-saving">
      {{
        t('compression.batch.saved', {
          size: formatBytesDecimal(savedBytes),
          percent: n(percent)
        })
      }}
    </p>

    <ul class="queue-items">
      <li v-for="item in items" :key="item.queueId" class="queue-item" :class="item.status">
        <div class="item-head">
          <Check v-if="item.status === 'done'" :size="13" class="icon-done" />
          <AlertTriangle v-else-if="item.status === 'error'" :size="13" class="icon-error" />
          <span class="item-name">{{ item.fileName }}</span>

          <span v-if="item.status === 'error'" class="item-note error">
            {{ t(`compression.refusal.${item.error ?? 'unknown'}`) }}
          </span>
          <span v-else-if="item.status === 'cancelled'" class="item-note">
            {{ t('compression.batch.cancelled') }}
          </span>
          <span v-else-if="item.status === 'done' && item.result" class="item-note">
            {{ formatBytesDecimal(item.result.originalBytes) }} →
            {{ formatBytesDecimal(item.result.outputSizeBytes) }}
          </span>
          <span v-else-if="item.status === 'running'" class="item-note">{{ item.progress }}%</span>
          <span v-else class="item-note">{{ t('compression.batch.waiting') }}</span>

          <button
            v-if="item.status === 'pending' || item.status === 'running'"
            type="button"
            class="item-cancel"
            :title="t('compression.batch.cancelOne', { name: item.fileName })"
            :aria-label="t('compression.batch.cancelOne', { name: item.fileName })"
            @click="emit('cancelItem', item.queueId)"
          >
            <X :size="12" />
          </button>
          <button
            v-else-if="item.status === 'done' && item.result"
            type="button"
            class="item-reveal"
            @click="emit('reveal', item.result.outputPath)"
          >
            {{ t('compression.batch.show') }}
          </button>
        </div>

        <ProgressBar v-if="item.status === 'running'" :value="item.progress" />
      </li>
    </ul>
  </section>
</template>

<style scoped>
.queue {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
  padding: var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.queue-title {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.queue-saving {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-primary);
}

.queue-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 240px;
  overflow-y: auto;
}

.queue-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-head {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--fs-label-sm);
}

.item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
}

.queue-item.cancelled .item-name {
  color: var(--text-tertiary);
  text-decoration: line-through;
}

.item-note {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.item-note.error {
  color: var(--color-warning);
}

.icon-done {
  color: var(--color-primary);
  flex-shrink: 0;
}

.icon-error {
  color: var(--color-warning);
  flex-shrink: 0;
}

.item-cancel,
.item-reveal {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: var(--fs-label-sm);
  padding: 0 var(--space-1);
}

.item-cancel:hover {
  color: var(--color-danger);
}

.item-reveal:hover {
  color: var(--color-primary);
}
</style>

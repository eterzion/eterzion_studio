<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, RotateCcw, FolderOpen } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'
import { formatBytesDecimal } from '../../utils/formatBytes'
import type { CompressionHistoryEntry } from '../../services/compression'

// specs/008-compression-centre — T085: o histórico, e o botão de repetir.
//
// **"Repetir" parte do `settings_snapshot`, nunca do preset.** É a única coisa
// nesta tela que precisa ser dita duas vezes, porque a implementação errada é a
// natural: guardar o preset e relê-lo é menos código e parece equivalente. Falha
// quando alguém confia — comprimir cinquenta fotos com "Web leve", ajustar o
// preset na semana seguinte, e repetir uma entrada antiga produziria um
// resultado diferente do que a própria entrada exibe.

const props = defineProps<{ entries: CompressionHistoryEntry[] }>()

const emit = defineEmits<{
  repeat: [CompressionHistoryEntry]
  remove: [string]
  clear: []
  reveal: [string]
}>()

const { t, n } = useI18n()

interface Linha {
  entry: CompressionHistoryEntry
  original: number | null
  final: number | null
  percent: number | null
  grew: boolean
}

const rows = computed<Linha[]>(() =>
  props.entries.map((entry) => {
    const r = entry.result ?? {}
    const original = typeof r.original_bytes === 'number' ? r.original_bytes : null
    const final = typeof r.output_size_bytes === 'number' ? r.output_size_bytes : null
    const razao = typeof r.reduction_ratio === 'number' ? r.reduction_ratio : null
    return {
      entry,
      original,
      final,
      percent: razao === null ? null : Math.abs(Math.round(razao * 100)),
      grew: r.grew === true
    }
  })
)
</script>

<template>
  <section class="history" :aria-label="t('compression.history.title')">
    <header class="history-header">
      <span class="history-title">{{ t('compression.history.title') }}</span>
      <AppButton v-if="entries.length" variant="ghost" size="sm" @click="emit('clear')">
        {{ t('compression.history.clear') }}
      </AppButton>
    </header>

    <p v-if="!entries.length" class="history-empty">{{ t('compression.history.empty') }}</p>

    <ul v-else class="history-items">
      <li v-for="row in rows" :key="row.entry.id" class="history-item">
        <div class="item-main">
          <span class="item-name">{{ row.entry.display_name }}</span>
          <span v-if="row.original !== null && row.final !== null" class="item-sizes">
            {{ formatBytesDecimal(row.original) }} → {{ formatBytesDecimal(row.final) }}
            <span v-if="row.percent !== null" :class="{ warn: row.grew }">
              ({{ row.grew ? '+' : '−' }}{{ n(row.percent) }}%)
            </span>
          </span>
        </div>

        <div class="item-actions">
          <button
            type="button"
            class="item-action"
            :title="t('compression.history.repeatHint')"
            @click="emit('repeat', row.entry)"
          >
            <RotateCcw :size="13" />
            {{ t('compression.history.repeat') }}
          </button>
          <button
            v-if="row.entry.output_path"
            type="button"
            class="item-action"
            :title="t('compression.history.showInFolder', { name: row.entry.display_name })"
            :aria-label="t('compression.history.showInFolder', { name: row.entry.display_name })"
            @click="emit('reveal', row.entry.output_path!)"
          >
            <FolderOpen :size="13" />
          </button>
          <button
            type="button"
            class="item-action danger"
            :title="t('compression.history.remove', { name: row.entry.display_name })"
            @click="emit('remove', row.entry.id)"
          >
            <X :size="13" />
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.history {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.history-title {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.history-empty {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.history-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 240px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.item-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 1px;
}

.item-name {
  font-size: var(--fs-label-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-sizes {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.item-sizes .warn {
  color: var(--color-warning);
}

.item-actions {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.item-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px var(--space-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.item-action:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.item-action.danger:hover {
  color: var(--color-danger);
  border-color: var(--color-danger);
}
</style>

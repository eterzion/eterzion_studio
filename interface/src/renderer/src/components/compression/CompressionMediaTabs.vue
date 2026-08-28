<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { COMPRESSION_MEDIA_KINDS, type MediaKind } from '../../constants/compression'

// specs/008-compression-centre — T027.
//
// Itera o registro em vez de listar as quatro abas no template. FR-004 pede que
// acrescentar um tipo de mídia não obrigue a mexer nos existentes, e um template
// com quatro botões escritos à mão seria a primeira coisa a esquecer.

defineProps<{ modelValue: MediaKind; label: string }>()
defineEmits<{ 'update:modelValue': [MediaKind] }>()

const { t } = useI18n()
</script>

<template>
  <nav class="media-tabs" role="tablist" :aria-label="label">
    <button
      v-for="entry in COMPRESSION_MEDIA_KINDS"
      :key="entry.value"
      type="button"
      role="tab"
      class="media-tab"
      :class="{ active: modelValue === entry.value }"
      :aria-selected="modelValue === entry.value"
      @click="$emit('update:modelValue', entry.value)"
    >
      {{ t(entry.labelKey) }}
    </button>
  </nav>
</template>

<style scoped>
.media-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  align-self: flex-start;
}

.media-tab {
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.media-tab:hover {
  background: var(--surface-3);
  color: var(--text-primary);
}

.media-tab.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.media-tab:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
</style>

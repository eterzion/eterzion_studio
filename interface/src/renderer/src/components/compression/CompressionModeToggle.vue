<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { CompressionMode } from '../../constants/compression'

// specs/008-compression-centre — T028.
//
// Básico é o padrão, e isso não é estético: a condição 2 da exceção do Princípio
// V (constituição v4.0.0) exige que quem nunca abrir o Avançado jamais encontre
// um nome de codec. Este alternador é o lugar onde essa condição é visível — e o
// padrão vive em `constants/compression.ts`, não aqui, para que mudá-lo exija
// mexer no arquivo que diz por quê.

defineProps<{ modelValue: CompressionMode }>()
defineEmits<{ 'update:modelValue': [CompressionMode] }>()

const { t } = useI18n()
const MODES: CompressionMode[] = ['basic', 'advanced']
</script>

<template>
  <div class="mode-toggle" role="group" :aria-label="t('compression.mode.label')">
    <button
      v-for="value in MODES"
      :key="value"
      type="button"
      class="mode-option"
      :class="{ active: modelValue === value }"
      :aria-pressed="modelValue === value"
      @click="$emit('update:modelValue', value)"
    >
      {{ t(`compression.mode.${value}`) }}
    </button>
  </div>
</template>

<style scoped>
.mode-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
}

.mode-option {
  padding: var(--space-1) var(--space-2-5);
  border: none;
  border-radius: calc(var(--radius-sm) - 2px);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.mode-option:hover {
  color: var(--text-primary);
}

.mode-option.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.mode-option:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
</style>

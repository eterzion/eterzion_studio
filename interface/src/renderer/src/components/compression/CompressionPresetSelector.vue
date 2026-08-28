<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import type { CompressionPreset } from '../../services/compression'

// specs/008-compression-centre — T040.
//
// **Um preset interno tem chave de tradução; um do usuário tem a palavra que a
// pessoa escreveu.** Traduzir "Discord 8 MB" seria alterar o que ela nomeou, e
// é por isso que os dois campos existem separados no contrato em vez de um
// `name` que às vezes é chave.
//
// Escolher um preset **substitui** as configurações, e há um indicador para
// quando elas foram alteradas depois: um preset que continua selecionado
// enquanto os valores já são outros é uma afirmação falsa sobre o que vai
// acontecer.

const props = defineProps<{
  presets: CompressionPreset[]
  modelValue: string | null
  /** Verdadeiro quando as configurações mudaram depois de escolher o preset. */
  modified?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

const { t } = useI18n()

function label(preset: CompressionPreset): string {
  return preset.name_key ? t(preset.name_key) : (preset.name ?? preset.id)
}

const options = computed<SelectOption[]>(() => {
  const grupos: SelectOption[] = [{ value: '', label: t('compression.preset.custom') }]
  for (const preset of props.presets) {
    grupos.push({
      value: preset.id,
      label: label(preset),
      description: t(`compression.preset.origin.${preset.origin}`)
    })
  }
  return grupos
})

const selected = computed(() => props.modelValue ?? '')

function choose(value: string | number | null): void {
  emit('update:modelValue', value === '' || value === null ? null : String(value))
}
</script>

<template>
  <div class="preset-selector">
    <AppSelect
      :model-value="selected"
      :options="options"
      :disabled="disabled"
      :placeholder="t('compression.preset.placeholder')"
      @update:model-value="choose"
    />
    <p v-if="modified && modelValue" class="preset-modified">
      {{ t('compression.preset.modified') }}
    </p>
  </div>
</template>

<style scoped>
.preset-selector {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.preset-modified {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

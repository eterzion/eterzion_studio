<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ref } from 'vue'
import { Save, Copy, Trash2 } from '@lucide/vue'
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

const emit = defineEmits<{
  'update:modelValue': [string | null]
  save: [string]
  duplicate: [{ id: string; name: string }]
  remove: [string]
}>()

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

/** O preset escolhido, quando é do usuário. Só esses aceitam escrita — tentar
 *  alterar um interno responde 409 no backend, e oferecer o botão aqui seria
 *  prometer o que a API recusa (FR-014). */
const ownPreset = computed(
  () => props.presets.find((p) => p.id === props.modelValue && p.origin === 'user') ?? null
)

const naming = ref(false)
const draftName = ref('')

function startSaving(): void {
  naming.value = true
  draftName.value = ownPreset.value?.name ?? ''
}

function confirmSave(): void {
  const nome = draftName.value.trim()
  // Um nome vazio criaria um preset que a pessoa não consegue distinguir dos
  // outros na lista. Não é erro — é só não salvar ainda.
  if (!nome) return
  naming.value = false
  emit('save', nome)
}

function duplicate(): void {
  const atual = props.presets.find((p) => p.id === props.modelValue)
  if (!atual) return
  const base = atual.name_key ? t(atual.name_key) : (atual.name ?? '')
  emit('duplicate', { id: atual.id, name: t('compression.preset.copyOf', { name: base }) })
}

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

    <div v-if="naming" class="preset-naming">
      <input
        v-model="draftName"
        type="text"
        class="preset-name-input"
        :placeholder="t('compression.preset.namePlaceholder')"
        :aria-label="t('compression.preset.namePlaceholder')"
        @keyup.enter="confirmSave"
        @keyup.escape="naming = false"
      />
      <button
        type="button"
        class="preset-action"
        :disabled="!draftName.trim()"
        @click="confirmSave"
      >
        {{ t('compression.preset.confirmSave') }}
      </button>
      <button type="button" class="preset-action" @click="naming = false">
        {{ t('compression.preset.cancel') }}
      </button>
    </div>

    <div v-else class="preset-actions">
      <button type="button" class="preset-action" :disabled="disabled" @click="startSaving">
        <Save :size="12" />
        {{ ownPreset ? t('compression.preset.update') : t('compression.preset.saveAs') }}
      </button>
      <button
        v-if="modelValue"
        type="button"
        class="preset-action"
        :disabled="disabled"
        @click="duplicate"
      >
        <Copy :size="12" />
        {{ t('compression.preset.duplicate') }}
      </button>
      <button
        v-if="ownPreset"
        type="button"
        class="preset-action danger"
        :disabled="disabled"
        @click="emit('remove', ownPreset.id)"
      >
        <Trash2 :size="12" />
        {{ t('compression.preset.delete') }}
      </button>
    </div>
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

.preset-actions,
.preset-naming {
  display: flex;
  gap: var(--space-1);
  align-items: center;
}

.preset-name-input {
  flex: 1;
  min-width: 0;
  padding: var(--space-1) var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-label-sm);
}

.preset-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.preset-action:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.preset-action.danger:hover:not(:disabled) {
  color: var(--color-danger);
  border-color: var(--color-danger);
}

.preset-action:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>

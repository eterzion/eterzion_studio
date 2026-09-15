<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderOpen } from '@lucide/vue'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import AppButton from '../atoms/AppButton.vue'
import SettingRow from '../SettingRow.vue'
import { api, hasNativeApi } from '../../services/native'
import { getCapabilities, type CapabilityEntry } from '../../services/compression'
import type { ConflictMode, Profile } from '../../services/api'

// A exportacao do Audio, com as regras dos outros modos (app/destino.py): a
// pasta padrao das Configuracoes, o nome do original, "Se ja' existir".
//
// O formato vem das capacidades desta maquina -- o mesmo levantamento da
// Compressao, porque a codificacao e' a mesma. A qualidade so' aparece em
// formato com perda: em WAV e FLAC nao ha' bitrate a escolher, e um controle
// que nao faz nada e' pior que a sua ausencia.

export interface AudioExport {
  /** 'keep' = o formato do original. */
  format: string
  profile: Profile
  directory: string | null
  /** Sem extensao; `null` = o nome do original. Vale para o arquivo ativo. */
  filename: string | null
  conflict: ConflictMode
}

const FORMATOS = ['wav', 'flac', 'mp3', 'm4a', 'ogg', 'opus'] as const
const SEM_PERDA = new Set(['wav', 'flac'])

const props = defineProps<{
  modelValue: AudioExport
  /** Nome do arquivo ativo: o exemplo do campo de nome e o formato de "Mesmo do original". */
  sourceName: string | null
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [AudioExport] }>()

const { t } = useI18n()

const disponiveis = ref<CapabilityEntry[] | null>(null)
onMounted(async () => {
  try {
    disponiveis.value = (await getCapabilities()).audio.formats
  } catch {
    // Sem a lista, tudo fica oferecido: a recusa vem do backend, antes do job.
    disponiveis.value = null
  }
})

const extensaoDoOriginal = computed(
  () => /\.([^.]+)$/.exec(props.sourceName ?? '')?.[1]?.toLowerCase() ?? ''
)

const formatoEfetivo = computed(() =>
  props.modelValue.format === 'keep' ? extensaoDoOriginal.value : props.modelValue.format
)

const comPerda = computed(() => !!formatoEfetivo.value && !SEM_PERDA.has(formatoEfetivo.value))

const formatOptions = computed<SelectOption[]>(() => [
  { value: 'keep', label: t('audio.export.keep') },
  ...FORMATOS.map((f) => {
    const entrada = disponiveis.value?.find((d) => d.value === f)
    const indisponivel = !!entrada && !entrada.available
    return {
      value: f,
      label: f.toUpperCase(),
      disabled: indisponivel,
      description: indisponivel ? t('audio.export.refusal.encoder_unavailable') : undefined
    }
  })
])

const qualityOptions = computed<SelectOption[]>(() =>
  (['fast', 'balanced', 'quality'] as const).map((p) => ({
    value: p,
    label: t(`audio.export.quality.${p}`)
  }))
)

const conflictOptions = computed<SelectOption[]>(() => [
  { value: 'rename', label: t('destination.conflict.rename') },
  { value: 'overwrite', label: t('destination.conflict.overwrite') },
  { value: 'ask', label: t('destination.conflict.ask') }
])

const namePlaceholder = computed(() => {
  if (!props.sourceName) return ''
  const base = props.sourceName.replace(/\.[^.]+$/, '')
  return formatoEfetivo.value ? `${base}.${formatoEfetivo.value}` : base
})

function patch(mudanca: Partial<AudioExport>): void {
  emit('update:modelValue', { ...props.modelValue, ...mudanca })
}

async function chooseDirectory(): Promise<void> {
  if (!hasNativeApi) return
  const escolhido = await api.selectOutputFolder(props.modelValue.directory ?? undefined)
  // Cancelar mantem a pasta que estava.
  if (escolhido) patch({ directory: escolhido })
}
</script>

<template>
  <div class="export-panel">
    <SettingRow :label="t('audio.export.format')">
      <AppSelect
        :model-value="modelValue.format"
        :options="formatOptions"
        :disabled="disabled"
        @update:model-value="patch({ format: String($event) })"
      />
    </SettingRow>

    <SettingRow v-if="comPerda" :label="t('audio.export.qualityLabel')">
      <AppSelect
        :model-value="modelValue.profile"
        :options="qualityOptions"
        :disabled="disabled"
        @update:model-value="patch({ profile: $event as Profile })"
      />
    </SettingRow>

    <SettingRow :label="t('audio.export.destination')">
      <AppButton variant="outline" size="sm" :disabled="disabled" @click="chooseDirectory">
        <template #icon><FolderOpen :size="14" /></template>
        {{ modelValue.directory ?? t('audio.export.sameFolder') }}
      </AppButton>
    </SettingRow>

    <SettingRow :label="t('destination.fileName')">
      <input
        class="name-input"
        type="text"
        :placeholder="namePlaceholder"
        :value="modelValue.filename ?? ''"
        :disabled="disabled"
        :aria-label="t('destination.fileName')"
        @input="patch({ filename: ($event.target as HTMLInputElement).value.trim() || null })"
      />
    </SettingRow>

    <SettingRow :label="t('destination.onConflict')">
      <AppSelect
        :model-value="modelValue.conflict"
        :options="conflictOptions"
        :disabled="disabled"
        @update:model-value="patch({ conflict: $event as ConflictMode })"
      />
    </SettingRow>
  </div>
</template>

<style scoped>
.export-panel {
  display: flex;
  flex-direction: column;
}

/* O mesmo campo do padrao de nome da Compressao (CompressionExportPanel.vue). */
.name-input {
  width: min(180px, 100%);
  min-width: 0;
  padding: var(--space-1) var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.name-input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
</style>

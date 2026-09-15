<script setup lang="ts">
import { AudioWaveform, FileType, Wrench } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import SliderField from '../SliderField.vue'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import TargetSizeControl from './TargetSizeControl.vue'
import type {
  CompressionCapabilities,
  CompressionSettings,
  SizeTarget
} from '../../services/compression'
import type { CompressionMode } from '../../constants/compression'

// specs/008-compression-centre — T066.
//
// **Formato sem perda não mostra controle de bitrate** (FR-033), e o controle
// não é desabilitado: ele não existe. Um slider cinza sugere que há algo a
// destravar; a ausência diz a verdade, que é "para este formato o tamanho vem do
// conteúdo".
//
// **`Como no original` é o padrão da taxa de amostragem e dos canais** (FR-034).
// Reamostrar é conversão com perda, e rebaixar estéreo para mono é uma escolha —
// fazer qualquer uma delas sozinho seria alterar a mídia por conta própria.

const props = defineProps<{
  settings: CompressionSettings
  target: SizeTarget | null
  mode: CompressionMode
  capabilities: CompressionCapabilities | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  set: [field: string, value: unknown]
  'update:target': [SizeTarget | null]
}>()

const { t } = useI18n()

/** Formatos cujo **todo** codec é sem perda. Espelha `lossless_format` de
 *  `app/compression/audio.py`; a lista curta vive aqui porque a interface
 *  precisa da resposta antes de qualquer chamada. */
const LOSSLESS_FORMATS = new Set(['wav', 'flac'])

const format = computed(() => String(props.settings.output_format ?? 'auto'))
const lossless = computed(() => LOSSLESS_FORMATS.has(format.value))
const quality = computed(() => Number(props.settings.quality ?? 70))

const formatOptions = computed<SelectOption[]>(() => {
  const entradas = props.capabilities?.audio.formats ?? []
  return [
    { value: 'auto', label: t('compression.audio.auto') },
    ...entradas.map((entrada) => ({
      value: entrada.value,
      label: entrada.value.toUpperCase(),
      disabled: !entrada.available,
      description: entrada.available
        ? LOSSLESS_FORMATS.has(entrada.value)
          ? t('compression.audio.losslessTag')
          : undefined
        : t(`compression.unavailable.${entrada.unavailable_reason ?? 'no_encoder_available'}`)
    }))
  ]
})

const SAMPLE_RATES = ['original', '48000', '44100', '32000', '22050']
const sampleRateOptions = computed<SelectOption[]>(() =>
  SAMPLE_RATES.map((r) => ({
    value: r,
    label: r === 'original' ? t('compression.audio.sameAsSource') : `${Number(r) / 1000} kHz`
  }))
)

const channelOptions = computed<SelectOption[]>(() => [
  { value: 'original', label: t('compression.audio.sameAsSource') },
  { value: '2', label: t('compression.audio.stereo') },
  {
    value: '1',
    label: t('compression.audio.mono'),
    description: t('compression.audio.monoHint')
  }
])

const bitrateModeOptions = computed<SelectOption[]>(() => [
  {
    value: 'cbr',
    label: t('compression.audio.cbr'),
    description: t('compression.audio.cbrHint')
  },
  {
    value: 'vbr',
    label: t('compression.audio.vbr'),
    description: t('compression.audio.vbrHint')
  }
])

/** Os degraus que as pessoas de fato usam — os mesmos do backend. Interpolar
 *  produziria 187 kbps, um número que nenhum player exibe de forma
 *  reconhecível. */
const qualityHint = computed(() => {
  const q = quality.value
  if (q >= 90) return t('compression.audio.qualityHint.maximum')
  if (q >= 70) return t('compression.audio.qualityHint.high')
  if (q >= 45) return t('compression.audio.qualityHint.balanced')
  if (q >= 25) return t('compression.audio.qualityHint.small')
  return t('compression.audio.qualityHint.minimum')
})

function set(field: string, value: unknown): void {
  emit('set', field, value)
}

/** `original` viaja como a palavra; um número viaja como número. O backend
 *  distingue os dois, e mandar `"44100"` como texto o obrigaria a adivinhar. */
function setNumericOrOriginal(field: string, value: unknown): void {
  set(field, value === 'original' ? 'original' : Number(value))
}
</script>

<template>
  <div class="audio-settings">
    <CollapsiblePanel
      :title="t('compression.audio.output')"
      :description="t('compression.audio.outputDescription')"
      :icon="FileType"
    >
      <SettingRow :label="t('compression.audio.format')">
        <AppSelect
          :model-value="format"
          :options="formatOptions"
          :disabled="disabled"
          @update:model-value="set('output_format', $event)"
        />
      </SettingRow>

      <!-- Sem perda não tem qualidade a escolher, e o controle não fica cinza:
           ele não existe. Um slider desabilitado sugeriria algo a destravar. -->
      <SliderField
        v-if="!lossless"
        :label="t('compression.audio.quality')"
        :model-value="quality"
        :min="1"
        :max="100"
        :hint="qualityHint"
        :disabled="disabled"
        @update:model-value="set('quality', $event)"
      />
      <p v-else class="lossless-note">{{ t('compression.audio.losslessNote') }}</p>

      <TargetSizeControl
        v-if="!lossless"
        :model-value="target"
        :disabled="disabled"
        @update:model-value="emit('update:target', $event)"
      />
    </CollapsiblePanel>

    <CollapsiblePanel
      :title="t('compression.audio.signal')"
      :description="t('compression.audio.signalDescription')"
      :icon="AudioWaveform"
      :default-open="false"
    >
      <SettingRow
        :label="t('compression.audio.sampleRate')"
        :description="t('compression.audio.sampleRateHint')"
      >
        <AppSelect
          :model-value="String(settings.sample_rate ?? 'original')"
          :options="sampleRateOptions"
          :disabled="disabled"
          @update:model-value="setNumericOrOriginal('sample_rate', $event)"
        />
      </SettingRow>

      <SettingRow :label="t('compression.audio.channels')" :divided="false">
        <AppSelect
          :model-value="String(settings.channels ?? 'original')"
          :options="channelOptions"
          :disabled="disabled"
          @update:model-value="setNumericOrOriginal('channels', $event)"
        />
      </SettingRow>
    </CollapsiblePanel>

    <CollapsiblePanel
      v-if="mode === 'advanced' && !lossless"
      :title="t('compression.audio.advanced')"
      :description="t('compression.audio.advancedDescription')"
      :icon="Wrench"
      :default-open="false"
    >
      <SettingRow
        :label="t('compression.audio.bitrateMode')"
        :description="t('compression.audio.bitrateModeHint')"
        :divided="false"
      >
        <AppSelect
          :model-value="String(settings.bitrate_mode ?? 'cbr')"
          :options="bitrateModeOptions"
          :disabled="disabled"
          @update:model-value="set('bitrate_mode', $event)"
        />
      </SettingRow>
    </CollapsiblePanel>
  </div>
</template>

<style scoped>
.audio-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.lossless-note {
  margin: var(--space-1) 0 var(--space-2);
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

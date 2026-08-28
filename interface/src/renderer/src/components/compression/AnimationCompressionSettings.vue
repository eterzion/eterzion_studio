<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import SliderField from '../SliderField.vue'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import TargetSizeControl from './TargetSizeControl.vue'
import type {
  CompressionCapabilities,
  CompressionSettings,
  SizeTarget
} from '../../services/compression'
import type { CompressionMode } from '../../constants/compression'

// specs/008-compression-centre — T074.
//
// **Um GIF não tem "qualidade" como um JPEG tem.** Ele guarda uma paleta de até
// 256 cores e índices para ela, e comprimi-lo é escolher quais cores ficam. Por
// isso o controle principal aqui é o número de cores, e não um slider genérico:
// nomear a coisa certa é o que permite à pessoa entender por que o resultado
// mudou daquele jeito.
//
// **Converter para vídeo troca de domínio.** GIF → MP4/WebM sai da paleta e
// entra em codecs, e os controles de cor e dithering deixam de existir — não
// ficam cinza. Um controle que não se aplica ao formato escolhido não é uma
// opção desabilitada; é uma opção que não existe naquele formato.

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

const format = computed(() => String(props.settings.output_format ?? 'gif'))

/** Formatos que ainda são "animação com paleta". WebP animado não usa paleta,
 *  mas mantém o vocabulário de quadros e cores para quem vem do GIF. */
const PALETTE_FORMATS = new Set(['gif'])
const usesPalette = computed(() => PALETTE_FORMATS.has(format.value))
const isVideo = computed(() => format.value === 'mp4' || format.value === 'webm')

const formatOptions = computed<SelectOption[]>(() => {
  const entradas = props.capabilities?.animation.formats ?? []
  return entradas.map((entrada) => ({
    value: entrada.value,
    label: entrada.value.toUpperCase(),
    disabled: !entrada.available,
    description: entrada.available
      ? entrada.value === 'gif'
        ? undefined
        : t(`compression.animation.formatHint.${entrada.value}`)
      : t(`compression.unavailable.${entrada.unavailable_reason ?? 'no_encoder_available'}`)
  }))
})

const DITHERS = ['bayer', 'none', 'floyd_steinberg', 'sierra2_4a']
const ditherOptions = computed<SelectOption[]>(() =>
  DITHERS.map((d) => ({
    value: d,
    label: t(`compression.animation.dither.${d}`),
    description: t(`compression.animation.ditherHint.${d}`)
  }))
)

const FPS = ['original', '24', '15', '12', '10', '8']
const fpsOptions = computed<SelectOption[]>(() =>
  FPS.map((f) => ({
    value: f,
    label: f === 'original' ? t('compression.animation.sameAsSource') : `${f} fps`
  }))
)

const RESOLUTIONS = ['original', '1080p', '720p', '480p']
const resolutionOptions = computed<SelectOption[]>(() =>
  RESOLUTIONS.map((r) => ({
    value: r,
    label: r === 'original' ? t('compression.animation.sameAsSource') : r.toUpperCase()
  }))
)

const colors = computed(() => {
  const valor = props.settings.max_colors
  if (valor === undefined || valor === null || valor === 'auto') return null
  return Number(valor)
})

const quality = computed(() => Number(props.settings.quality ?? 70))

function set(field: string, value: unknown): void {
  emit('set', field, value)
}
</script>

<template>
  <div class="animation-settings">
    <CollapsiblePanel :title="t('compression.animation.output')">
      <SettingRow :label="t('compression.animation.format')">
        <AppSelect
          :model-value="format"
          :options="formatOptions"
          :disabled="disabled"
          @update:model-value="set('output_format', $event)"
        />
      </SettingRow>

      <SliderField
        :label="t('compression.animation.quality')"
        :model-value="quality"
        :min="1"
        :max="100"
        :hint="
          usesPalette
            ? t('compression.animation.qualityHintPalette')
            : t('compression.animation.qualityHintCodec')
        "
        :disabled="disabled"
        @update:model-value="set('quality', $event)"
      />

      <p v-if="isVideo" class="format-note">{{ t('compression.animation.videoNote') }}</p>
    </CollapsiblePanel>

    <!-- Cores e dithering só existem onde há paleta. Num MP4 eles não estão
         desabilitados: não fazem parte do formato. -->
    <CollapsiblePanel v-if="usesPalette" :title="t('compression.animation.palette')">
      <SettingRow
        :label="t('compression.animation.autoColors')"
        :description="t('compression.animation.autoColorsHint')"
        :divided="colors === null"
      >
        <SettingSwitch
          :model-value="colors === null"
          :disabled="disabled"
          @update:model-value="set('max_colors', $event ? 'auto' : 128)"
        />
      </SettingRow>

      <SliderField
        v-if="colors !== null"
        :label="t('compression.animation.colors')"
        :model-value="colors"
        :min="2"
        :max="256"
        :hint="t('compression.animation.colorsHint')"
        :disabled="disabled"
        @update:model-value="set('max_colors', $event)"
      />

      <SettingRow
        v-if="mode === 'advanced'"
        :label="t('compression.animation.ditherLabel')"
        :description="t('compression.animation.ditherDescription')"
        :divided="false"
      >
        <AppSelect
          :model-value="String(settings.dither ?? 'bayer')"
          :options="ditherOptions"
          :disabled="disabled"
          @update:model-value="set('dither', $event)"
        />
      </SettingRow>
    </CollapsiblePanel>

    <CollapsiblePanel :title="t('compression.animation.size')">
      <SettingRow :label="t('compression.animation.resolution')">
        <AppSelect
          :model-value="String(settings.resolution ?? 'original')"
          :options="resolutionOptions"
          :disabled="disabled"
          @update:model-value="set('resolution', $event)"
        />
      </SettingRow>

      <SettingRow
        :label="t('compression.animation.fps')"
        :description="t('compression.animation.fpsHint')"
      >
        <AppSelect
          :model-value="String(settings.fps ?? 'original')"
          :options="fpsOptions"
          :disabled="disabled"
          @update:model-value="set('fps', $event === 'original' ? 'original' : Number($event))"
        />
      </SettingRow>

      <TargetSizeControl
        :model-value="target"
        :disabled="disabled"
        @update:model-value="emit('update:target', $event)"
      />
    </CollapsiblePanel>
  </div>
</template>

<style scoped>
.animation-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.format-note {
  margin: var(--space-1) 0 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

<script setup lang="ts">
import { Expand, FileType, Tags, Wrench } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import SliderField from '../SliderField.vue'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import TargetSizeControl from './TargetSizeControl.vue'
import type { CapabilityEntry, CompressionSettings, SizeTarget } from '../../services/compression'
import type { CompressionMode } from '../../constants/compression'

// specs/008-compression-centre — T038 (Básico) e T039 (Avançado).
//
// Duas regras carregam este arquivo:
//
// **Os controles do Avançado mudam com o formato, em vez de ficarem presentes e
// desabilitados** (FR-029). Um "nível de compressão PNG" cinza ao lado de um
// JPEG selecionado não informa nada e ocupa a atenção que o controle útil
// precisaria; pior, sugere que existe algo a destravar.
//
// **A qualidade tem descrição, não só número** (FR-025). "70" não diz nada a
// quem não comprime imagem por profissão; "boa para web, diferença difícil de
// notar" diz. O número continua ali para quem o quer.
//
// O modo Básico não mostra nenhum campo técnico, e isso é constitucional (a
// condição 2 da exceção do Princípio V): quem nunca abrir o Avançado não pode
// encontrar chroma, effort nem nível de compressão.

const props = defineProps<{
  settings: CompressionSettings
  target: SizeTarget | null
  mode: CompressionMode
  /** O que esta máquina consegue gravar. Um formato indisponível aparece
   *  desabilitado **com o motivo**, em vez de sumir: sumir faria a pessoa
   *  procurar o que ela sabe que existe (FR-043). */
  formats: CapabilityEntry[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  set: [field: string, value: unknown]
  'update:target': [SizeTarget | null]
}>()

const { t } = useI18n()

const format = computed(() => String(props.settings.output_format ?? 'keep'))
const quality = computed(() => Number(props.settings.quality ?? 80))
const lossless = computed(() => Boolean(props.settings.lossless))

/** Formatos sem perda não têm qualidade a ajustar, e um slider que não faz nada
 *  é pior que a ausência dele — a pessoa arrasta e conclui que o produto ignorou
 *  o que ela pediu. */
const LOSSLESS_ONLY = new Set(['png', 'bmp', 'tiff'])
const LOSSLESS_CAPABLE = new Set(['png', 'bmp', 'tiff', 'webp'])

const hasQuality = computed(() => !LOSSLESS_ONLY.has(format.value) && !lossless.value)
const canBeLossless = computed(() => LOSSLESS_CAPABLE.has(format.value))

const formatOptions = computed<SelectOption[]>(() => [
  { value: 'keep', label: t('compression.image.format.keep') },
  ...props.formats.map((entrada) => ({
    value: entrada.value,
    label: entrada.value.toUpperCase(),
    disabled: !entrada.available,
    description: entrada.available
      ? undefined
      : t(`compression.unavailable.${entrada.unavailable_reason ?? 'no_encoder_available'}`)
  }))
])

const RESOLUTIONS = ['original', '4k', '1440p', '1080p', '720p', '480p']
const resolutionOptions = computed<SelectOption[]>(() =>
  RESOLUTIONS.map((r) => ({
    value: r,
    label: r === 'original' ? t('compression.image.resolution.original') : r.toUpperCase()
  }))
)

const METADATA_POLICIES = [
  'preserve_all',
  'essential_only',
  'strip_exif',
  'strip_gps',
  'strip_comments',
  'strip_icc',
  'strip_all'
]
const metadataOptions = computed<SelectOption[]>(() =>
  METADATA_POLICIES.map((p) => ({
    value: p,
    label: t(`compression.image.metadata.${p}`),
    description: t(`compression.image.metadataHint.${p}`)
  }))
)

/** A descrição que acompanha o número (FR-025). Os degraus são os que a
 *  diferença visível de fato tem — não terços iguais. */
const qualityHint = computed(() => {
  const q = quality.value
  if (q >= 95) return t('compression.image.qualityHint.maximum')
  if (q >= 80) return t('compression.image.qualityHint.high')
  if (q >= 60) return t('compression.image.qualityHint.balanced')
  if (q >= 40) return t('compression.image.qualityHint.small')
  return t('compression.image.qualityHint.minimum')
})

function set(field: string, value: unknown): void {
  emit('set', field, value)
}
</script>

<template>
  <div class="image-settings">
    <CollapsiblePanel
      :title="t('compression.image.output')"
      :description="t('compression.image.outputDescription')"
      :icon="FileType"
    >
      <SettingRow :label="t('compression.image.format.label')">
        <AppSelect
          :model-value="format"
          :options="formatOptions"
          :disabled="disabled"
          @update:model-value="set('output_format', $event)"
        />
      </SettingRow>

      <SettingRow
        v-if="canBeLossless"
        :label="t('compression.image.lossless')"
        :description="t('compression.image.losslessHint')"
        :divided="!hasQuality"
      >
        <SettingSwitch
          :model-value="lossless"
          :disabled="disabled"
          @update:model-value="set('lossless', $event)"
        />
      </SettingRow>

      <SliderField
        v-if="hasQuality"
        :label="t('compression.image.quality')"
        :model-value="quality"
        :min="1"
        :max="100"
        :hint="qualityHint"
        :disabled="disabled"
        @update:model-value="set('quality', $event)"
      />
    </CollapsiblePanel>

    <CollapsiblePanel
      :title="t('compression.image.size')"
      :description="t('compression.image.sizeDescription')"
      :icon="Expand"
    >
      <SettingRow :label="t('compression.image.resolution.label')">
        <AppSelect
          :model-value="String(settings.resolution ?? 'original')"
          :options="resolutionOptions"
          :disabled="disabled"
          @update:model-value="set('resolution', $event)"
        />
      </SettingRow>

      <SettingRow
        :label="t('compression.image.preventUpscale')"
        :description="t('compression.image.preventUpscaleHint')"
      >
        <SettingSwitch
          :model-value="settings.prevent_upscale !== false"
          :disabled="disabled"
          @update:model-value="set('prevent_upscale', $event)"
        />
      </SettingRow>

      <TargetSizeControl
        :model-value="target"
        :disabled="disabled"
        @update:model-value="emit('update:target', $event)"
      />
    </CollapsiblePanel>

    <CollapsiblePanel
      :title="t('compression.image.metadataTitle')"
      :description="t('compression.image.metadataDescription')"
      :icon="Tags"
      :default-open="false"
    >
      <SettingRow
        :label="t('compression.image.metadataPolicy')"
        :description="t('compression.image.metadataPolicyHint')"
      >
        <AppSelect
          :model-value="String(settings.metadata_policy ?? 'essential_only')"
          :options="metadataOptions"
          :disabled="disabled"
          @update:model-value="set('metadata_policy', $event)"
        />
      </SettingRow>
    </CollapsiblePanel>

    <!-- Só no Avançado, e só o que vale para o formato escolhido (FR-029). -->
    <CollapsiblePanel
      v-if="mode === 'advanced' && format !== 'keep'"
      :title="t('compression.image.advanced')"
      :description="t('compression.image.advancedDescription')"
      :icon="Wrench"
      :default-open="false"
    >
      <template v-if="format === 'png'">
        <SliderField
          :label="t('compression.image.pngLevel')"
          :model-value="Number(settings.png_compress_level ?? 6)"
          :min="0"
          :max="9"
          :hint="t('compression.image.pngLevelHint')"
          :disabled="disabled"
          @update:model-value="set('png_compress_level', $event)"
        />
      </template>

      <template v-else-if="format === 'jpeg'">
        <SettingRow
          :label="t('compression.image.chroma')"
          :description="t('compression.image.chromaHint')"
        >
          <AppSelect
            :model-value="String(settings.chroma_subsampling ?? '4:2:0')"
            :options="[
              { value: '4:4:4', label: '4:4:4' },
              { value: '4:2:2', label: '4:2:2' },
              { value: '4:2:0', label: '4:2:0' }
            ]"
            :disabled="disabled"
            @update:model-value="set('chroma_subsampling', $event)"
          />
        </SettingRow>
        <SettingRow
          :label="t('compression.image.progressive')"
          :description="t('compression.image.progressiveHint')"
        >
          <SettingSwitch
            :model-value="Boolean(settings.progressive)"
            :disabled="disabled"
            @update:model-value="set('progressive', $event)"
          />
        </SettingRow>
      </template>

      <template v-else-if="format === 'webp'">
        <SliderField
          :label="t('compression.image.effort')"
          :model-value="Number(settings.effort ?? 4)"
          :min="0"
          :max="6"
          :hint="t('compression.image.effortHint')"
          :disabled="disabled"
          @update:model-value="set('effort', $event)"
        />
      </template>

      <template v-else-if="format === 'avif'">
        <SliderField
          :label="t('compression.image.speed')"
          :model-value="Number(settings.speed ?? 6)"
          :min="0"
          :max="10"
          :hint="t('compression.image.speedHint')"
          :disabled="disabled"
          @update:model-value="set('speed', $event)"
        />
      </template>

      <p v-else class="no-advanced">{{ t('compression.image.noAdvanced') }}</p>
    </CollapsiblePanel>
  </div>
</template>

<style scoped>
.image-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.no-advanced {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

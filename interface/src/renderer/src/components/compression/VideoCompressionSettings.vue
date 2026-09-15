<script setup lang="ts">
import { Expand, FileType, Music, Wrench } from '@lucide/vue'
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

// specs/008-compression-centre — T058/T060.
//
// **Um formato indisponível aparece desabilitado com o motivo, em vez de sumir**
// (FR-043/FR-044). Sumir faria a pessoa procurar o que ela sabe que existe e
// concluir que o produto não faz; dizer "precisa de aceleração de vídeo que esta
// máquina não tem" é verdadeiro, acionável, e não nomeia nenhum encoder
// (Princípio V).
//
// Este é o caso concreto nesta build: H.264 e H.265 vêm de encoders de hardware
// porque as bibliotecas por software para eles são GPL e incompatíveis com o
// licenciamento do aplicativo. Onde não há hardware, WebM e MKV são o que a
// Central oferece — e a interface diz por quê em vez de esconder.
//
// **A qualidade tem interpretação visual, não só número** (§16). "CRF 23" não
// significa nada para quem não codifica vídeo por profissão; "praticamente
// idêntico ao original, arquivo maior" significa.

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

const container = computed(() => String(props.settings.container ?? 'auto'))
const videoCodec = computed(() => String(props.settings.video_codec ?? 'auto'))
const audioMode = computed(() => String(props.settings.audio_mode ?? 'keep'))
const quality = computed(() => Number(props.settings.quality ?? 70))

const video = computed(() => props.capabilities?.video ?? null)

function entryOptions(
  entries: { value: string; available: boolean; unavailable_reason: string | null }[],
  incluirAuto: boolean
): SelectOption[] {
  const opcoes: SelectOption[] = incluirAuto
    ? [{ value: 'auto', label: t('compression.video.auto') }]
    : []
  for (const entrada of entries) {
    opcoes.push({
      value: entrada.value,
      label: entrada.value.toUpperCase(),
      disabled: !entrada.available,
      description: entrada.available
        ? undefined
        : t(`compression.unavailable.${entrada.unavailable_reason ?? 'no_encoder_available'}`)
    })
  }
  return opcoes
}

const containerOptions = computed(() => entryOptions(video.value?.containers ?? [], true))

/** Os codecs que **este container** aceita, e não todos. Oferecer H.264 com WebM
 *  escolhido seria oferecer uma combinação que não existe (FR-046) — e a recusa
 *  chegaria depois de a pessoa montar o resto. */
const videoCodecOptions = computed(() => {
  const todos = video.value?.video_codecs ?? []
  const permitidos =
    props.settings.container && container.value !== 'auto'
      ? video.value?.compatibility?.[container.value]?.video
      : undefined
  return entryOptions(permitidos ? todos.filter((c) => permitidos.includes(c.value)) : todos, true)
})

const audioCodecOptions = computed(() => {
  const todos = video.value?.audio_codecs ?? []
  const permitidos =
    props.settings.container && container.value !== 'auto'
      ? video.value?.compatibility?.[container.value]?.audio
      : undefined
  return entryOptions(permitidos ? todos.filter((c) => permitidos.includes(c.value)) : todos, true)
})

/** Aceleração: Automático, CPU ou GPU (FR-047).
 *
 *  O automático prefere **qualidade e compatibilidade** a velocidade (FR-048) —
 *  a um mesmo tamanho o encoder por software produz imagem melhor. Pedir GPU
 *  numa máquina sem GPU utilizável não é erro: cai para CPU, porque recusar o
 *  trabalho trocaria um arquivo mais lento por nenhum arquivo. */
const encoderOptions = computed<SelectOption[]>(() => [
  {
    value: 'auto',
    label: t('compression.video.encoder.auto'),
    description: t('compression.video.encoder.autoHint')
  },
  { value: 'cpu', label: t('compression.video.encoder.cpu') },
  {
    value: 'gpu',
    label: t('compression.video.encoder.gpu'),
    description: video.value?.hardware.available
      ? undefined
      : t('compression.video.encoder.noHardware')
  }
])

const RESOLUTIONS = ['original', '4k', '1440p', '1080p', '720p', '480p']
const resolutionOptions = computed<SelectOption[]>(() =>
  RESOLUTIONS.map((r) => ({
    value: r,
    label: r === 'original' ? t('compression.video.sameAsSource') : r.toUpperCase()
  }))
)

const FPS = ['original', '60', '30', '24']
const fpsOptions = computed<SelectOption[]>(() =>
  FPS.map((f) => ({
    value: f,
    label: f === 'original' ? t('compression.video.sameAsSource') : `${f} fps`
  }))
)

const audioModeOptions = computed<SelectOption[]>(() => [
  {
    value: 'keep',
    label: t('compression.video.audio.keep'),
    description: t('compression.video.audio.keepHint')
  },
  { value: 'recompress', label: t('compression.video.audio.recompress') },
  {
    value: 'remove',
    label: t('compression.video.audio.remove'),
    description: t('compression.video.audio.removeHint')
  }
])

const speedOptions = computed<SelectOption[]>(() => [
  { value: 'auto', label: t('compression.video.auto') },
  {
    value: 'slow',
    label: t('compression.video.speed.slow'),
    description: t('compression.video.speed.slowHint')
  },
  { value: 'medium', label: t('compression.video.speed.medium') },
  {
    value: 'fast',
    label: t('compression.video.speed.fast'),
    description: t('compression.video.speed.fastHint')
  }
])

/** A interpretação visual do §16: o que o número significa para os olhos. */
const qualityHint = computed(() => {
  const q = quality.value
  if (q >= 90) return t('compression.video.qualityHint.maximum')
  if (q >= 75) return t('compression.video.qualityHint.high')
  if (q >= 55) return t('compression.video.qualityHint.balanced')
  if (q >= 35) return t('compression.video.qualityHint.small')
  return t('compression.video.qualityHint.minimum')
})

/** Aviso honesto e não alarme: dizer que nenhum formato precisa de hardware está
 *  disponível é diferente de dizer que a máquina é incapaz. */
const noHardware = computed(() => video.value !== null && !video.value.hardware.available)

function set(field: string, value: unknown): void {
  emit('set', field, value)
}
</script>

<template>
  <div class="video-settings">
    <CollapsiblePanel
      :title="t('compression.video.output')"
      :description="t('compression.video.outputDescription')"
      :icon="FileType"
    >
      <!-- So' no Avancado. O container e' campo tecnico: o modo Basico nao o
           envia (condicao 2 da excecao do Principio V, conferida no backend).
           Mostrado aqui, a pessoa escolhia WebM e recebia o formato original,
           sem aviso -- um controle que parecia funcionar e era descartado. -->
      <SettingRow
        v-if="mode === 'advanced'"
        :label="t('compression.video.container')"
        :description="t('compression.video.containerHint')"
      >
        <AppSelect
          :model-value="container"
          :options="containerOptions"
          :disabled="disabled"
          @update:model-value="set('container', $event)"
        />
      </SettingRow>

      <SliderField
        :label="t('compression.video.quality')"
        :model-value="quality"
        :min="1"
        :max="100"
        :hint="qualityHint"
        :disabled="disabled"
        @update:model-value="set('quality', $event)"
      />

      <p v-if="noHardware" class="hardware-note">
        {{ t('compression.video.noHardwareNote') }}
      </p>
    </CollapsiblePanel>

    <CollapsiblePanel
      :title="t('compression.video.size')"
      :description="t('compression.video.sizeDescription')"
      :icon="Expand"
    >
      <SettingRow :label="t('compression.video.resolution')">
        <AppSelect
          :model-value="String(settings.resolution ?? 'original')"
          :options="resolutionOptions"
          :disabled="disabled"
          @update:model-value="set('resolution', $event)"
        />
      </SettingRow>

      <SettingRow :label="t('compression.video.fps')" :description="t('compression.video.fpsHint')">
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

    <CollapsiblePanel
      :title="t('compression.video.audioTitle')"
      :description="t('compression.video.audioDescription')"
      :icon="Music"
      :default-open="false"
    >
      <SettingRow :label="t('compression.video.audio.label')" :divided="audioMode !== 'recompress'">
        <AppSelect
          :model-value="audioMode"
          :options="audioModeOptions"
          :disabled="disabled"
          @update:model-value="set('audio_mode', $event)"
        />
      </SettingRow>

      <!-- Os controles do áudio só aparecem quando há o que ajustar. Manter a
           trilha é copiá-la: não há bitrate a escolher, e um controle presente
           mas inerte sugeriria que há. -->
      <template v-if="audioMode === 'recompress' && mode === 'advanced'">
        <SettingRow :label="t('compression.video.audio.codec')">
          <AppSelect
            :model-value="String(settings.audio_codec ?? 'auto')"
            :options="audioCodecOptions"
            :disabled="disabled"
            @update:model-value="set('audio_codec', $event)"
          />
        </SettingRow>
        <SettingRow
          :label="t('compression.video.audio.bitrate')"
          :description="t('compression.video.audio.bitrateHint')"
        >
          <AppSelect
            :model-value="String(settings.audio_bitrate_bps ?? 128000)"
            :options="[
              { value: '96000', label: '96 kbps' },
              { value: '128000', label: '128 kbps' },
              { value: '192000', label: '192 kbps' },
              { value: '256000', label: '256 kbps' },
              { value: '320000', label: '320 kbps' }
            ]"
            :disabled="disabled"
            @update:model-value="set('audio_bitrate_bps', Number($event))"
          />
        </SettingRow>
      </template>
    </CollapsiblePanel>

    <CollapsiblePanel
      v-if="mode === 'advanced'"
      :title="t('compression.video.advanced')"
      :description="t('compression.video.advancedDescription')"
      :icon="Wrench"
      :default-open="false"
    >
      <SettingRow
        :label="t('compression.video.codec')"
        :description="t('compression.video.codecHint')"
      >
        <AppSelect
          :model-value="videoCodec"
          :options="videoCodecOptions"
          :disabled="disabled"
          @update:model-value="set('video_codec', $event)"
        />
      </SettingRow>

      <SettingRow
        :label="t('compression.video.speed.label')"
        :description="t('compression.video.speed.hint')"
      >
        <AppSelect
          :model-value="String(settings.encoding_preset ?? 'auto')"
          :options="speedOptions"
          :disabled="disabled"
          @update:model-value="set('encoding_preset', $event)"
        />
      </SettingRow>

      <SettingRow
        :label="t('compression.video.encoder.label')"
        :description="t('compression.video.encoder.hint')"
        :divided="false"
      >
        <AppSelect
          :model-value="String(settings.encoder_preference ?? 'auto')"
          :options="encoderOptions"
          :disabled="disabled"
          @update:model-value="set('encoder_preference', $event)"
        />
      </SettingRow>
    </CollapsiblePanel>
  </div>
</template>

<style scoped>
.video-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hardware-note {
  margin: var(--space-1) 0 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

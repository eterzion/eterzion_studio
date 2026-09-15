<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, RotateCcw, SlidersHorizontal, WandSparkles } from '@lucide/vue'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SliderField from '../SliderField.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import AppButton from '../atoms/AppButton.vue'
import {
  neutralAdjustments,
  neutralEffects,
  type VideoAdjustments,
  type VideoEffects
} from '../../composables/useVideoEdits'

// T046/T049 (specs/007-video-editor-player) — FR-013a, FR-013b.
//
// Ranges and neutral values come from useVideoEdits, which mirrors schemas.py,
// which mirrors FFmpeg's eq. Repeating the numbers here would create a fourth
// place to keep in sync, and the first one to drift would make the preview
// disagree with the export without anything failing.
//
// Cada ajuste fica atrás de um interruptor, como os filtros do editor de
// imagem. O motivo não é simetria visual: desligar preserva o valor, enquanto
// arrastar o controle de volta ao neutro joga fora a escolha da pessoa. E o
// painel fica curto — seis controles abertos ao mesmo tempo é uma parede.

const props = defineProps<{
  adjustments: VideoAdjustments
  effects: VideoEffects
  /** True when something in this panel will not appear in the moving preview
      (FR-015). Decided centrally by hasUnpreviewableEffects, not here. */
  showsDisclosure: boolean
  disabled?: boolean
}>()

// Values are emitted, not written into the props. The panel renders state it
// does not own; useVideoEdits owns it. Mutating a prop would work by accident —
// the objects are reactive — while making the flow of ownership unreadable, and
// eslint's vue/no-mutating-props is right to refuse it.
const emit = defineEmits<{
  resetAdjustments: []
  resetEffects: []
  updateAdjustment: [key: keyof VideoAdjustments, value: number | boolean]
  updateEffect: [key: keyof VideoEffects, value: number | boolean]
}>()

const { t } = useI18n()

// Bounds mirror VideoAdjustments in useVideoEdits.ts and the Field() ranges in
// schemas.py. Step sizes are chosen for the control, not for the model: 0.01 is
// fine enough that a drag feels continuous without producing values a person
// cannot reason about.
// `decimals` acompanha o `step`: um controle que anda de 0,01 precisa de duas
// casas para o número mostrado mudar quando a pessoa arrasta. Mostrar 0 casas
// num passo de 0,01 seria um número que fica parado enquanto o controle anda.
const SLIDERS = [
  { key: 'brightness', min: -1, max: 1, step: 0.01, neutral: 0, decimals: 2 },
  { key: 'contrast', min: 0, max: 4, step: 0.01, neutral: 1, decimals: 2 },
  { key: 'saturation', min: 0, max: 3, step: 0.01, neutral: 1, decimals: 2 },
  { key: 'gamma', min: 0.1, max: 10, step: 0.01, neutral: 1, decimals: 2 },
  { key: 'hue_degrees', min: -180, max: 180, step: 1, neutral: 0, decimals: 0, unit: '°' },
  { key: 'sharpness', min: 0, max: 2, step: 0.01, neutral: 0, decimals: 2 }
] as const

const EFFECTS = [
  { toggle: 'denoise_enabled', strength: 'denoise_strength', hint: 'denoiseHint' },
  { toggle: 'blur_enabled', strength: 'blur_strength', hint: 'blurHint' },
  { toggle: 'grain_enabled', strength: 'grain_strength', hint: 'grainHint' }
] as const

/** Comparado contra o conjunto neutro em vez de contra os valores um a um: o
 *  neutro é definido num lugar só, e uma comparação escrita à mão aqui seria a
 *  segunda definição a divergir. */
const adjustmentsAreNeutral = computed(
  () => JSON.stringify(props.adjustments) === JSON.stringify(neutralAdjustments())
)
const effectsAreNeutral = computed(
  () => JSON.stringify(props.effects) === JSON.stringify(neutralEffects())
)
</script>

<template>
  <div class="flex flex-col gap-2">
    <CollapsiblePanel
      :title="t('videoEditor.edits.adjustments')"
      :description="t('videoEditor.edits.adjustmentsDescription')"
      :icon="SlidersHorizontal"
      open
    >
      <template v-for="slider in SLIDERS" :key="slider.key">
        <SettingRow
          :label="t(`videoEditor.edits.${slider.key}`)"
          :divided="!adjustments[`${slider.key}_enabled`]"
        >
          <SettingSwitch
            :model-value="adjustments[`${slider.key}_enabled`]"
            :disabled="disabled"
            :aria-label="t(`videoEditor.edits.${slider.key}`)"
            @update:model-value="emit('updateAdjustment', `${slider.key}_enabled`, $event)"
          />
        </SettingRow>
        <SliderField
          v-if="adjustments[`${slider.key}_enabled`]"
          :label="t('videoEditor.edits.strength')"
          :model-value="adjustments[slider.key]"
          :min="slider.min"
          :max="slider.max"
          :step="slider.step"
          :default-value="slider.neutral"
          :decimals="slider.decimals"
          :unit="'unit' in slider ? slider.unit : undefined"
          :hint="t(`videoEditor.edits.${slider.key}Hint`)"
          :aria-label="`${t(`videoEditor.edits.${slider.key}`)} — ${t('videoEditor.edits.strength')}`"
          :disabled="disabled"
          @update:model-value="emit('updateAdjustment', slider.key, $event)"
        />
      </template>

      <AppButton
        variant="ghost"
        size="sm"
        :disabled="disabled || adjustmentsAreNeutral"
        class="self-start"
        @click="emit('resetAdjustments')"
      >
        <template #icon><RotateCcw :size="14" /></template>
        {{ t('videoEditor.edits.reset') }}
      </AppButton>
    </CollapsiblePanel>

    <CollapsiblePanel
      :title="t('videoEditor.edits.effects')"
      :description="t('videoEditor.edits.effectsDescription')"
      :icon="WandSparkles"
    >
      <template v-for="effect in EFFECTS" :key="effect.toggle">
        <SettingRow
          :label="t(`videoEditor.edits.${effect.toggle}`)"
          :divided="!effects[effect.toggle]"
        >
          <SettingSwitch
            :model-value="effects[effect.toggle]"
            :disabled="disabled"
            :aria-label="t(`videoEditor.edits.${effect.toggle}`)"
            @update:model-value="emit('updateEffect', effect.toggle, $event)"
          />
        </SettingRow>
        <SliderField
          v-if="effects[effect.toggle]"
          :label="t('videoEditor.edits.strength')"
          :model-value="effects[effect.strength]"
          :min="0"
          :max="100"
          :step="1"
          :hint="t(`videoEditor.edits.${effect.hint}`)"
          :aria-label="`${t(`videoEditor.edits.${effect.toggle}`)} — ${t('videoEditor.edits.strength')}`"
          :disabled="disabled"
          @update:model-value="emit('updateEffect', effect.strength, $event)"
        />
      </template>

      <AppButton
        variant="ghost"
        size="sm"
        :disabled="disabled || effectsAreNeutral"
        class="self-start"
        @click="emit('resetEffects')"
      >
        <template #icon><RotateCcw :size="14" /></template>
        {{ t('videoEditor.edits.reset') }}
      </AppButton>
    </CollapsiblePanel>

    <!-- FR-015. Not a warning about something being wrong — a statement that
         the moving preview is showing less than the export will. Saying nothing
         here is what the requirement forbids. -->
    <p
      v-if="showsDisclosure"
      class="flex items-start gap-2 rounded border border-surface-border bg-surface-2 px-3 py-2 text-(length:--fs-caption) text-text-tertiary"
    >
      <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
      {{ t('videoEditor.edits.notInLivePreview') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, RotateCcw } from '@lucide/vue'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import RangeSlider from '../RangeSlider.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import AppButton from '../atoms/AppButton.vue'
import type { VideoAdjustments, VideoEffects } from '../../composables/useVideoEdits'

// T046/T049 (specs/007-video-editor-player) — FR-013a, FR-013b.
//
// Ranges and neutral values come from useVideoEdits, which mirrors schemas.py,
// which mirrors FFmpeg's eq. Repeating the numbers here would create a fourth
// place to keep in sync, and the first one to drift would make the preview
// disagree with the export without anything failing.

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
  reset: []
  updateAdjustment: [key: keyof VideoAdjustments, value: number]
  updateEffect: [key: keyof VideoEffects, value: number | boolean]
}>()

const { t } = useI18n()

// Bounds mirror VideoAdjustments in useVideoEdits.ts and the Field() ranges in
// schemas.py. Step sizes are chosen for the control, not for the model: 0.01 is
// fine enough that a drag feels continuous without producing values a person
// cannot reason about.
const SLIDERS = [
  { key: 'brightness', min: -1, max: 1, step: 0.01, neutral: 0 },
  { key: 'contrast', min: 0, max: 4, step: 0.01, neutral: 1 },
  { key: 'saturation', min: 0, max: 3, step: 0.01, neutral: 1 },
  { key: 'gamma', min: 0.1, max: 10, step: 0.01, neutral: 1 },
  { key: 'hue_degrees', min: -180, max: 180, step: 1, neutral: 0 },
  { key: 'sharpness', min: 0, max: 2, step: 0.01, neutral: 0 }
] as const

const EFFECTS = [
  { toggle: 'denoise_enabled', strength: 'denoise_strength' },
  { toggle: 'blur_enabled', strength: 'blur_strength' },
  { toggle: 'grain_enabled', strength: 'grain_strength' }
] as const

const isNeutral = computed(() => SLIDERS.every((s) => props.adjustments[s.key] === s.neutral))
</script>

<template>
  <div class="flex flex-col gap-2">
    <CollapsiblePanel :title="t('videoEditor.edits.adjustments')" open>
      <SettingRow
        v-for="slider in SLIDERS"
        :key="slider.key"
        :label="t(`videoEditor.edits.${slider.key}`)"
      >
        <RangeSlider
          :model-value="adjustments[slider.key]"
          :min="slider.min"
          :max="slider.max"
          :step="slider.step"
          :default-value="slider.neutral"
          :aria-label="t(`videoEditor.edits.${slider.key}`)"
          :disabled="disabled"
          @update:model-value="emit('updateAdjustment', slider.key, $event)"
        />
      </SettingRow>

      <AppButton
        variant="ghost"
        size="sm"
        :disabled="disabled || isNeutral"
        class="self-start"
        @click="emit('reset')"
      >
        <template #icon><RotateCcw :size="14" /></template>
        {{ t('videoEditor.edits.reset') }}
      </AppButton>
    </CollapsiblePanel>

    <CollapsiblePanel :title="t('videoEditor.edits.effects')">
      <template v-for="effect in EFFECTS" :key="effect.toggle">
        <SettingRow :label="t(`videoEditor.edits.${effect.toggle}`)">
          <SettingSwitch
            :model-value="effects[effect.toggle]"
            :disabled="disabled"
            @update:model-value="emit('updateEffect', effect.toggle, $event)"
          />
        </SettingRow>
        <SettingRow v-if="effects[effect.toggle]" :label="t('videoEditor.edits.strength')">
          <RangeSlider
            :model-value="effects[effect.strength]"
            :min="0"
            :max="100"
            :step="1"
            :aria-label="`${t(`videoEditor.edits.${effect.toggle}`)} — ${t('videoEditor.edits.strength')}`"
            :disabled="disabled"
            @update:model-value="emit('updateEffect', effect.strength, $event)"
          />
        </SettingRow>
      </template>
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

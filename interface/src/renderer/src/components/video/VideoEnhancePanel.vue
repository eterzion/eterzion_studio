<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, Expand } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import AppSelect from '../AppSelect.vue'
import NumberStepper from '../NumberStepper.vue'
import ModeTabs from '../ModeTabs.vue'
import ImageInfoPanel from '../ImageInfoPanel.vue'
import { profileOptions, deviceOptions } from '../../constants/processing'
import type { ContentType, Profile } from '../../services/api'

// Unifies the upscale controls into the editor, so video has one screen instead
// of two (replaces the "coexist as an additional mode" reading of FR-032).
//
// The controls themselves are the ones VideoView already offered — content
// type, scale, profile, device — carried over rather than redesigned. This is a
// consolidation, not a redesign: someone who knew the old screen should
// recognise every option here.

export type ScaleChoice = 'none' | '2x' | '4x' | 'custom'

export interface EnhanceSettings {
  scale: ScaleChoice
  customWidth: number | null
  customHeight: number | null
  contentType: ContentType
  profile: Profile
  device: string
}

const props = defineProps<{
  settings: EnhanceSettings
  sourceWidth: number | null
  sourceHeight: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{ update: [patch: Partial<EnhanceSettings>] }>()

const { t } = useI18n()

const profiles = computed(() => profileOptions())
const devices = computed(() => deviceOptions())

// 'none' is what makes the unified screen honest about cost: with no upscale
// requested there is no model pass at all, and the job goes through the
// edit-only route. Without it, opening the editor to trim ten seconds would
// silently run a neural network.
const SCALE_MODE_OPTIONS = computed(() => [
  { value: 'preset', label: t('videoEditor.enhance.modePreset') },
  { value: 'custom', label: t('videoEditor.enhance.modeCustom') }
])

/** Entering the preset mode picks a factor, since 'preset' is not a scale the
 *  backend understands — 2x and 4x are. */
function onModeChange(mode: string): void {
  if (mode === 'preset') {
    const current = props.settings.scale
    emit('update', { scale: current === '2x' || current === '4x' ? current : '2x' })
    return
  }
  emit('update', { scale: mode as ScaleChoice })
}

// Described rather than bare labels: the name alone does not tell you which one
// a stylised music video or a rotoscoped short belongs to. Same reasoning, and
// same wording, VideoView used.
const CONTENT_TYPE_OPTIONS = computed(() => [
  // "Sem modelo" leads for the same reason it does on the Imagem screen: it is
  // the choice that changes the most about what happens. Detection still picks
  // the selected value; this only fixes the order.
  {
    value: 'no_model',
    label: t('videoEditor.enhance.noModel'),
    description: t('videoEditor.enhance.noModelHint')
  },
  {
    value: 'real_video',
    label: t('videoEditor.enhance.realVideo'),
    description: t('videoEditor.enhance.realVideoHint')
  },
  {
    value: 'anime_video',
    label: t('videoEditor.enhance.animeVideo'),
    description: t('videoEditor.enhance.animeVideoHint')
  }
])

const upscaling = computed(() => props.settings.scale !== 'none')

const resultSize = computed(() => {
  const width = props.sourceWidth ?? 0
  const height = props.sourceHeight ?? 0
  if (props.settings.scale === 'custom') {
    return {
      width: props.settings.customWidth ?? width,
      height: props.settings.customHeight ?? height
    }
  }
  const factor = props.settings.scale === '2x' ? 2 : props.settings.scale === '4x' ? 4 : 1
  return { width: width * factor, height: height * factor }
})
</script>

<template>
  <!-- Two panels, laid out like the Imagem screen: what decides HOW the picture
       is processed, then what decides its SIZE. They were one panel mixing both,
       so "which model" and "how big" read as one setting when they are not — and
       the two screens looked unrelated doing the same job. -->
  <CollapsiblePanel
    v-if="upscaling"
    :title="t('videoEditor.enhance.processingTitle')"
    :description="t('videoEditor.enhance.processingDescription')"
    :icon="Cpu"
    open
  >
    <div class="field">
      <label class="field-label">{{ t('videoEditor.enhance.contentType') }}</label>
      <AppSelect
        :model-value="settings.contentType"
        :options="CONTENT_TYPE_OPTIONS"
        :disabled="disabled"
        @update:model-value="emit('update', { contentType: $event as ContentType })"
      />
    </div>

    <div class="field">
      <label class="field-label">{{ t('videoEditor.enhance.profile') }}</label>
      <AppSelect
        :model-value="settings.profile"
        :options="profiles"
        :disabled="disabled"
        @update:model-value="emit('update', { profile: $event as Profile })"
      />
    </div>

    <div class="field">
      <label class="field-label">{{ t('videoEditor.enhance.device') }}</label>
      <AppSelect
        :model-value="settings.device"
        :options="devices"
        :disabled="disabled"
        @update:model-value="emit('update', { device: $event as string })"
      />
    </div>
  </CollapsiblePanel>

  <CollapsiblePanel
    :title="t('videoEditor.enhance.scaleTitle')"
    :description="t('videoEditor.enhance.scaleDescription')"
    :icon="Expand"
    open
  >
    <ModeTabs
      :model-value="settings.scale === '2x' || settings.scale === '4x' ? 'preset' : settings.scale"
      :options="SCALE_MODE_OPTIONS"
      :disabled="disabled"
      @update:model-value="onModeChange($event)"
    />

    <!-- The factor, only under the mode it belongs to — the same shape the
         Imagem screen uses, where 2x/4x live inside "Ampliar" rather than
         competing with it as siblings. -->
    <div v-if="settings.scale === '2x' || settings.scale === '4x'" class="scale-buttons">
      <button
        v-for="factor in ['2x', '4x']"
        :key="factor"
        class="scale-btn"
        :class="{ active: settings.scale === factor }"
        type="button"
        :disabled="disabled"
        @click="emit('update', { scale: factor as ScaleChoice })"
      >
        {{ factor }}
      </button>
    </div>

    <template v-if="settings.scale === 'custom'">
      <div class="steppers-row">
        <NumberStepper
          :model-value="settings.customWidth ?? sourceWidth ?? 0"
          :label="t('videoEditor.enhance.width')"
          :disabled="disabled"
          @update:model-value="emit('update', { customWidth: $event })"
        />
        <NumberStepper
          :model-value="settings.customHeight ?? sourceHeight ?? 0"
          :label="t('videoEditor.enhance.height')"
          :disabled="disabled"
          @update:model-value="emit('update', { customHeight: $event })"
        />
      </div>
    </template>

    <!-- The same readout the Imagem screen shows, not a second one shaped
         differently: original size, new size, the multiplier and the estimate
         are the same four facts about the same operation. -->
    <ImageInfoPanel
      :original-width="sourceWidth"
      :original-height="sourceHeight"
      :new-width="upscaling ? resultSize.width : sourceWidth"
      :new-height="upscaling ? resultSize.height : sourceHeight"
      :estimated-bytes="null"
    />
  </CollapsiblePanel>
</template>

<style scoped>
.field-hint {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  line-height: 1.4;
}

.scale-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

.scale-btn {
  padding: 8px 0;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  font-family: inherit;
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.scale-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--on-primary);
}

.scale-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.steppers-row {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.field-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
}
</style>

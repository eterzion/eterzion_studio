<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, Expand, Link, Unlink } from '@lucide/vue'
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

export type ScaleChoice = '2x' | '4x' | 'custom'

export interface EnhanceSettings {
  scale: ScaleChoice
  lockAspectRatio: boolean
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
  sourceBytes?: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{ update: [patch: Partial<EnhanceSettings>] }>()

const { t } = useI18n()

const profiles = computed(() => profileOptions())
const devices = computed(() => deviceOptions())

// Scale no longer carries "should a model run" — the content type does, and
// 'no_model' is where that lives now. What remains here is the cost question:
// requested there is no model pass at all, and the job goes through the
// edit-only route. Without it, opening the editor to trim ten seconds would
// silently run a neural network.
/** Whether a model runs at all — the content type decides. */
const usesModel = computed(() => {
  const ct = props.settings.contentType
  return ct !== 'pixel_art' && ct !== 'no_model'
})

/** How many times bigger each side gets, when an exact size was typed. */
const customFactor = computed(() => {
  if (!props.sourceWidth || !props.sourceHeight) return null
  // Falls back to the source's own size, exactly as the steppers do: before
  // anything is typed the field shows the source dimensions, so the multiplier
  // has to agree with them and read 1.00x instead of vanishing.
  const width = props.settings.customWidth ?? props.sourceWidth
  const height = props.settings.customHeight ?? props.sourceHeight
  return Math.max(width / props.sourceWidth, height / props.sourceHeight)
})

/** A rough estimate, and labelled as one in the panel.
 *
 *  Video size scales with pixel count far more than with anything else at a
 *  fixed quality target, so area ratio is the honest first approximation. It
 *  ignores how much easier or harder the new frames are to compress, which is
 *  exactly why the panel prints it behind a "≈". */
const estimatedBytes = computed(() => {
  if (!props.sourceBytes || !props.sourceWidth || !props.sourceHeight) return null
  const target = upscaling.value
    ? resultSize.value
    : { width: props.sourceWidth, height: props.sourceHeight }
  const ratio = (target.width * target.height) / (props.sourceWidth * props.sourceHeight)
  return Math.round(props.sourceBytes * ratio)
})

/** Typing one side moves the other while the ratio is locked — the same
 *  behaviour the Imagem screen has, and the reason the lock exists at all. */
function onCustomWidth(width: number): void {
  const patch: Partial<EnhanceSettings> = { customWidth: width }
  if (props.settings.lockAspectRatio && props.sourceWidth && props.sourceHeight) {
    patch.customHeight = Math.max(1, Math.round(width * (props.sourceHeight / props.sourceWidth)))
  }
  emit('update', patch)
}

function onCustomHeight(height: number): void {
  const patch: Partial<EnhanceSettings> = { customHeight: height }
  if (props.settings.lockAspectRatio && props.sourceWidth && props.sourceHeight) {
    patch.customWidth = Math.max(1, Math.round(height * (props.sourceWidth / props.sourceHeight)))
  }
  emit('update', patch)
}

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

/** Whether the output will be bigger than the source. 'custom' only counts
 *  when the target actually exceeds it — asking for the source's own size is
 *  not an upscale, and treating it as one would charge for work not done. */
const upscaling = computed(() => {
  const { scale, customWidth, customHeight } = props.settings
  if (scale === '2x' || scale === '4x') return true
  if (!props.sourceWidth || !props.sourceHeight) return false
  return (customWidth ?? 0) > props.sourceWidth || (customHeight ?? 0) > props.sourceHeight
})

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

    <!-- Ver ImageEditorView: o tipo de conteúdo fica, o resto só faz sentido
         quando um modelo roda. -->
    <div v-if="usesModel" class="field">
      <label class="field-label">{{ t('videoEditor.enhance.profile') }}</label>
      <AppSelect
        :model-value="settings.profile"
        :options="profiles"
        :disabled="disabled"
        @update:model-value="emit('update', { profile: $event as Profile })"
      />
    </div>

    <div v-if="usesModel" class="field">
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
      <!-- The same three parts the Imagem screen shows for an exact size: the
           aspect lock, the two steppers, and the multiplier that says what the
           numbers add up to. They were missing here, so the same task looked
           like two different features on the two screens. -->
      <div class="field-label-row">
        <label class="field-label">{{ t('videoEditor.enhance.sizeLabel') }}</label>
        <button
          class="link-btn"
          type="button"
          :aria-pressed="settings.lockAspectRatio"
          :disabled="disabled"
          :title="
            settings.lockAspectRatio
              ? t('videoEditor.enhance.aspectLocked')
              : t('videoEditor.enhance.aspectFree')
          "
          @click="emit('update', { lockAspectRatio: !settings.lockAspectRatio })"
        >
          <component :is="settings.lockAspectRatio ? Link : Unlink" :size="13" />
          {{
            settings.lockAspectRatio
              ? t('videoEditor.enhance.locked')
              : t('videoEditor.enhance.free')
          }}
        </button>
      </div>

      <div class="steppers-row">
        <NumberStepper
          :model-value="settings.customWidth ?? sourceWidth ?? 0"
          :label="t('videoEditor.enhance.width')"
          :disabled="disabled"
          @update:model-value="onCustomWidth($event)"
        />
        <NumberStepper
          :model-value="settings.customHeight ?? sourceHeight ?? 0"
          :label="t('videoEditor.enhance.height')"
          :disabled="disabled"
          @update:model-value="onCustomHeight($event)"
        />
      </div>

      <div v-if="customFactor" class="scale-multiplier">
        <span class="scale-multiplier-label">
          {{ t('videoEditor.enhance.resolutionMultiplier') }}
        </span>
        <span class="scale-multiplier-value">{{ customFactor.toFixed(2) }}&times;</span>
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
      :estimated-bytes="estimatedBytes"
    />
  </CollapsiblePanel>
</template>

<style scoped>
.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  padding: 3px 10px;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
}

.link-btn[aria-pressed='true'] {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.scale-multiplier {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  padding: 8px var(--space-3);
}

.scale-multiplier-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.scale-multiplier-value {
  font-size: 18px;
  font-weight: var(--fw-semibold);
  color: var(--color-primary);
  font-family: var(--font-mono);
}

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

/* Grid with two equal columns, the same the Imagem screen uses. With flex and
   no basis on the children each stepper shrank to its content, and the value
   field inside NumberStepper is `width: 0; flex: 1` by design — so it
   collapsed and the number disappeared between the − and + buttons. */
.steppers-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
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

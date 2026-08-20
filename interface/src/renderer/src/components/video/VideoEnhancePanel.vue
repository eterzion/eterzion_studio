<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import AppSelect from '../AppSelect.vue'
import NumberStepper from '../NumberStepper.vue'
import ModeTabs from '../ModeTabs.vue'
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
const SCALE_OPTIONS = computed(() => [
  { value: 'none', label: t('videoEditor.enhance.noUpscale') },
  { value: '2x', label: '2x' },
  { value: '4x', label: '4x' },
  { value: 'custom', label: t('videoEditor.enhance.custom') }
])

// Described rather than bare labels: the name alone does not tell you which one
// a stylised music video or a rotoscoped short belongs to. Same reasoning, and
// same wording, VideoView used.
const CONTENT_TYPE_OPTIONS = computed(() => [
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
  <CollapsiblePanel :title="t('videoEditor.enhance.title')" open>
    <!-- Label above and full width, exactly as the Imagem screen lays it out.
         Inside a SettingRow the tabs share the row with their own label and end
         up about a fifth of the panel wide; the same control looking different
         on the two screens is the thing this was meant to fix. -->
    <div class="field">
      <label class="field-label">{{ t('videoEditor.enhance.scale') }}</label>
      <ModeTabs
        :model-value="settings.scale"
        :options="SCALE_OPTIONS"
        :disabled="disabled"
        @update:model-value="emit('update', { scale: $event as ScaleChoice })"
      />
    </div>

    <template v-if="settings.scale === 'custom'">
      <SettingRow :label="t('videoEditor.enhance.customSize')">
        <div class="flex items-center gap-2">
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
      </SettingRow>
    </template>

    <!-- Only shown while an upscale is actually requested: content type, profile
         and device all describe how the MODEL runs, and there is no model when
         scale is none. Offering them anyway would imply a cost that is not
         being paid. -->
    <template v-if="upscaling">
      <SettingRow :label="t('videoEditor.enhance.contentType')">
        <AppSelect
          :model-value="settings.contentType"
          :options="CONTENT_TYPE_OPTIONS"
          :disabled="disabled"
          @update:model-value="emit('update', { contentType: $event as ContentType })"
        />
      </SettingRow>

      <SettingRow :label="t('videoEditor.enhance.profile')">
        <AppSelect
          :model-value="settings.profile"
          :options="profiles"
          :disabled="disabled"
          @update:model-value="emit('update', { profile: $event as Profile })"
        />
      </SettingRow>

      <SettingRow :label="t('videoEditor.enhance.device')">
        <AppSelect
          :model-value="settings.device"
          :options="devices"
          :disabled="disabled"
          @update:model-value="emit('update', { device: $event as string })"
        />
      </SettingRow>
    </template>

    <SettingRow v-if="upscaling && sourceWidth" :label="t('videoEditor.enhance.resultSize')">
      <span class="text-(length:--fs-caption) tabular-nums text-text-tertiary">
        {{ resultSize.width }} &times; {{ resultSize.height }}
      </span>
    </SettingRow>
  </CollapsiblePanel>
</template>

<style scoped>
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

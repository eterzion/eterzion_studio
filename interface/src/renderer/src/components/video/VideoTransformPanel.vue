<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Crop, RotateCw } from '@lucide/vue'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import AppButton from '../atoms/AppButton.vue'
import type { VideoTransform, VideoTrim } from '../../composables/useVideoEdits'

// T047 (specs/007-video-editor-player) — FR-013c, plus the trim readout.
//
// Rotation is a cycle button rather than four radio options: the values are the
// four FFmpeg supports, and a person rotating a clip presses until it looks
// right rather than reasoning about degrees.

const props = defineProps<{
  transform: VideoTransform
  trim: VideoTrim | null
  formatTime: (seconds: number) => string
  disabled?: boolean
  /** A Imagem nao tem trecho. */
  image?: boolean
}>()

const emit = defineEmits<{
  updateTransform: [patch: Partial<VideoTransform>]
  clearTrim: []
}>()

const { t } = useI18n()

function rotate(): void {
  const next = ((props.transform.rotation_degrees + 90) % 360) as 0 | 90 | 180 | 270
  emit('updateTransform', { rotation_degrees: next })
}
</script>

<template>
  <CollapsiblePanel
    :title="t('videoEditor.edits.transform')"
    :description="t('videoEditor.edits.transformDescription')"
    :icon="Crop"
  >
    <SettingRow :label="t('videoEditor.edits.rotation')">
      <AppButton variant="outline" size="sm" :disabled="disabled" @click="rotate">
        <template #icon><RotateCw :size="14" /></template>
        {{ transform.rotation_degrees }}&deg;
      </AppButton>
    </SettingRow>

    <SettingRow :label="t('videoEditor.edits.flipHorizontal')">
      <SettingSwitch
        :model-value="transform.flip_horizontal"
        :disabled="disabled"
        @update:model-value="emit('updateTransform', { flip_horizontal: $event })"
      />
    </SettingRow>

    <SettingRow :label="t('videoEditor.edits.flipVertical')">
      <SettingSwitch
        :model-value="transform.flip_vertical"
        :disabled="disabled"
        @update:model-value="emit('updateTransform', { flip_vertical: $event })"
      />
    </SettingRow>

    <!-- Trim is set on the timeline, not typed here. This is the readout and
         the way back out of it (FR-013d) -- so it only appears when there is a
         trim: "whole video" told nobody anything. -->
    <SettingRow v-if="!image && trim" :label="t('videoEditor.edits.trim')">
      <div class="flex items-center gap-2">
        <span class="text-(length:--fs-caption) tabular-nums text-text-tertiary">
          {{ formatTime(trim.start_seconds) }} &ndash; {{ formatTime(trim.end_seconds) }}
        </span>
        <AppButton variant="ghost" size="sm" :disabled="disabled" @click="emit('clearTrim')">
          {{ t('videoEditor.edits.clearTrim') }}
        </AppButton>
      </div>
    </SettingRow>
  </CollapsiblePanel>
</template>

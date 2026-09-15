<script setup lang="ts">
import { computed } from 'vue'
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
  sourceWidth: number | null
  sourceHeight: number | null
  formatTime: (seconds: number) => string
  disabled?: boolean
}>()

const emit = defineEmits<{
  updateTransform: [patch: Partial<VideoTransform>]
  clearTrim: []
}>()

const { t } = useI18n()

// Rotating by a quarter turn swaps the output's dimensions. Showing the result
// means the exported file's shape is not a surprise.
const outputSize = computed(() => {
  const crop = props.transform.crop
  let width = crop?.width ?? props.sourceWidth ?? 0
  let height = crop?.height ?? props.sourceHeight ?? 0
  if (props.transform.rotation_degrees === 90 || props.transform.rotation_degrees === 270) {
    const swap = width
    width = height
    height = swap
  }
  // Even, because encoders reject odd dimensions in yuv420p. The same rounding
  // video_edits.py applies, shown before the export rather than discovered
  // after it.
  return {
    width: Math.max(2, Math.floor(width / 2) * 2),
    height: Math.max(2, Math.floor(height / 2) * 2)
  }
})

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

    <SettingRow :label="t('videoEditor.edits.outputSize')">
      <span class="text-(length:--fs-caption) tabular-nums text-text-tertiary">
        {{ outputSize.width }} &times; {{ outputSize.height }}
      </span>
    </SettingRow>

    <!-- Trim is set on the timeline, not typed here. This is the readout and
         the way back out of it (FR-013d). -->
    <SettingRow :label="t('videoEditor.edits.trim')">
      <div class="flex items-center gap-2">
        <span class="text-(length:--fs-caption) tabular-nums text-text-tertiary">
          <template v-if="trim">
            {{ formatTime(trim.start_seconds) }} &ndash; {{ formatTime(trim.end_seconds) }}
          </template>
          <template v-else>{{ t('videoEditor.edits.wholeVideo') }}</template>
        </span>
        <AppButton
          v-if="trim"
          variant="ghost"
          size="sm"
          :disabled="disabled"
          @click="emit('clearTrim')"
        >
          {{ t('videoEditor.edits.clearTrim') }}
        </AppButton>
      </div>
    </SettingRow>
  </CollapsiblePanel>
</template>

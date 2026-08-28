<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { AlertTriangle } from '@lucide/vue'

// T028 (specs/007-video-editor-player) — FR-008 and FR-012.
//
// The FR-012 rule lives here, in the one place that would otherwise render a
// number: when the frame index is unreliable the component shows why instead of
// showing a figure that does not match the picture. Putting that decision in
// the display rather than in the caller means no caller can forget it.

defineProps<{
  currentTime: number
  duration: number
  frame: number | null
  totalFrames: number | null
  frameIsReliable: boolean
  formatTime: (seconds: number) => string
}>()

const { t } = useI18n()
</script>

<template>
  <div class="flex items-center gap-3 text-(length:--fs-caption) tabular-nums">
    <span class="text-text-primary">
      {{ formatTime(currentTime) }}
      <span class="text-text-tertiary">/ {{ formatTime(duration) }}</span>
    </span>

    <span v-if="frameIsReliable && frame !== null" class="text-text-tertiary">
      {{ t('videoEditor.player.frame') }} {{ frame
      }}<template v-if="totalFrames !== null"> / {{ totalFrames }}</template>
    </span>

    <!-- FR-012: no number at all, and a reason. Showing a confident figure that
         does not correspond to the visible frame is worse than showing none. -->
    <span
      v-else
      class="flex items-center gap-1 text-text-tertiary"
      :title="t('videoEditor.player.frameUnavailable')"
    >
      <AlertTriangle :size="13" />
      {{ t('videoEditor.player.frameUnavailable') }}
    </span>
  </div>
</template>

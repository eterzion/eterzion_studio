<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Volume, Volume1, Volume2, VolumeOff, VolumeX } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'
import RangeSlider from '../RangeSlider.vue'

// T029 (specs/007-video-editor-player) — FR-009.
//
// When the video has no audio track this renders a disabled state that says so,
// rather than a working-looking slider that does nothing. A control that
// silently has no effect is a worse answer than an honest absence.

const props = defineProps<{ volume: number; muted: boolean; hasAudio: boolean }>()

const emit = defineEmits<{ 'update:volume': [number]; 'update:muted': [boolean] }>()

const { t } = useI18n()

const percent = computed(() => Math.round(props.volume * 100))

// The icon follows the level, the way every media player does: one icon that
// never changes gives no feedback that dragging did anything, and the number is
// not always on screen.
//
// Muted and dragged-to-zero are told apart on purpose. They look identical if
// both use one icon, but they are different situations — unmuting restores the
// old level, while a slider at zero has nothing to restore.
//
// Lucide ships three wave levels (Volume, Volume1, Volume2), so the bands at 25,
// 50 and 75 map onto those three plus silence: 76-100 shares Volume2 with
// 51-75. Inventing a fourth by tinting or rotating one of them would signal a
// distinction the icon set does not actually draw.
const icon = computed(() => {
  if (props.muted) return VolumeOff
  if (percent.value === 0) return VolumeX
  if (percent.value <= 25) return Volume
  if (percent.value <= 50) return Volume1
  return Volume2
})
</script>

<template>
  <div class="volume-control">
    <template v-if="props.hasAudio">
      <AppButton
        variant="ghost"
        size="sm"
        icon-only
        :title="muted ? t('videoEditor.player.unmute') : t('videoEditor.player.mute')"
        :aria-label="muted ? t('videoEditor.player.unmute') : t('videoEditor.player.mute')"
        @click="emit('update:muted', !muted)"
      >
        <!-- AppButton renders `<slot v-if="!iconOnly" />`, so with icon-only the
             default slot is skipped and only #icon is drawn. -->
        <template #icon><component :is="icon" :size="16" /></template>
      </AppButton>

      <!-- The shared slider, not a bare <input type="range">: it carries the
           app's track, thumb and default-marker styling, so this control looks
           like every other one instead of like a browser default. -->
      <RangeSlider
        class="volume-slider"
        :model-value="percent"
        :min="0"
        :max="100"
        :step="1"
        :default-value="100"
        :aria-label="t('videoEditor.player.volume')"
        @update:model-value="emit('update:volume', $event / 100)"
      />
    </template>

    <span v-else class="no-audio" :title="t('videoEditor.player.noAudio')">
      <VolumeX :size="16" />
      {{ t('videoEditor.player.noAudio') }}
    </span>
  </div>
</template>

<style scoped>
.volume-control {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* Narrow enough to sit in the transport bar without crowding the time readout,
   wide enough that a drag still has useful resolution. */
.volume-slider {
  width: 96px;
}

.no-audio {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}
</style>

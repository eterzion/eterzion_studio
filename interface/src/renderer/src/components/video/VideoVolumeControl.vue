<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Volume2, VolumeX } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'

// T029 (specs/007-video-editor-player) — FR-009.
//
// When the video has no audio track this renders a disabled state that says so,
// rather than a working-looking slider that does nothing. A control that
// silently has no effect is a worse answer than an honest absence.

const props = defineProps<{ volume: number; muted: boolean; hasAudio: boolean }>()

const emit = defineEmits<{ 'update:volume': [number]; 'update:muted': [boolean] }>()

const { t } = useI18n()

function onInput(event: Event): void {
  emit('update:volume', Number((event.target as HTMLInputElement).value) / 100)
}
</script>

<template>
  <div class="flex items-center gap-2">
    <template v-if="props.hasAudio">
      <AppButton
        variant="ghost"
        size="sm"
        icon-only
        :title="muted ? t('videoEditor.player.unmute') : t('videoEditor.player.mute')"
        :aria-label="muted ? t('videoEditor.player.unmute') : t('videoEditor.player.mute')"
        @click="emit('update:muted', !muted)"
      >
        <VolumeX v-if="muted || volume === 0" :size="16" />
        <Volume2 v-else :size="16" />
      </AppButton>
      <input
        type="range"
        min="0"
        max="100"
        :value="Math.round(volume * 100)"
        :aria-label="t('videoEditor.player.volume')"
        class="h-1 w-20 accent-accent"
        @input="onInput"
      />
    </template>

    <span
      v-else
      class="flex items-center gap-1 text-(length:--fs-caption) text-text-tertiary"
      :title="t('videoEditor.player.noAudio')"
    >
      <VolumeX :size="16" />
      {{ t('videoEditor.player.noAudio') }}
    </span>
  </div>
</template>

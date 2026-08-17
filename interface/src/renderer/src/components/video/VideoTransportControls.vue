<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Pause, Play, SkipBack, SkipForward } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'

// T026 (specs/007-video-editor-player) — FR-006 and FR-010.
//
// Its own component rather than markup inside VideoPlayer because transport is
// the one part of the player that a second surface will want unchanged (the
// export progress view shows the same controls over a rendered result), and
// because keyboard handling belongs with the controls it drives, not with the
// element that happens to contain them.

defineProps<{ isPlaying: boolean; disabled?: boolean }>()

const emit = defineEmits<{ toggle: []; stepBack: []; stepForward: [] }>()

const { t } = useI18n()

// Arrow keys step, space toggles — the bindings anyone who has used a video
// tool already expects. Handled here so the buttons stay reachable by Tab and
// the shortcuts work without focusing them (FR-010).
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    emit('stepBack')
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    emit('stepForward')
  } else if (event.key === ' ' || event.key === 'k') {
    event.preventDefault()
    emit('toggle')
  }
}

defineExpose({ onKeydown })
</script>

<template>
  <div class="flex items-center gap-1" role="group" :aria-label="t('videoEditor.player.timeline')">
    <AppButton
      variant="ghost"
      size="sm"
      icon-only
      :disabled="disabled"
      :title="t('videoEditor.player.stepBack')"
      :aria-label="t('videoEditor.player.stepBack')"
      @click="emit('stepBack')"
    >
      <SkipBack :size="16" />
    </AppButton>

    <AppButton
      variant="primary"
      size="md"
      icon-only
      :disabled="disabled"
      :title="isPlaying ? t('videoEditor.player.pause') : t('videoEditor.player.play')"
      :aria-label="isPlaying ? t('videoEditor.player.pause') : t('videoEditor.player.play')"
      @click="emit('toggle')"
    >
      <Pause v-if="isPlaying" :size="18" />
      <Play v-else :size="18" />
    </AppButton>

    <AppButton
      variant="ghost"
      size="sm"
      icon-only
      :disabled="disabled"
      :title="t('videoEditor.player.stepForward')"
      :aria-label="t('videoEditor.player.stepForward')"
      @click="emit('stepForward')"
    >
      <SkipForward :size="16" />
    </AppButton>
  </div>
</template>

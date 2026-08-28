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

// The transport shortcuts live in VideoPlayer, not here. An earlier version
// defined them in this component and exposed the handler — which nothing bound,
// so the shortcuts silently never fired. Keyboard handling belongs to whatever
// actually holds focus, and that is the player, not a button group inside it.
</script>

<template>
  <div class="flex items-center gap-1" role="group" :aria-label="t('videoEditor.player.transport')">
    <AppButton
      variant="ghost"
      size="sm"
      icon-only
      :disabled="disabled"
      :title="t('videoEditor.player.stepBack')"
      :aria-label="t('videoEditor.player.stepBack')"
      @click="emit('stepBack')"
    >
      <template #icon><SkipBack :size="16" /></template>
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
      <template #icon>
        <Pause v-if="isPlaying" :size="18" />
        <Play v-else :size="18" />
      </template>
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
      <template #icon><SkipForward :size="16" /></template>
    </AppButton>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import VideoPlayerSurface from './VideoPlayerSurface.vue'
import VideoTransportControls from './VideoTransportControls.vue'
import VideoTimeline from './VideoTimeline.vue'
import VideoTimeDisplay from './VideoTimeDisplay.vue'
import VideoVolumeControl from './VideoVolumeControl.vue'
import VideoTimelineThumbnails from './VideoTimelineThumbnails.vue'
import { useVideoPlayback } from '../../composables/useVideoPlayback'
import { useVideoTimeline } from '../../composables/useVideoTimeline'
import { useTimelineThumbnails } from '../../composables/useTimelineThumbnails'
import type { MediaHandle } from '../../services/api'
import type { VideoAdjustments } from '../../composables/useVideoEdits'

// T030 (specs/007-video-editor-player) — the root of the player component tree
// the original request specified (constitution.md:29).
//
// This composes; it does not implement. Playback state lives in
// useVideoPlayback, arithmetic in useVideoTimeline, and each control owns its
// own presentation. What is left here is wiring — which is the shape
// Princípio X asks for once a part becomes independently meaningful.

const props = defineProps<{
  handle: MediaHandle | null
  sourcePath: string | null
  /** Pushed straight through to the shader. Null means "preview untouched". */
  adjustments?: VideoAdjustments | null
  recalculating?: boolean
}>()

const element = ref<HTMLVideoElement | null>(null)
/** Rendered width of the picture, reported by the surface. The controls match
 *  it so the timeline lines up with the frame instead of with the stage. */
const pictureWidth = ref(0)
const handleRef = computed(() => props.handle)

const timeline = useVideoTimeline(handleRef)
const thumbnails = useTimelineThumbnails(handleRef)
const playback = useVideoPlayback(element) as ReturnType<typeof useVideoPlayback> & {
  attach: () => void
}

function onReady(video: HTMLVideoElement): void {
  element.value = video
  playback.attach()
}

// Switching files must not leave the previous one's position on the new one.
watch(
  () => props.handle?.handle_id,
  () => {
    if (element.value) playback.seek(0)
  }
)

watch(playback.volume, (value) => {
  if (element.value) element.value.volume = value
})
watch(playback.muted, (value) => {
  if (element.value) element.value.muted = value
})

const duration = computed(() => props.handle?.duration_seconds ?? 0)

// Exposed so the view can seed a trim range from the current position without
// reaching into the player's internals.
defineExpose({ currentTime: playback.currentTime })
const frame = computed(() => timeline.frameAt(playback.presentedTime.value))
const disabled = computed(() => !props.handle)

// FR-010. Space toggles, arrows step — the bindings anyone who has used a video
// tool expects. Bound on the player's own container so they work whenever the
// player has focus, without stealing keys from the rest of the application.
//
// Ignored while focus is in a text field or a slider: arrows mean something
// else there, and a shortcut that hijacks them is worse than no shortcut.
function onKeydown(event: KeyboardEvent): void {
  if (disabled.value) return
  const target = event.target as HTMLElement | null
  const tag = target?.tagName.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return

  if (event.key === ' ' || event.key === 'k') {
    event.preventDefault()
    playback.toggle()
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    playback.step(-1, timeline.frameDuration.value)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    playback.step(1, timeline.frameDuration.value)
  }
}
</script>

<template>
  <div
    class="video-player"
    tabindex="0"
    role="application"
    :aria-label="handle?.display_name ?? ''"
    @keydown="onKeydown"
  >
    <div class="player-stage">
      <VideoPlayerSurface
        :handle="handle"
        :source-path="sourcePath"
        :adjustments="adjustments ?? null"
        :recalculating="recalculating"
        @ready="onReady"
        @picture-resize="pictureWidth = $event"
      />
    </div>

    <!-- Width tied to the picture above it, so the timeline starts and ends
         where the frame does. min-width keeps it usable under a very narrow
         clip, where matching the picture exactly would crush the transport. -->
    <div class="player-controls" :style="{ width: pictureWidth ? `${pictureWidth}px` : undefined }">
      <VideoTimeline
        :progress="timeline.progressAt(playback.currentTime.value)"
        :duration="duration"
        :current-time="playback.currentTime.value"
        :format-time="timeline.formatTime"
        :disabled="disabled"
        @seek="playback.seek(timeline.timeAtProgress($event))"
      >
        <template #track-background>
          <VideoTimelineThumbnails
            :sprite-url="thumbnails.spriteUrl.value"
            :count="thumbnails.count.value"
            :thumb-width="thumbnails.thumbWidth.value"
            :thumb-height="thumbnails.thumbHeight.value"
          />
          <slot name="timeline-overlay" />
        </template>
      </VideoTimeline>

      <div class="flex items-center justify-between gap-3">
        <VideoTransportControls
          :is-playing="playback.isPlaying.value"
          :disabled="disabled"
          @toggle="playback.toggle()"
          @step-back="playback.step(-1, timeline.frameDuration.value)"
          @step-forward="playback.step(1, timeline.frameDuration.value)"
        />

        <VideoTimeDisplay
          :current-time="playback.currentTime.value"
          :duration="duration"
          :frame="frame"
          :total-frames="timeline.totalFrames.value"
          :frame-is-reliable="timeline.frameNumberIsReliable.value"
          :format-time="timeline.formatTime"
        />

        <VideoVolumeControl
          v-model:volume="playback.volume.value"
          v-model:muted="playback.muted.value"
          :has-audio="handle?.has_audio ?? false"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* The video should be as large as the stage allows, so the frame is what fills
   the eye rather than the chrome around it. The controls keep their intrinsic
   height; everything left over goes to the picture.
 *
 * This block used to be dead: the root element carried Tailwind utilities and
 * never the .video-player class, so none of it applied. The measured result was
 * a player 454px wide inside a 680px stage — the width was being decided by the
 * intrinsic width of the controls, with the rest of the stage left empty. */
.video-player {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  gap: var(--space-1);
}
.video-player:focus {
  outline: none;
}

.player-stage {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.player-stage :deep(.video-surface) {
  width: 100%;
  height: 100%;
}

.player-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-1-5) var(--space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  background: var(--surface-2);
  flex: 0 0 auto;
  max-width: 100%;
  min-width: min(420px, 100%);
}
</style>

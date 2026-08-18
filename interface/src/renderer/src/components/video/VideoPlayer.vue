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
    class="flex h-full flex-col focus:outline-none"
    tabindex="0"
    role="application"
    :aria-label="handle?.display_name ?? ''"
    @keydown="onKeydown"
  >
    <div class="min-h-0 flex-1">
      <VideoPlayerSurface
        :handle="handle"
        :source-path="sourcePath"
        :adjustments="adjustments ?? null"
        :recalculating="recalculating"
        @ready="onReady"
      />
    </div>

    <div class="flex flex-col gap-1 border-t border-surface-border bg-surface-2 px-3 py-2">
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

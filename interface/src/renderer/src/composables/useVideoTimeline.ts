import { computed, type Ref } from 'vue'
import type { MediaHandle } from '../services/api'

// T024 (specs/007-video-editor-player) — the conversions the timeline and the
// frame counter need: time ↔ frame ↔ pixel.
//
// Kept apart from useVideoPlayback because it is pure arithmetic over a
// handle's metadata: it touches no element, holds no playback state, and is
// therefore testable without a DOM. Playback is the opposite — it is entirely
// about an element's behaviour. Splitting on that line is what makes both
// testable rather than a size decision (Princípio X).

export interface VideoTimeline {
  /** Frame index at a given time, or null when the frame number cannot be
      trusted (FR-012). */
  frameAt: (seconds: number) => number | null
  /** Start time of a frame index. Null under the same condition. */
  timeOfFrame: (frame: number) => number | null
  /** Total frames, or null when unknowable. */
  totalFrames: Ref<number | null> | { value: number | null }
  /** False when the source is VFR or its metadata is inconsistent. The player
      MUST NOT present a frame number as exact while this is false. */
  frameNumberIsReliable: { value: boolean }
  /** One frame's duration, used for stepping. Falls back to a sane value when
      the rate is unknown, because stepping still has to do something. */
  frameDuration: { value: number }
  /** Fraction 0..1 of the way through the video, clamped. */
  progressAt: (seconds: number) => number
  /** Inverse of progressAt, for click/drag on the timeline. */
  timeAtProgress: (progress: number) => number
  formatTime: (seconds: number) => string
}

// Used only for stepping when the real rate is unknown. Not a claim about the
// video — a claim about how far to move when asked to step and told nothing.
const FALLBACK_STEP_FPS = 30

export function useVideoTimeline(handle: Ref<MediaHandle | null>): VideoTimeline {
  const duration = computed(() => handle.value?.duration_seconds ?? 0)

  const frameNumberIsReliable = computed(() => {
    const h = handle.value
    if (!h) return false
    // Both conditions matter. A VFR file has no stable time→frame mapping at
    // all; a file with no reported rate gives us nothing to compute one from.
    // FR-012 forbids showing a confident number in either case, and a false
    // "reliable" is the expensive direction — it puts a number on screen that
    // does not match the picture.
    return !h.frame_rate_is_variable && !!h.frame_rate && h.frame_rate > 0
  })

  const frameDuration = computed(() => {
    const rate = handle.value?.frame_rate
    return 1 / (rate && rate > 0 ? rate : FALLBACK_STEP_FPS)
  })

  const totalFrames = computed(() => {
    if (!frameNumberIsReliable.value) return null
    return Math.max(0, Math.floor(duration.value * handle.value!.frame_rate!))
  })

  function frameAt(seconds: number): number | null {
    if (!frameNumberIsReliable.value) return null
    const frame = Math.floor(seconds * handle.value!.frame_rate!)
    return Math.max(0, Math.min(frame, (totalFrames.value ?? frame) - 1 >= 0 ? frame : 0))
  }

  function timeOfFrame(frame: number): number | null {
    if (!frameNumberIsReliable.value) return null
    return Math.max(0, frame) / handle.value!.frame_rate!
  }

  function progressAt(seconds: number): number {
    if (duration.value <= 0) return 0
    return Math.min(1, Math.max(0, seconds / duration.value))
  }

  function timeAtProgress(progress: number): number {
    return Math.min(1, Math.max(0, progress)) * duration.value
  }

  function formatTime(seconds: number): string {
    // Hours appear only when there are hours: a ten-second clip showing
    // "00:00:04" reads as a mistake, and a three-hour file showing "184:12"
    // is unreadable. The format follows the material.
    const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0
    const whole = Math.floor(safe)
    const hours = Math.floor(whole / 3600)
    const minutes = Math.floor((whole % 3600) / 60)
    const secs = whole % 60
    const pad = (n: number): string => String(n).padStart(2, '0')
    return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`
  }

  return {
    frameAt,
    timeOfFrame,
    totalFrames,
    frameNumberIsReliable,
    frameDuration,
    progressAt,
    timeAtProgress,
    formatTime
  }
}

import { onBeforeUnmount, readonly, ref, type Ref } from 'vue'

// T023 (specs/007-video-editor-player) — playback state and frame-accurate
// stepping over a <video> element.
//
// research.md Decisão 3: the frame actually on screen comes from
// requestVideoFrameCallback, not from `currentTime × fps`. The browser rounds
// currentTime to the nearest decodable frame, and in a variable-frame-rate file
// the arithmetic does not hold at all. rVFC is the only source in Chromium that
// reports which frame was really presented.

/** The subset of requestVideoFrameCallback's metadata this needs. Declared
 *  here because TypeScript's DOM lib does not ship it yet. */
interface FrameMetadata {
  mediaTime: number
  presentedFrames: number
}

type VideoWithFrameCallback = HTMLVideoElement & {
  requestVideoFrameCallback?: (cb: (now: number, metadata: FrameMetadata) => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

export interface VideoPlayback {
  isPlaying: Readonly<Ref<boolean>>
  currentTime: Readonly<Ref<number>>
  /** mediaTime of the frame the browser last presented — the honest answer to
      "what am I looking at", where currentTime is only approximately that. */
  presentedTime: Readonly<Ref<number>>
  volume: Ref<number>
  muted: Ref<boolean>
  play: () => Promise<void>
  pause: () => void
  toggle: () => Promise<void>
  seek: (seconds: number) => void
  /** Step by whole frames. Pauses first: stepping while playing is a request
      the element cannot honour, and silently ignoring it looks like a bug. */
  step: (frames: number, frameDuration: number) => void
}

export function useVideoPlayback(element: Ref<HTMLVideoElement | null>): VideoPlayback {
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const presentedTime = ref(0)
  const volume = ref(1)
  const muted = ref(false)

  let frameCallbackHandle: number | null = null

  function scheduleFrameCallback(): void {
    const video = element.value as VideoWithFrameCallback | null
    if (!video?.requestVideoFrameCallback) return
    frameCallbackHandle = video.requestVideoFrameCallback((_now, metadata) => {
      presentedTime.value = metadata.mediaTime
      currentTime.value = metadata.mediaTime
      // Re-arm unconditionally rather than only while playing: a seek while
      // paused presents a new frame too, and that is exactly the case the
      // frame counter must follow.
      scheduleFrameCallback()
    })
  }

  function cancelFrameCallback(): void {
    const video = element.value as VideoWithFrameCallback | null
    if (frameCallbackHandle !== null && video?.cancelVideoFrameCallback) {
      video.cancelVideoFrameCallback(frameCallbackHandle)
    }
    frameCallbackHandle = null
  }

  /** Bind to an element. Called by the surface component once the element
   *  exists; safe to call again when the source changes. */
  function attach(): void {
    const video = element.value
    if (!video) return
    cancelFrameCallback()

    video.volume = volume.value
    video.muted = muted.value

    video.addEventListener('play', () => (isPlaying.value = true))
    video.addEventListener('pause', () => (isPlaying.value = false))
    video.addEventListener('ended', () => (isPlaying.value = false))
    // timeupdate fires ~4x/second, far too coarse to drive a frame counter, but
    // it is the only signal in browsers without rVFC — so it is the fallback,
    // not the primary.
    video.addEventListener('timeupdate', () => {
      if (!(video as VideoWithFrameCallback).requestVideoFrameCallback) {
        currentTime.value = video.currentTime
        presentedTime.value = video.currentTime
      }
    })
    video.addEventListener('seeked', () => {
      currentTime.value = video.currentTime
    })

    scheduleFrameCallback()
  }

  async function play(): Promise<void> {
    const video = element.value
    if (!video) return
    try {
      await video.play()
    } catch {
      // A rejected play() is normal — autoplay policy, or a source that has not
      // loaded. The element's own 'pause' state remains authoritative, so there
      // is nothing to correct here beyond not crashing.
    }
  }

  function pause(): void {
    element.value?.pause()
  }

  async function toggle(): Promise<void> {
    if (isPlaying.value) pause()
    else await play()
  }

  function seek(seconds: number): void {
    const video = element.value
    if (!video) return
    const bounded = Math.max(0, Math.min(seconds, video.duration || seconds))
    video.currentTime = bounded
    currentTime.value = bounded
  }

  function step(frames: number, frameDuration: number): void {
    const video = element.value
    if (!video) return
    // Stepping only means anything against a still image. Pausing first is what
    // makes "forward one, back one returns to the same frame" true, which is
    // US1's acceptance scenario 4.
    if (!video.paused) video.pause()
    seek(video.currentTime + frames * frameDuration)
  }

  onBeforeUnmount(cancelFrameCallback)

  return {
    isPlaying: readonly(isPlaying),
    currentTime: readonly(currentTime),
    presentedTime: readonly(presentedTime),
    volume,
    muted,
    play,
    pause,
    toggle,
    seek,
    step,
    // Not part of the public contract a view uses, but the surface component
    // has to bind the element at mount. Exposed deliberately rather than run
    // from a watcher inside here: the composable does not own the element's
    // lifecycle, the component does.
    attach
  } as VideoPlayback & { attach: () => void }
}

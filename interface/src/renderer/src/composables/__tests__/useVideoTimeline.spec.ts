import { describe, expect, it } from 'vitest'
import { ref } from 'vue'
import { useVideoTimeline } from '../useVideoTimeline'
import type { MediaHandle } from '../../services/api'

// T022 (specs/007-video-editor-player)

function handle(overrides: Partial<MediaHandle> = {}): MediaHandle {
  return {
    handle_id: 'vh_test',
    display_name: 'curto.mp4',
    duration_seconds: 10,
    width: 1920,
    height: 1080,
    frame_rate: 30,
    frame_rate_is_variable: false,
    has_audio: true,
    size_bytes: 1024,
    content_key: 'abc',
    ...overrides
  }
}

describe('useVideoTimeline', () => {
  it('converts time to frame and back', () => {
    const t = useVideoTimeline(ref(handle()))
    expect(t.frameAt(0)).toBe(0)
    expect(t.frameAt(1)).toBe(30)
    expect(t.timeOfFrame(30)).toBeCloseTo(1)
  })

  it('round-trips a frame index through time', () => {
    // The property the frame-stepping controls depend on: stepping forward and
    // back must land on the frame it started from (US1 acceptance scenario 4).
    const t = useVideoTimeline(ref(handle({ frame_rate: 29.97 })))
    for (const frame of [0, 1, 42, 299]) {
      expect(t.frameAt(t.timeOfFrame(frame)!)).toBe(frame)
    }
  })

  it('reports total frames', () => {
    expect(useVideoTimeline(ref(handle())).totalFrames.value).toBe(300)
  })

  describe('FR-012 — a frame number that cannot be trusted is not shown', () => {
    it('suppresses frame numbers for a variable frame rate', () => {
      const t = useVideoTimeline(ref(handle({ frame_rate_is_variable: true })))
      expect(t.frameNumberIsReliable.value).toBe(false)
      expect(t.frameAt(1)).toBeNull()
      expect(t.timeOfFrame(30)).toBeNull()
      expect(t.totalFrames.value).toBeNull()
    })

    it('suppresses frame numbers when the rate is unknown', () => {
      const t = useVideoTimeline(ref(handle({ frame_rate: null })))
      expect(t.frameNumberIsReliable.value).toBe(false)
      expect(t.frameAt(1)).toBeNull()
    })

    it('suppresses frame numbers when there is no handle at all', () => {
      expect(useVideoTimeline(ref(null)).frameNumberIsReliable.value).toBe(false)
    })

    it('still allows stepping when the frame number is unreliable', () => {
      // Suppressing the NUMBER must not disable the CONTROL: a person can still
      // move through a VFR file, they just are not told a frame index.
      const t = useVideoTimeline(ref(handle({ frame_rate_is_variable: true })))
      expect(t.frameDuration.value).toBeGreaterThan(0)
    })
  })

  describe('progress mapping', () => {
    it('maps time to a 0..1 fraction and back', () => {
      const t = useVideoTimeline(ref(handle()))
      expect(t.progressAt(5)).toBeCloseTo(0.5)
      expect(t.timeAtProgress(0.5)).toBeCloseTo(5)
    })

    it('clamps out-of-range values instead of extrapolating', () => {
      // A drag can leave the element's box; the timeline must not seek past the
      // end or before the start.
      const t = useVideoTimeline(ref(handle()))
      expect(t.progressAt(-5)).toBe(0)
      expect(t.progressAt(999)).toBe(1)
      expect(t.timeAtProgress(-1)).toBe(0)
      expect(t.timeAtProgress(2)).toBe(10)
    })

    it('does not divide by zero for a zero-duration handle', () => {
      const t = useVideoTimeline(ref(handle({ duration_seconds: 0 })))
      expect(t.progressAt(1)).toBe(0)
      expect(t.timeAtProgress(0.5)).toBe(0)
    })
  })

  describe('duration extremes stay usable', () => {
    it('handles a video of a few frames', () => {
      const t = useVideoTimeline(ref(handle({ duration_seconds: 0.1 })))
      expect(t.totalFrames.value).toBe(3)
      expect(t.progressAt(0.05)).toBeCloseTo(0.5)
    })

    it('handles a video of hours without losing precision', () => {
      const threeHours = 3 * 60 * 60
      const t = useVideoTimeline(ref(handle({ duration_seconds: threeHours })))
      // One frame in three hours must still map to a distinguishable position.
      expect(t.progressAt(threeHours / 2)).toBeCloseTo(0.5)
      expect(t.frameAt(threeHours - 1)).toBe(323970)
    })
  })

  describe('formatTime', () => {
    it('omits hours for short material and includes them for long', () => {
      const t = useVideoTimeline(ref(handle()))
      expect(t.formatTime(4)).toBe('00:04')
      expect(t.formatTime(64)).toBe('01:04')
      expect(t.formatTime(3664)).toBe('1:01:04')
    })

    it('survives NaN and negative input', () => {
      // currentTime is NaN before metadata loads; the display must not read
      // "NaN:NaN" during that window.
      const t = useVideoTimeline(ref(handle()))
      expect(t.formatTime(Number.NaN)).toBe('00:00')
      expect(t.formatTime(-5)).toBe('00:00')
    })
  })
})

import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { useVideoPlayback } from '../useVideoPlayback'

// T021 (specs/007-video-editor-player)
//
// happy-dom's HTMLVideoElement has no real decoder: play() does not start
// anything and currentTime is plain state. That is the genuine external
// boundary here (Princípio VIII allows mocking exactly there), so these tests
// drive a stand-in element and assert the composable's own logic — what it
// calls, in what order, with what values. Whether Chromium decodes a frame is
// not this composable's behaviour and is covered by quickstart scenario 1.

interface FakeVideo {
  currentTime: number
  duration: number
  paused: boolean
  volume: number
  muted: boolean
  play: ReturnType<typeof vi.fn>
  pause: ReturnType<typeof vi.fn>
  addEventListener: ReturnType<typeof vi.fn>
  requestVideoFrameCallback?: ReturnType<typeof vi.fn>
  cancelVideoFrameCallback?: ReturnType<typeof vi.fn>
}

function fakeVideo(overrides: Partial<FakeVideo> = {}): FakeVideo {
  const video: FakeVideo = {
    currentTime: 0,
    duration: 10,
    paused: true,
    volume: 1,
    muted: false,
    play: vi.fn(async function (this: FakeVideo) {
      this.paused = false
    }),
    pause: vi.fn(function (this: FakeVideo) {
      this.paused = true
    }),
    addEventListener: vi.fn(),
    ...overrides
  }
  return video
}

type Playback = ReturnType<typeof useVideoPlayback> & { attach: () => void }

function setup(video: FakeVideo = fakeVideo()): { video: FakeVideo; playback: Playback } {
  const element = ref(video as unknown as HTMLVideoElement)
  return { video, playback: useVideoPlayback(element) as Playback }
}

describe('useVideoPlayback', () => {
  describe('transport', () => {
    it('plays and pauses the element', async () => {
      const { video, playback } = setup()
      await playback.play()
      expect(video.play).toHaveBeenCalled()
      playback.pause()
      expect(video.pause).toHaveBeenCalled()
    })

    it('survives a rejected play()', async () => {
      // Autoplay policy rejects play() routinely. A throw here would surface as
      // an unhandled rejection on a perfectly ordinary interaction.
      const video = fakeVideo({ play: vi.fn().mockRejectedValue(new Error('NotAllowedError')) })
      const { playback } = setup(video)
      await expect(playback.play()).resolves.toBeUndefined()
    })

    it('does nothing without an element instead of throwing', () => {
      const playback = useVideoPlayback(ref(null))
      expect(() => playback.pause()).not.toThrow()
      expect(() => playback.seek(5)).not.toThrow()
      expect(() => playback.step(1, 1 / 30)).not.toThrow()
    })
  })

  describe('seeking', () => {
    it('clamps a seek to the video bounds', () => {
      const { video, playback } = setup()
      playback.seek(-5)
      expect(video.currentTime).toBe(0)
      playback.seek(999)
      expect(video.currentTime).toBe(10)
    })
  })

  describe('frame stepping', () => {
    const FRAME = 1 / 30

    it('pauses before stepping', () => {
      // Stepping against a moving picture is a request the element cannot
      // honour; ignoring it silently looks like a broken button.
      const video = fakeVideo({ paused: false })
      const { playback } = setup(video)
      playback.step(1, FRAME)
      expect(video.pause).toHaveBeenCalled()
    })

    it('moves forward and back by exactly one frame', () => {
      const { video, playback } = setup()
      video.currentTime = 1
      playback.step(1, FRAME)
      expect(video.currentTime).toBeCloseTo(1 + FRAME)
      playback.step(-1, FRAME)
      expect(video.currentTime).toBeCloseTo(1)
    })

    it('returns to the starting frame after forward-then-back', () => {
      // US1 acceptance scenario 4, as a property rather than one example.
      const { video, playback } = setup()
      for (const start of [0, 0.5, 3.3333, 9.9]) {
        video.currentTime = start
        playback.step(1, FRAME)
        playback.step(-1, FRAME)
        expect(video.currentTime).toBeCloseTo(Math.min(start, 10), 5)
      }
    })

    it('does not step below zero', () => {
      const { video, playback } = setup()
      video.currentTime = 0
      playback.step(-1, FRAME)
      expect(video.currentTime).toBe(0)
    })
  })

  describe('requestVideoFrameCallback', () => {
    it('reports the presented frame time, not currentTime', () => {
      // The whole reason Decisão 3 exists: currentTime is the browser's
      // approximation, mediaTime is the frame actually shown. When they
      // disagree, the counter must follow mediaTime.
      let registered:
        ((now: number, metadata: { mediaTime: number; presentedFrames: number }) => void) | null =
        null
      const video = fakeVideo({
        requestVideoFrameCallback: vi.fn((cb) => {
          if (!registered) registered = cb
          return 1
        }),
        cancelVideoFrameCallback: vi.fn()
      })
      const { playback } = setup(video)
      playback.attach()

      expect(video.requestVideoFrameCallback).toHaveBeenCalled()
      registered!(0, { mediaTime: 4.2666, presentedFrames: 128 })
      expect(playback.presentedTime.value).toBeCloseTo(4.2666)
      expect(playback.currentTime.value).toBeCloseTo(4.2666)
    })

    it('re-arms so a seek while paused still updates the counter', () => {
      const video = fakeVideo({
        requestVideoFrameCallback: vi.fn(() => 1),
        cancelVideoFrameCallback: vi.fn()
      })
      const { playback } = setup(video)
      playback.attach()
      const callsAfterAttach = video.requestVideoFrameCallback!.mock.calls.length
      const cb = video.requestVideoFrameCallback!.mock.calls[0][0]
      cb(0, { mediaTime: 1, presentedFrames: 1 })
      expect(video.requestVideoFrameCallback!.mock.calls.length).toBeGreaterThan(callsAfterAttach)
    })

    it('falls back to timeupdate when rVFC is unavailable', () => {
      // Not a hypothetical: the composable must not go silent on a runtime
      // without rVFC, it must just be coarser.
      const video = fakeVideo()
      const { playback } = setup(video)
      playback.attach()
      const timeupdate = video.addEventListener.mock.calls.find((c) => c[0] === 'timeupdate')
      expect(timeupdate).toBeDefined()
      video.currentTime = 7
      timeupdate![1]()
      expect(playback.currentTime.value).toBe(7)
    })
  })
})

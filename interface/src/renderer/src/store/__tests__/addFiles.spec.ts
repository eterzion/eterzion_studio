import { nextTick, watch } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Importing files used to read each image's dimensions inside a sequential
// loop: file N waited for all N-1 to finish decoding. Content-type detection is
// fired right after that read, so the last file's detection could not even
// start until every earlier image had decoded — which is what made
// "Detectando…" sit there on a batch. The API answers detection in about 10ms;
// all the waiting was on this side.
//
// These tests hold the reads to a barrier and assert that every one of them has
// started before any is allowed to finish. Sequential code cannot pass that:
// its second read does not exist until the first resolves.

const DECODE_MS = 30

let started = 0
let releaseAll: () => void
let allStarted: Promise<void>

vi.mock('../../services/native', () => ({
  hasNativeApi: true,
  api: { toFileUrl: (path: string) => `astros-media://${path}` }
}))

const detectCalls: string[] = []
let pendingDetection: Promise<string> | null = null
vi.mock('../../services/api', () => ({
  detectContentType: (path: string) => {
    detectCalls.push(path)
    return pendingDetection ?? Promise.resolve('photo')
  },
  createJob: vi.fn(),
  processJob: vi.fn(),
  getJobStatus: vi.fn(),
  exportJob: vi.fn(),
  cancelJob: vi.fn(),
  errorCategoryCopy: () => ({ message: '', action: '' })
}))

vi.mock('../history', () => ({ recordJob: vi.fn(), recordSimpleJob: vi.fn() }))
vi.mock('../settings', () => ({
  settingsState: { defaultScalePreset: 2, defaultLockAspectRatio: true, defaultQuality: 90 }
}))

/** A fake <img> whose load only completes once every pending one has begun. */
class BarrierImage {
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  naturalWidth = 64
  naturalHeight = 64
  set src(_value: string) {
    started += 1
    void allStarted.then(() => setTimeout(() => this.onload?.(), DECODE_MS))
  }
}

function file(name: string): {
  path: string
  name: string
  ext: string
  kind: 'Imagem'
  size: number
} {
  return { path: `D:/fake/${name}`, name, ext: '.png', kind: 'Imagem' as const, size: 1024 }
}

describe('addFiles', () => {
  beforeEach(() => {
    started = 0
    detectCalls.length = 0
    vi.stubGlobal('crypto', { randomUUID: () => Math.random().toString(36).slice(2) })
  })

  it('reads every image at once instead of one after another', async () => {
    const total = 8
    let resolveBarrier: () => void = () => {}
    allStarted = new Promise<void>((r) => (resolveBarrier = r))
    releaseAll = resolveBarrier

    // Let the barrier open only once all reads have been kicked off.
    const poll = setInterval(() => {
      if (started >= total) {
        clearInterval(poll)
        releaseAll()
      }
    }, 1)

    vi.stubGlobal('Image', BarrierImage)
    const { addFiles, queueState } = await import('../jobs')
    queueState.jobs.length = 0

    const files = Array.from({ length: total }, (_, i) => file(`img${i}.png`))
    const result = await addFiles(files)

    clearInterval(poll)
    expect(result.added).toHaveLength(total)
    expect(started).toBe(total)
  })

  it('keeps the order the person picked', async () => {
    allStarted = Promise.resolve()
    vi.stubGlobal('Image', BarrierImage)
    const { addFiles, queueState } = await import('../jobs')
    queueState.jobs.length = 0

    const names = ['c.png', 'a.png', 'b.png']
    const result = await addFiles(names.map(file))
    expect(result.added.map((j) => j.fileName)).toEqual(names)
  })

  it('still catches a duplicate inside the same batch', async () => {
    allStarted = Promise.resolve()
    vi.stubGlobal('Image', BarrierImage)
    const { addFiles, queueState } = await import('../jobs')
    queueState.jobs.length = 0

    const result = await addFiles([file('same.png'), file('same.png')])
    expect(result.added).toHaveLength(1)
    expect(result.duplicates).toEqual(['same.png'])
  })

  it('asks for detection once per accepted file', async () => {
    allStarted = Promise.resolve()
    vi.stubGlobal('Image', BarrierImage)
    const { addFiles, queueState } = await import('../jobs')
    queueState.jobs.length = 0

    await addFiles([file('one.png'), file('two.png')])
    expect(detectCalls).toHaveLength(2)
  })

  it('a render effect runs when detection lands', async () => {
    // The bug: queueState is reactive(), so the array holds Vue's proxy while
    // the local `job` is the raw object underneath. Writing to the raw object
    // updates the value — so merely reading it back proves nothing — but never
    // runs the proxy's set trap, so nothing re-renders. The field stayed on
    // "Detectando…" until an unrelated edit forced a redraw, which is how it
    // was noticed.
    //
    // So this watches for the effect, not the value, and detection is held
    // until after the watcher exists.
    allStarted = Promise.resolve()
    vi.stubGlobal('Image', BarrierImage)
    let releaseDetection: (value: string) => void = () => {}
    pendingDetection = new Promise<string>((r) => (releaseDetection = r))

    const { addFiles, queueState } = await import('../jobs')
    queueState.jobs.length = 0
    await addFiles([file('um.png')])

    let effects = 0
    watch(
      () => queueState.jobs[0]?.scaleConfig.contentType,
      () => (effects += 1)
    )

    releaseDetection('photo')
    await new Promise((r) => setTimeout(r, 10))
    await nextTick()

    expect(queueState.jobs[0].scaleConfig.contentType).toBe('photo')
    expect(effects).toBe(1)
  })
})

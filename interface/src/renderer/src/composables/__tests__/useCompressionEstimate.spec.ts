import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const pedidos: Array<Record<string, unknown>> = []
vi.mock('../../services/compression', async (original) => {
  const real = await original<typeof import('../../services/compression')>()
  return {
    ...real,
    estimate: vi.fn(async (body: Record<string, unknown>) => {
      pedidos.push(body)
      return { estimated_bytes: 1, confidence: 'high', assumptions: [] }
    })
  }
})

import { useCompressionEstimate } from '../useCompressionEstimate'
import type { CompressionMode, MediaKind } from '../../constants/compression'

// A estimativa precisa partir das mesmas configuracoes que a compressao vai
// usar. No modo Basico, o backend resolve o preset e o "Repetir" -- entao a
// estimativa tem que mandar os mesmos ids e o mesmo modo, ou mostra um numero
// que a compressao nao produz.

beforeEach(() => {
  vi.useFakeTimers()
  pedidos.length = 0
})
afterEach(() => vi.useRealTimers())

function montar(): {
  fonte: Parameters<typeof useCompressionEstimate>[0]
  api: ReturnType<typeof useCompressionEstimate>
} {
  const fonte = {
    handleId: ref<string | null>('h'),
    mediaKind: ref<MediaKind>('video'),
    settings: ref({}),
    target: ref(null),
    presetId: ref<string | null>('builtin.video.balanced'),
    historyId: ref<string | null>(null),
    mode: ref<CompressionMode>('basic')
  }
  const api = useCompressionEstimate(fonte)
  return { fonte, api }
}

describe('useCompressionEstimate', () => {
  it('manda o preset, o historico e o modo junto com as configuracoes', async () => {
    const { api } = montar()
    await vi.runAllTimersAsync()
    expect(pedidos.at(-1)).toMatchObject({
      preset_id: 'builtin.video.balanced',
      history_id: null,
      advanced: false
    })
    api.stop()
  })

  it('pede de novo quando a origem ou o modo mudam', async () => {
    const { fonte, api } = montar()
    await vi.runAllTimersAsync()
    const antes = pedidos.length

    fonte.presetId.value = null
    fonte.historyId.value = 'h1'
    await vi.runAllTimersAsync()
    expect(pedidos.length).toBeGreaterThan(antes)
    expect(pedidos.at(-1)).toMatchObject({ preset_id: null, history_id: 'h1' })

    fonte.mode.value = 'advanced'
    await vi.runAllTimersAsync()
    expect(pedidos.at(-1)).toMatchObject({ advanced: true })
    api.stop()
  })
})

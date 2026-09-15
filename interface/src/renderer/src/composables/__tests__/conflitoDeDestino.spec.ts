import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

// "Perguntar" quando o destino ja' existe, igual em todos os modos: o backend
// recusa com 409 `conflict` antes do job (app/destino.py), a tela pergunta, e
// com a resposta pede de novo. Cancelar nao e' erro -- nada foi processado.

const api = vi.hoisted(() => ({
  createVideoEditJob: vi.fn(),
  createLocalJob: vi.fn(),
  getJob: vi.fn(async () => ({ status: 'queued' })),
  processJob: vi.fn(async () => undefined),
  cancelJob: vi.fn()
}))
vi.mock('../../services/api', async (original) => ({
  ...(await original<typeof import('../../services/api')>()),
  ...api
}))

const compressao = vi.hoisted(() => ({ createJob: vi.fn() }))
vi.mock('../../services/compression', async (original) => ({
  ...(await original<typeof import('../../services/compression')>()),
  ...compressao
}))

vi.mock('../../services/websocket', () => ({
  // Fecha logo: o composable cai na consulta final (getJob).
  subscribeJobProgress: (_id: string, _cada: unknown, fim?: () => void) => {
    queueMicrotask(() => fim?.())
    return () => undefined
  }
}))
vi.mock('../../store/history', () => ({ recordSimpleJob: vi.fn() }))

import { usePerguntaDeConflito } from '../usePerguntaDeConflito'
import { useCompressionJob, type RunRequest } from '../useCompressionJob'
import { useCompressionBatch, type BatchRequest } from '../useCompressionBatch'
import { useVideoProcessing, type VideoRequest } from '../useVideoProcessing'
import { CompressionError } from '../../services/compression'
import ConflictDialog from '../../components/ConflictDialog.vue'
import { i18n, setLocale } from '../../i18n'

afterEach(() => vi.clearAllMocks())

// --------------------------------------------------------------- a pergunta --

describe('usePerguntaDeConflito', () => {
  it('abre com o caminho e devolve a resposta', async () => {
    const p = usePerguntaDeConflito()
    const resposta = p.perguntar('C:\\saida\\foto.jpg')
    expect(p.caminho.value).toBe('C:\\saida\\foto.jpg')
    p.responder('overwrite')
    expect(await resposta).toBe('overwrite')
    expect(p.caminho.value).toBeNull()
  })

  it('uma pergunta nova fecha a anterior como cancelada', async () => {
    const p = usePerguntaDeConflito()
    const primeira = p.perguntar('a.jpg')
    const segunda = p.perguntar('b.jpg')
    expect(await primeira).toBeNull()
    p.responder('rename')
    expect(await segunda).toBe('rename')
  })
})

describe('ConflictDialog', () => {
  function montar(): ReturnType<typeof mount> {
    setLocale('pt-BR')
    return mount(ConflictDialog, {
      props: { caminho: 'C:\\saida\\foto.jpg' },
      global: { plugins: [i18n], stubs: { Teleport: true } },
      attachTo: document.body
    })
  }

  it('mostra o nome e a pasta, e cada botao responde', async () => {
    const w = montar()
    expect(w.text()).toContain('foto.jpg')
    expect(w.text()).toContain('C:\\saida')
    const botoes = w.findAll('button')
    await botoes[0].trigger('click')
    await botoes[1].trigger('click')
    await botoes[2].trigger('click')
    expect(w.emitted('responder')).toEqual([['rename'], ['overwrite'], [null]])
    w.unmount()
  })

  it('Esc cancela', async () => {
    const w = montar()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('responder')).toEqual([[null]])
    w.unmount()
  })
})

// --------------------------------------------------------------- Compressao --

function pedidoDeCompressao(): RunRequest {
  return {
    handleId: 'h',
    mediaKind: 'image',
    settings: {},
    target: null,
    mode: 'basic',
    presetId: null,
    historyId: null,
    export: { directory: 'C:\\saida', conflict_policy: 'ask' }
  }
}

const recusaPorConflito = (): CompressionError =>
  new CompressionError(409, 'conflict', { reason: 'conflict', path: 'C:\\saida\\foto.jpg' })

describe('Compressao com "Perguntar"', () => {
  it('pergunta e pede de novo com a resposta', async () => {
    compressao.createJob.mockRejectedValueOnce(recusaPorConflito())
    compressao.createJob.mockResolvedValueOnce({ job_id: 'j1', status: 'queued' })
    const perguntar = vi.fn(async () => 'overwrite' as const)
    const job = useCompressionJob({ perguntarConflito: perguntar })

    await job.run(pedidoDeCompressao())

    expect(perguntar).toHaveBeenCalledWith('C:\\saida\\foto.jpg')
    expect(compressao.createJob).toHaveBeenCalledTimes(2)
    expect(compressao.createJob.mock.calls[1][0].export.conflict_policy).toBe('overwrite')
  })

  it('cancelar nao vira erro nem cria job', async () => {
    compressao.createJob.mockRejectedValueOnce(recusaPorConflito())
    const job = useCompressionJob({ perguntarConflito: async () => null })

    await job.run(pedidoDeCompressao())

    expect(compressao.createJob).toHaveBeenCalledTimes(1)
    expect(job.error.value).toBeNull()
    expect(job.running.value).toBe(false)
  })
})

describe('fila da Compressao com "Perguntar"', () => {
  const pedido = (queueId: string): BatchRequest => ({
    ...pedidoDeCompressao(),
    queueId,
    fileName: `${queueId}.png`
  })

  it('pergunta por arquivo; cancelar um nao para a fila', async () => {
    api.getJob.mockResolvedValue({ status: 'done' })
    compressao.createJob.mockRejectedValueOnce(recusaPorConflito()) // a: pergunta
    compressao.createJob.mockResolvedValueOnce({ job_id: 'ja', status: 'queued' }) // a: de novo
    compressao.createJob.mockRejectedValueOnce(recusaPorConflito()) // b: pergunta, cancela
    compressao.createJob.mockResolvedValueOnce({ job_id: 'jc', status: 'queued' }) // c
    const respostas = ['rename', null] as const
    let n = 0
    const batch = useCompressionBatch({ perguntarConflito: async () => respostas[n++] })

    await batch.run([pedido('a'), pedido('b'), pedido('c')])

    expect(compressao.createJob.mock.calls[1][0].export.conflict_policy).toBe('rename')
    expect(batch.items.value.map((i) => i.status)).toEqual(['done', 'cancelled', 'done'])
  })
})

// -------------------------------------------------------------------- Video --

function pedidoDeVideo(enhance: Partial<VideoRequest['enhance']> = {}): VideoRequest {
  return {
    handleId: 'v1',
    displayName: 'clip.mp4',
    sourcePath: 'C:\\videos\\clip.mp4',
    sourceWidth: 640,
    sourceHeight: 480,
    edits: {} as VideoRequest['edits'],
    enhance: {
      scale: 'custom',
      lockAspectRatio: true,
      customWidth: null,
      customHeight: null,
      contentType: 'no_model',
      profile: 'fast',
      device: 'auto',
      ...enhance
    },
    container: 'webm',
    directory: 'C:\\saida',
    filename: 'capa',
    conflict: 'ask',
    exportProfile: 'quality'
  }
}

function processamento(perguntar: (c: string) => Promise<'rename' | 'overwrite' | null>): {
  processing: ReturnType<typeof useVideoProcessing>
  desmontar: () => void
} {
  let processing!: ReturnType<typeof useVideoProcessing>
  const w = mount(
    defineComponent({
      setup() {
        processing = useVideoProcessing({ perguntarConflito: perguntar })
        return () => h('div')
      }
    })
  )
  return { processing, desmontar: () => w.unmount() }
}

describe('Video com "Perguntar"', () => {
  it('edicao: manda nome, conflito e a qualidade da exportacao; pergunta e repete', async () => {
    api.createVideoEditJob.mockRejectedValueOnce(
      new Error(JSON.stringify({ reason: 'conflict', path: 'C:\\saida\\capa.webm' }))
    )
    api.createVideoEditJob.mockResolvedValueOnce({ job_id: 'j2', status: 'queued' })
    const perguntar = vi.fn(async () => 'rename' as const)
    const { processing, desmontar } = processamento(perguntar)

    await processing.start(pedidoDeVideo())

    expect(perguntar).toHaveBeenCalledWith('C:\\saida\\capa.webm')
    const [primeiro, segundo] = api.createVideoEditJob.mock.calls.map((c) => c[0])
    expect(primeiro).toMatchObject({
      output_directory: 'C:\\saida',
      output_filename: 'capa',
      conflict: 'ask',
      // A "Qualidade" do painel de exportacao, nao a do painel de melhoria.
      profile: 'quality'
    })
    expect(segundo.conflict).toBe('rename')
    desmontar()
  })

  it('upscale: manda o destino, e cancelar volta ao estado neutro', async () => {
    api.createLocalJob.mockRejectedValueOnce(new Error('CONFLICT:C:\\saida\\capa.mp4'))
    const { processing, desmontar } = processamento(async () => null)

    await processing.start(pedidoDeVideo({ contentType: 'real_video', scale: '2x' }))

    expect(api.createLocalJob.mock.calls[0][0].output_target).toEqual({
      format: 'mp4',
      directory: 'C:\\saida',
      filename: 'capa',
      conflict: 'ask'
    })
    expect(api.createLocalJob).toHaveBeenCalledTimes(1)
    expect(processing.states.value.get('v1')?.status).toBe('idle')
    desmontar()
  })
})

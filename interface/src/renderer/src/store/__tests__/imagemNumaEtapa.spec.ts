import { afterEach, describe, expect, it, vi } from 'vitest'

// A Imagem numa etapa so': o destino vai junto com o job, "Perguntar"
// pergunta antes de processar, e o resultado vem do job assim que ele termina
// -- antes ficava vazio ate' a pessoa exportar, e o antes/depois comparava a
// original com ela mesma.

vi.mock('../../services/native', () => ({
  hasNativeApi: true,
  api: { toFileUrl: (path: string) => `eterzion-media://${path}` }
}))

const api = vi.hoisted(() => ({
  createLocalJob: vi.fn(),
  processJob: vi.fn(async () => undefined),
  getJob: vi.fn(),
  cancelJob: vi.fn(),
  detectContentType: vi.fn(async () => 'photo')
}))
vi.mock('../../services/api', async (original) => ({
  ...(await original<typeof import('../../services/api')>()),
  ...api
}))

// O socket "fecha" logo: o store cai na consulta final, que traz o status.
vi.mock('../../services/websocket', () => ({
  subscribeJobProgress: (_id: string, _cada: unknown, fim?: () => void) => {
    queueMicrotask(() => fim?.())
    return () => undefined
  }
}))

const historico = vi.hoisted(() => ({ recordJob: vi.fn(), recordSimpleJob: vi.fn() }))
vi.mock('../history', () => historico)

import { startProcessing, type ImageExport, type Job } from '../jobs'
import { ComponentActionError } from '../../services/api'
import { perfilDaQualidade } from '../settings'
import { setLocale } from '../../i18n'

afterEach(() => vi.clearAllMocks())

function job(): Job {
  return {
    id: 'j',
    backendJobId: null,
    sourcePath: 'C:\\fotos\\foto.png',
    fileName: 'foto.png',
    sourceMeta: { width: 64, height: 64, format: 'PNG', sizeBytes: 100 },
    scaleConfig: {
      mode: 'preset',
      presetFactor: 2,
      customWidth: null,
      customHeight: null,
      lockAspectRatio: true,
      contentType: 'photo',
      profile: 'fast',
      device: 'auto',
      denoise: 50,
      sharpenEnabled: false,
      sharpen: 50,
      faceRecovery: false,
      faceRecoveryStrength: 50,
      denoiseFilterEnabled: false,
      denoiseFilterStrength: 45
    },
    status: 'configuring',
    progress: 0,
    queuePosition: null,
    createdAt: 0
  } as Job
}

const exportacao: ImageExport = {
  format: 'jpg',
  profile: 'quality',
  directory: 'C:\\saida',
  conflict: 'ask'
}

const esperar = (): Promise<void> => new Promise((r) => setTimeout(r, 0))

describe('startProcessing com destino', () => {
  it('manda o destino junto com o job e le o resultado quando termina', async () => {
    api.createLocalJob.mockResolvedValueOnce('b1')
    api.getJob.mockResolvedValueOnce({
      status: 'done',
      progress: 100,
      output_path: 'C:\\saida\\capa.jpg',
      queue_position: null
    })
    const j = job()

    await startProcessing(j, { exportacao, filename: 'capa' })
    await esperar()

    expect(api.createLocalJob.mock.calls[0][0].output_target).toEqual({
      format: 'jpg',
      profile: 'quality',
      directory: 'C:\\saida',
      filename: 'capa',
      conflict: 'ask'
    })
    expect(j.status).toBe('done')
    expect(j.outputPath).toBe('C:\\saida\\capa.jpg')
    // O caminho ja' estava no job quando o Historico registrou o "concluido".
    const feito = historico.recordJob.mock.calls.find((c) => c[1] === 'done')
    expect(feito?.[0].outputPath).toBe('C:\\saida\\capa.jpg')
  })

  it('no conflito pergunta, e com a resposta pede de novo', async () => {
    api.createLocalJob.mockRejectedValueOnce(new Error('CONFLICT:C:\\saida\\foto.jpg'))
    api.createLocalJob.mockResolvedValueOnce('b2')
    api.getJob.mockResolvedValue({ status: 'queued', progress: 0, queue_position: 1 })
    const perguntar = vi.fn(async () => 'overwrite' as const)
    const j = job()

    await startProcessing(j, { exportacao, perguntarConflito: perguntar })

    expect(perguntar).toHaveBeenCalledWith('C:\\saida\\foto.jpg')
    expect(api.createLocalJob.mock.calls[1][0].output_target.conflict).toBe('overwrite')
  })

  it('cancelar a pergunta volta a configurar, sem erro', async () => {
    api.createLocalJob.mockRejectedValueOnce(new Error('CONFLICT:C:\\saida\\foto.jpg'))
    const j = job()

    await startProcessing(j, { exportacao, perguntarConflito: async () => null })

    expect(api.createLocalJob).toHaveBeenCalledTimes(1)
    expect(j.status).toBe('configuring')
    expect(j.errorMessage).toBeUndefined()
  })

  it('a recusa antes do job vira a frase da interface', async () => {
    api.createLocalJob.mockRejectedValueOnce(
      new ComponentActionError('Não há espaço em disco para o resultado.', 'insufficient_disk')
    )
    setLocale('en')
    const j = job()
    await startProcessing(j, { exportacao })
    expect(j.status).toBe('error')
    expect(j.errorMessage).toBe('Not enough disk space for the result.')
    setLocale('pt-BR')
  })
})

describe('qualidade salva como numero vira perfil', () => {
  it('fica com o perfil mais perto', () => {
    expect(perfilDaQualidade(97)).toBe('quality')
    expect(perfilDaQualidade(90)).toBe('balanced')
    expect(perfilDaQualidade(60)).toBe('fast')
  })
})

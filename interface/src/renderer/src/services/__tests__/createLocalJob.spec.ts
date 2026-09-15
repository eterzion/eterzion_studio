import { afterEach, describe, expect, it, vi } from 'vitest'
import { ComponentActionError, createLocalJob, defaultAdjustments } from '../api'

// As recusas de POST /jobs/local chegam a tela em duas formas, e cada tela
// depende de uma: o 422 com `reason` vira ComponentActionError (a frase e' da
// interface, na lingua do app), e o 409 de conflito vira `CONFLICT:<caminho>`
// (a pergunta de conflito le o caminho dali).

function responder(status: number, corpo: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(corpo), { status }))
  )
}

const pedido = {
  media_type: 'audio',
  operation: 'enhance',
  input_path: 'C:\\audio\\voz.mp3'
} as Parameters<typeof createLocalJob>[0]

afterEach(() => vi.unstubAllGlobals())

describe('createLocalJob', () => {
  it('422 com motivo vira ComponentActionError com a chave', async () => {
    responder(422, { detail: { reason: 'insufficient_disk', message: 'Não há espaço.' } })
    const erro = await createLocalJob(pedido, defaultAdjustments()).catch((e) => e)
    expect(erro).toBeInstanceOf(ComponentActionError)
    expect(erro.reason).toBe('insufficient_disk')
  })

  it('409 de conflito continua como CONFLICT:<caminho>', async () => {
    responder(409, { detail: { reason: 'conflict', path: 'C:\\saida\\voz.mp3' } })
    const erro = await createLocalJob(pedido, defaultAdjustments()).catch((e) => e)
    expect(erro).not.toBeInstanceOf(ComponentActionError)
    expect(erro.message).toBe('CONFLICT:C:\\saida\\voz.mp3')
  })

  it('devolve o id no sucesso', async () => {
    responder(200, { id: 'job_1' })
    expect(await createLocalJob(pedido, defaultAdjustments())).toBe('job_1')
  })
})

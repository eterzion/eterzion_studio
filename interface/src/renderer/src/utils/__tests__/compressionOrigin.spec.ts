import { describe, expect, it } from 'vitest'
import { origemParaMidia } from '../compressionOrigin'

// Com o backend resolvendo preset e historico no modo Basico, um id de outra
// midia deixou de ser ignorado e passou a ser recusado. A tela nao pode
// continuar mandando o preset de video depois que a pessoa abriu uma imagem.

describe('origemParaMidia', () => {
  it('descarta o preset de outra midia', () => {
    const r = origemParaMidia(
      {
        presetId: 'builtin.video.balanced',
        presetKind: 'video',
        historyId: null,
        historyKind: null
      },
      'image'
    )
    expect(r).toEqual({ presetId: null, historyId: null })
  })

  it('mantem o preset da mesma midia', () => {
    const r = origemParaMidia(
      {
        presetId: 'builtin.image.balanced',
        presetKind: 'image',
        historyId: null,
        historyKind: null
      },
      'image'
    )
    expect(r.presetId).toBe('builtin.image.balanced')
  })

  it('descarta o registro do historico de outra midia, e mantem o da mesma', () => {
    const origem = {
      presetId: null,
      presetKind: null,
      historyId: 'h1',
      historyKind: 'video' as const
    }
    expect(origemParaMidia(origem, 'audio').historyId).toBeNull()
    expect(origemParaMidia(origem, 'video').historyId).toBe('h1')
  })

  it('preset cujo tipo nao se conhece (lista ainda nao carregou) nao e mandado', () => {
    // Mandar um id sem saber a midia arriscaria a recusa que isto existe para evitar.
    const r = origemParaMidia(
      { presetId: 'user.x', presetKind: null, historyId: null, historyKind: null },
      'image'
    )
    expect(r.presetId).toBeNull()
  })
})

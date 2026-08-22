import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ADVANCED_ONLY, AUTO, ORIGINAL, useCompressionSettings } from '../useCompressionSettings'

// specs/008-compression-centre — T029.
//
// O teste que importa aqui é o último: `ADVANCED_ONLY` existe dos dois lados da
// API, e as duas listas divergirem em silêncio é o defeito caro. O backend
// recusaria um campo que a interface deixou passar, e a pessoa veria um 422 que
// não causou.

describe('useCompressionSettings', () => {
  it('começa no modo Básico', () => {
    // FR-038, e constitucional: a condição 2 da exceção do Princípio V exige
    // que quem nunca abrir o Avançado jamais encontre um nome de codec.
    const { mode } = useCompressionSettings()
    expect(mode.value).toBe('basic')
  })

  it('guarda um estado por tipo de mídia', () => {
    const { mediaKind, settings, set } = useCompressionSettings()
    set('quality', 42)
    mediaKind.value = 'audio'
    expect(settings.value.quality).toBe(70)
    mediaKind.value = 'image'
    expect(settings.value.quality).toBe(42)
  })

  it('omite auto e original do pedido em vez de mandá-los', () => {
    // `auto` é convenção da interface. Mandá-la obrigaria o backend a
    // conhecê-la, e ausente já quer dizer exatamente isso no schema.
    const { mediaKind, mode, payload, settings } = useCompressionSettings()
    mediaKind.value = 'video'
    mode.value = 'advanced'
    expect(settings.value.video_codec).toBe(AUTO)
    expect(settings.value.fps).toBe(ORIGINAL)
    expect(payload.value).not.toHaveProperty('video_codec')
    expect(payload.value).not.toHaveProperty('fps')
  })

  it('no modo Básico não deixa campo técnico chegar ao pedido', () => {
    const { mediaKind, mode, set, payload } = useCompressionSettings()
    mediaKind.value = 'video'
    mode.value = 'advanced'
    set('video_codec', 'av1')
    expect(payload.value.video_codec).toBe('av1')

    mode.value = 'basic'
    // O campo continua no estado — voltar ao Avançado tem que devolver a
    // escolha — mas não viaja. Sem este filtro, uma troca de modo transformaria
    // um pedido válido em 422 que a pessoa não causou.
    expect(payload.value).not.toHaveProperty('video_codec')
  })

  it('aplicar um preset parte dos padrões, não do que estava', () => {
    // Mesclar com o estado atual deixaria resíduo do preset anterior, e o
    // resultado não seria nenhum dos dois.
    const { mediaKind, settings, set, applyPreset } = useCompressionSettings()
    mediaKind.value = 'image'
    set('quality', 10)
    set('metadata_policy', 'strip_all')
    applyPreset('image', { quality: 95 })
    expect(settings.value.quality).toBe(95)
    expect(settings.value.metadata_policy).toBe('essential_only')
  })

  it('a lista de campos técnicos é a mesma do backend', () => {
    // A duplicação existe porque não há geração de tipos entre Python e
    // TypeScript. Enquanto existir, ela precisa desta verificação.
    const fonte = readFileSync(
      resolve(__dirname, '../../../../../../api/astros_upscale_api/app/compression/runner.py'),
      'utf-8'
    )
    const bloco = fonte.match(/_ADVANCED_ONLY_FIELDS = frozenset\(\{([\s\S]*?)\}\)/)
    expect(bloco, 'bloco _ADVANCED_ONLY_FIELDS não encontrado em runner.py').toBeTruthy()

    const doBackend = new Set([...bloco![1].matchAll(/'([a-z_]+)'/g)].map((m) => m[1]))
    expect([...doBackend].sort()).toEqual([...ADVANCED_ONLY].sort())
  })
})

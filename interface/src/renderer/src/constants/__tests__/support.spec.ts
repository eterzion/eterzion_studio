import { describe, expect, it } from 'vitest'
import { SUPPORT_ENDPOINTS, configuredSupportLinks, type SupportEndpoints } from '../support'

const filled: SupportEndpoints = {
  site: 'https://exemplo.test/produto',
  discord: 'https://discord.gg/abc123',
  faq: 'https://exemplo.test/faq',
  help: 'https://exemplo.test/ajuda',
  email: 'suporte@exemplo.test'
}

describe('configuredSupportLinks', () => {
  it('não devolve nada quando nenhum canal tem endereço', () => {
    expect(configuredSupportLinks({ site: '', discord: '', faq: '', help: '', email: '' })).toEqual(
      []
    )
  })

  it('devolve só os canais preenchidos, na ordem de exibição', () => {
    const links = configuredSupportLinks({ ...filled, discord: '', help: '' })
    expect(links.map((link) => link.key)).toEqual(['site', 'faq', 'email'])
  })

  it('monta o mailto: do e-mail e deixa as demais URLs intactas', () => {
    const links = configuredSupportLinks(filled)
    expect(links.find((link) => link.key === 'email')?.url).toBe('mailto:suporte@exemplo.test')
    expect(links.find((link) => link.key === 'site')?.url).toBe('https://exemplo.test/produto')
  })

  it('trata espaço em branco como endereço ausente', () => {
    expect(
      configuredSupportLinks({ ...filled, site: '   ' }).some((link) => link.key === 'site')
    ).toBe(false)
  })

  it('nunca deixa um endereço de exemplo chegar à sidebar', () => {
    // Estes cinco endereços eram literais em AppSidebar.vue sob um TODO(config),
    // e um TODO não impede um build. Este teste impede.
    for (const [key, value] of Object.entries(SUPPORT_ENDPOINTS)) {
      expect(value, key).not.toMatch(/example\.(com|org|net)|discord\.gg\/example/i)
    }
  })
})

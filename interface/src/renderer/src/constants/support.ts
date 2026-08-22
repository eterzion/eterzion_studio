// Os endereços dos canais de suporte moram aqui, e só aqui.
//
// Até 2026-08-21 os cinco eram placeholders `example.com` escritos direto em
// AppSidebar.vue, sob um `TODO(config): substituir antes de publicar`. Um TODO
// não impede um build: qualquer versão publicada abriria o navegador do usuário
// num endereço inexistente.
//
// A regra agora é outra: **string vazia significa "esse canal ainda não
// existe", e o link não é renderizado**. Preencher a string é a única coisa
// necessária para o link aparecer — nenhuma outra mudança de código. Enquanto
// todas estiverem vazias, o bloco Suporte inteiro some da sidebar, que é
// preferível a um menu que abre sem nada dentro.

export interface SupportEndpoints {
  /** Página do produto. URL absoluta (`https://…`). */
  site: string
  /** Convite do servidor. URL absoluta (`https://discord.gg/…`). */
  discord: string
  /** Perguntas frequentes. URL absoluta. */
  faq: string
  /** Central de ajuda. URL absoluta. */
  help: string
  /** Endereço de e-mail puro, sem `mailto:` — o esquema é montado abaixo. */
  email: string
}

export const SUPPORT_ENDPOINTS: SupportEndpoints = {
  site: '',
  discord: '',
  faq: '',
  help: '',
  email: ''
}

/** Ordem de exibição na sidebar. Explícita, para não depender da ordem das
 * chaves do objeto acima. */
const DISPLAY_ORDER: (keyof SupportEndpoints)[] = ['site', 'discord', 'faq', 'help', 'email']

export interface SupportLink {
  key: keyof SupportEndpoints
  url: string
}

/** Os canais que têm endereço, na ordem de exibição. O e-mail sai daqui já como
 * `mailto:` porque é o que `window.open` precisa receber; guardá-lo assim na
 * config faria a entrada parecer uma URL, que não é. */
export function configuredSupportLinks(endpoints: SupportEndpoints = SUPPORT_ENDPOINTS): SupportLink[] {
  return DISPLAY_ORDER.map((key) => {
    const value = endpoints[key].trim()
    return { key, url: key === 'email' && value ? `mailto:${value}` : value }
  }).filter((link) => link.url !== '')
}

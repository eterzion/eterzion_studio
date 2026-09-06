import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import AppSidebar from '../AppSidebar.vue'

// O logo da marca é servido pelo CDN, e as duas formas de errá-lo são mudas.
//
// **A primeira já aconteceu:** o caminho era `/branding/logo-256.webp`, que não
// existe — a convenção do CDN é um diretório por variante. E a raiz do host tem
// fallback de SPA, então pedir uma imagem devolvia `200 text/html` em vez de
// 404. Nem o código de status denunciava.
//
// **A segunda é ler o sufixo ao contrário.** Ele nomeia o tema a que a arte
// serve, não a cor da tinta: `logo-dark` tem traço claro, para fundo escuro.
// Trocar os dois desenha o logo na cor do próprio fundo — ele não some com
// erro, apenas deixa de ser visível, e o console fica limpo.
//
// Por isso o teste fixa a URL inteira e o par tema→variante, e não só o host.

const i18n = createI18n({ legacy: false, locale: 'en', missingWarn: false, fallbackWarn: false })

const BASE = 'https://cdn.eterzion.com/branding'

function logoSrc(darkMode: boolean): string {
  const wrapper = mount(AppSidebar, {
    props: { active: 'home' as const, darkMode },
    global: { plugins: [i18n], stubs: { AppButton: true } }
  })
  const src = wrapper.get('img.brand-logo').attributes('src')
  wrapper.unmount()
  return src ?? ''
}

describe('AppSidebar — logo da marca', () => {
  it('usa a arte de traço claro no tema escuro', () => {
    expect(logoSrc(true)).toBe(`${BASE}/ez-logo-white/logo-256.webp`)
  })

  it('usa a arte de traço escuro no tema claro', () => {
    expect(logoSrc(false)).toBe(`${BASE}/ez-logo-black/logo-256.webp`)
  })

  it('nunca aponta para a raiz do host, onde o fallback de SPA devolve HTML', () => {
    for (const dark of [true, false]) {
      // Um caminho de um único segmento cai no index.html do CDN com status 200.
      expect(new URL(logoSrc(dark)).pathname.split('/').filter(Boolean).length).toBeGreaterThan(1)
    }
  })

  // O host da marca vive em DOIS lugares que precisam mudar juntos: a URL
  // acima e o `img-src` do CSP em `index.html`. Mudar só a URL não produz erro
  // de rede -- o navegador bloqueia a imagem e sobra um espaço vazio, com o
  // console limpo se ninguém estiver olhando a aba de segurança.
  //
  // Isso já custou duas migrações (`assets.ericinacio.com` em 13/08/2026,
  // `assets.eterzion.com` em 06/09/2026). E o CSP viaja dentro do pacote, então
  // o erro só aparece depois de instalar -- tarde demais para consertar sem
  // publicar outra versão.
  it('tem o host do logo liberado no img-src do CSP', () => {
    // Resolvido a partir da raiz do projeto, e nao de `import.meta.url`: sob o
    // Vitest esta URL nao tem esquema `file:`, e `fileURLToPath` lanca.
    const caminho = resolve(process.cwd(), 'src/renderer/index.html')
    const html = readFileSync(caminho, 'utf8')
    // Aspas duplas apenas: o proprio CSP usa aspas simples (`'self'`), e uma
    // classe que as exclua para a captura no primeiro `'self'`.
    const csp = /content="([^"]*default-src[^"]*)"/.exec(html)?.[1]
    expect(csp, 'CSP nao encontrado em index.html').toBeTruthy()

    const imgSrc = /img-src ([^;]*)/.exec(csp!)?.[1]
    expect(imgSrc, 'img-src ausente no CSP').toBeTruthy()

    for (const dark of [true, false]) {
      expect(imgSrc).toContain(new URL(logoSrc(dark)).origin)
    }
  })
})

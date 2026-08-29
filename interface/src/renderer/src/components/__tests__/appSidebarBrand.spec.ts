import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
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

const BASE = 'https://assets.eterzion.com/branding'

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
    expect(logoSrc(true)).toBe(`${BASE}/astros-logo-dark/logo-256.webp`)
  })

  it('usa a arte de traço escuro no tema claro', () => {
    expect(logoSrc(false)).toBe(`${BASE}/astros-logo-light/logo-256.webp`)
  })

  it('nunca aponta para a raiz do host, onde o fallback de SPA devolve HTML', () => {
    for (const dark of [true, false]) {
      // Um caminho de um único segmento cai no index.html do CDN com status 200.
      expect(new URL(logoSrc(dark)).pathname.split('/').filter(Boolean).length).toBeGreaterThan(1)
    }
  })
})

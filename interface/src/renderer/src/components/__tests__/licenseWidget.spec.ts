import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'

const { estado, desativar } = vi.hoisted(() => ({
  estado: {
    status: 'active',
    installationsUsed: 2,
    installationsLimit: 3,
    offlineDaysRemaining: null as number | null,
    licenseLast4: null as string | null,
    email: null as string | null,
    error: null as string | null,
    everUsable: true
  },
  desativar: vi.fn(() => Promise.resolve())
}))
vi.mock('../../store/license', () => ({
  licenseState: reactive(estado),
  deactivateLicense: desativar
}))

import { mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import LicenseWidget from '../LicenseWidget.vue'
import ptBR from '../../i18n/locales/pt-BR.json'

// Desativar libera a instalacao e devolve o app a' tela de ativacao. O popover
// fixa duas garantias: o primeiro clique nunca desativa, e uma confirmacao
// abandonada nao sobrevive ao popover fechar.

const i18n = createI18n({ legacy: false, locale: 'pt-BR', messages: { 'pt-BR': ptBR } })

function abrir(): VueWrapper {
  const wrapper = mount(LicenseWidget, { global: { plugins: [i18n] }, attachTo: document.body })
  return wrapper
}

function botao(wrapper: VueWrapper, texto: string): DOMWrapper<HTMLButtonElement> {
  const achado = wrapper.findAll('button').find((b) => b.text() === texto)
  if (!achado) throw new Error(`botao "${texto}" nao encontrado`)
  return achado
}

describe('LicenseWidget', () => {
  beforeEach(() => {
    desativar.mockClear()
    estado.status = 'active'
    estado.licenseLast4 = null
    estado.email = null
  })

  it('mostra o final da chave, mascarado, e o e-mail da compra', async () => {
    estado.licenseLast4 = '3f2a'
    estado.email = 'cliente@example.com'
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    expect(wrapper.get('.license-key').text()).toBe('••••3f2a')
    expect(wrapper.text()).toContain('cliente@example.com')
    wrapper.unmount()
  })

  it('sem esses dados (offline, servidor antigo), nao mostra as linhas', async () => {
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    expect(wrapper.find('.license-facts').exists()).toBe(false)
    wrapper.unmount()
  })

  it('mostra as instalacoes como "usadas de limite"', async () => {
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    expect(wrapper.get('.section-value').text()).toBe('2 de 3')
    wrapper.unmount()
  })

  it('pede confirmacao antes de desativar', async () => {
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    await botao(wrapper, ptBR.license.deactivate).trigger('click')
    expect(desativar).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(ptBR.license.deactivateConfirm)

    await botao(wrapper, ptBR.license.deactivateConfirmAction).trigger('click')
    expect(desativar).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('cancelar ou fechar o popover desarma a confirmacao', async () => {
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    await botao(wrapper, ptBR.license.deactivate).trigger('click')
    await botao(wrapper, ptBR.license.cancel).trigger('click')
    expect(wrapper.text()).not.toContain(ptBR.license.deactivateConfirm)

    await botao(wrapper, ptBR.license.deactivate).trigger('click')
    await wrapper.get('.license-pill').trigger('click')
    await wrapper.get('.license-pill').trigger('click')
    expect(wrapper.text()).not.toContain(ptBR.license.deactivateConfirm)
    expect(desativar).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('sem licenca ativa nao oferece desativar', async () => {
    estado.status = 'not_configured'
    const wrapper = abrir()
    await wrapper.get('.license-pill').trigger('click')
    expect(wrapper.findAll('button').some((b) => b.text() === ptBR.license.deactivate)).toBe(false)
    wrapper.unmount()
  })
})

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

import en from '../../i18n/locales/en.json'

/**
 * A tela de Componentes é a única superfície onde o usuário decide o que ocupa
 * disco na máquina dele. Três coisas precisam continuar valendo:
 *
 *  1. **Nunca mostrar identificador técnico** (FR-009/FR-063). O backend já
 *     separa isso — `GET /components` não traz `technical_name`, só `/details`
 *     traz. Mas a tela recebe o objeto de detalhes quando busca um erro, e
 *     bastaria interpolá-lo por engano para vazar `nomos-webphoto` na lista.
 *  2. **A falha em segundo plano precisa chegar.** O `POST /install` responde
 *     200 e só depois a thread cai; se a tela não for buscar o motivo em
 *     `/details`, o item volta para "não instalado" sem explicação alguma.
 *  3. **A recusa do backend é a mensagem certa.** `speech` e `music` respondem
 *     422 explicando por quê — texto melhor que qualquer genérico local.
 */

const listComponents = vi.fn()
const getComponentDetails = vi.fn()
const installComponent = vi.fn()
const updateComponent = vi.fn()
const uninstallComponent = vi.fn()
// A tela pede ao serviço a frase de uma falha de download; o padrão aqui é
// "não é download" (null), e o teste de download abaixo define a frase.
const downloadErrorCopy = vi.fn()

vi.mock('../../services/api', () => ({
  listComponents: (...a: unknown[]) => listComponents(...a),
  getComponentDetails: (...a: unknown[]) => getComponentDetails(...a),
  installComponent: (...a: unknown[]) => installComponent(...a),
  updateComponent: (...a: unknown[]) => updateComponent(...a),
  uninstallComponent: (...a: unknown[]) => uninstallComponent(...a),
  downloadErrorCopy: (...a: unknown[]) => downloadErrorCopy(...a)
}))

import ComponentsView from '../ComponentsView.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en },
  missingWarn: false,
  fallbackWarn: false
})

function componente(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'photo',
    capability_label: 'Melhoria de imagem — Foto',
    size_mb: 0,
    install_state: 'not_installed',
    update_available: false,
    ...over
  }
}

async function montar(): Promise<ReturnType<typeof mount>> {
  const wrapper = mount(ComponentsView, {
    global: { plugins: [i18n], stubs: { TopBar: true } }
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  listComponents.mockReset().mockResolvedValue([componente()])
  getComponentDetails.mockReset()
  installComponent.mockReset().mockResolvedValue(componente({ install_state: 'installing' }))
  updateComponent.mockReset().mockResolvedValue(componente())
  uninstallComponent.mockReset().mockResolvedValue(componente())
  downloadErrorCopy.mockReset().mockReturnValue(null)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('ComponentsView — o que a lista mostra', () => {
  it('usa o rótulo traduzido da capacidade, não o texto fixo da API', async () => {
    const wrapper = await montar()
    // A API devolve `capability_label` em português fixo; a tela roda em onze
    // idiomas e por isso lê de `credits.*`.
    expect(wrapper.text()).toContain(en.credits.imagePhoto)
    expect(wrapper.text()).not.toContain('Melhoria de imagem')
    wrapper.unmount()
  })

  it('nunca mostra o identificador técnico, mesmo tendo os detalhes em mãos', async () => {
    listComponents
      .mockResolvedValueOnce([componente({ install_state: 'installing' })])
      .mockResolvedValue([componente({ install_state: 'not_installed' })])
    getComponentDetails.mockResolvedValue({
      ...componente(),
      technical_name: 'nomos-webphoto',
      version: '1.0',
      provenance: 'x',
      license: 'CC-BY-4.0',
      error: 'pip falhou: disco cheio'
    })

    const wrapper = await montar()
    await vi.advanceTimersByTimeAsync(2100)
    await flushPromises()

    expect(wrapper.text()).toContain('pip falhou: disco cheio')
    expect(wrapper.text()).not.toContain('nomos-webphoto')
    wrapper.unmount()
  })

  it('falha de download mostra a frase do motivo, nunca o texto cru com link', async () => {
    // O caso real: um 429 da origem aparecia como "Todas as fontes de download
    // falharam para 2xHFA2kSPAN.safetensors: ... https://huggingface.co/...".
    listComponents
      .mockResolvedValueOnce([componente({ install_state: 'installing' })])
      .mockResolvedValue([componente({ install_state: 'not_installed' })])
    getComponentDetails.mockResolvedValue({
      ...componente(),
      technical_name: 'hfa2k-span',
      version: '1.0',
      provenance: 'x',
      license: 'CC-BY-4.0',
      error: 'O servidor de download está recebendo muitos pedidos agora.',
      error_reason: 'rate_limited'
    })
    downloadErrorCopy.mockImplementation((reason: string) =>
      reason === 'rate_limited'
        ? { message: 'The download server is busy.', action: 'Try again in a few minutes.' }
        : null
    )

    const wrapper = await montar()
    await vi.advanceTimersByTimeAsync(2100)
    await flushPromises()

    expect(downloadErrorCopy).toHaveBeenCalledWith('rate_limited')
    expect(wrapper.text()).toContain('The download server is busy. Try again in a few minutes.')
    expect(wrapper.text()).not.toContain('servidor de download está recebendo')
    expect(wrapper.text()).not.toContain('http')
    expect(wrapper.text()).not.toContain('hfa2k-span')
    wrapper.unmount()
  })

  it('música recusada mostra a frase traduzida, não o texto do backend', async () => {
    // O backend responde 422 com motivo; a frase sai na língua do app. Antes
    // a tela mostrava "Configure-a manualmente seguindo api/README.md (venv
    // próprio, checkpoint do modelo, variável HF_TOKEN)".
    listComponents.mockResolvedValue([componente({ id: 'music' })])
    installComponent.mockRejectedValue(
      Object.assign(new Error('mensagem só em português'), { reason: 'not_available_in_app' })
    )

    const wrapper = await montar()
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Not available in this version of the app yet.')
    expect(wrapper.text()).not.toContain('mensagem só em português')
    expect(wrapper.text()).not.toContain('README')
    wrapper.unmount()
  })

  it('mostra o tamanho apenas do que está instalado', async () => {
    listComponents.mockResolvedValue([
      componente({ install_state: 'installed', size_mb: 68 }),
      componente({ id: 'music', install_state: 'not_installed', size_mb: 0 })
    ])
    const wrapper = await montar()
    expect(wrapper.text()).toContain('68 MB')
    wrapper.unmount()
  })
})

describe('ComponentsView — ações', () => {
  it('oferece instalar quando não está instalado, e remover quando está', async () => {
    // Compara os BOTÕES e não o texto da tela: "Installed" contém "Install",
    // então procurar a palavra solta daria um falso positivo.
    const botoes = (w: ReturnType<typeof mount>): string[] =>
      w.findAll('.row-btn').map((b) => b.text())

    const wrapper = await montar()
    expect(botoes(wrapper)).toEqual([en.components.actions.install])
    wrapper.unmount()

    listComponents.mockResolvedValue([componente({ install_state: 'installed', size_mb: 68 })])
    const instalado = await montar()
    expect(botoes(instalado)).toEqual([en.components.actions.remove])
    instalado.unmount()

    listComponents.mockResolvedValue([
      componente({ install_state: 'update_available', size_mb: 68 })
    ])
    const desatualizado = await montar()
    expect(botoes(desatualizado)).toEqual([
      en.components.actions.update,
      en.components.actions.remove
    ])
    desatualizado.unmount()
  })

  it('exige uma segunda confirmação antes de remover', async () => {
    listComponents.mockResolvedValue([componente({ install_state: 'installed', size_mb: 68 })])
    const wrapper = await montar()

    await wrapper.get('.row-btn-danger').trigger('click')
    // Remover apaga arquivos: o primeiro clique só arma a confirmação.
    expect(uninstallComponent).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain(en.components.actions.confirmRemove)

    await wrapper.get('.row-btn-danger').trigger('click')
    expect(uninstallComponent).toHaveBeenCalledWith('photo')
    wrapper.unmount()
  })

  it('mostra a recusa do backend em vez de um texto genérico', async () => {
    listComponents.mockResolvedValue([componente({ id: 'music' })])
    installComponent.mockRejectedValue(
      new Error('SonicMaster roda de um venv isolado; veja api/README.md')
    )
    const wrapper = await montar()

    await wrapper.get('.row-btn').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('SonicMaster roda de um venv isolado')
    expect(wrapper.text()).not.toContain(en.components.errors.actionFailed)
    wrapper.unmount()
  })
})

describe('ComponentsView — consulta periódica', () => {
  it('consulta enquanto instala e para quando termina', async () => {
    listComponents
      .mockResolvedValueOnce([componente({ install_state: 'installing' })])
      .mockResolvedValueOnce([componente({ install_state: 'installing' })])
      .mockResolvedValue([componente({ install_state: 'installed', size_mb: 68 })])

    const wrapper = await montar()
    const inicial = listComponents.mock.calls.length

    await vi.advanceTimersByTimeAsync(2100)
    await flushPromises()
    expect(listComponents.mock.calls.length).toBeGreaterThan(inicial)

    await vi.advanceTimersByTimeAsync(2100)
    await flushPromises()
    const aposConcluir = listComponents.mock.calls.length

    // Já instalado: nada mais a esperar, e um timer que sobrevive gastaria
    // requisição a cada dois segundos pelo resto da sessão.
    await vi.advanceTimersByTimeAsync(6000)
    await flushPromises()
    expect(listComponents.mock.calls.length).toBe(aposConcluir)
    wrapper.unmount()
  })

  it('não deixa o timer vivo depois de sair da tela', async () => {
    listComponents.mockResolvedValue([componente({ install_state: 'installing' })])
    const wrapper = await montar()
    await vi.advanceTimersByTimeAsync(2100)
    await flushPromises()

    wrapper.unmount()
    const aposDesmontar = listComponents.mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    await flushPromises()
    expect(listComponents.mock.calls.length).toBe(aposDesmontar)
  })
})

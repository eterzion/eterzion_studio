// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  gravarEstado,
  instaladorPediuModelos,
  lerEstado,
  registrarPedidoDoInstalador
} from '../installerOptions'

// O pedido do instalador ("baixar os modelos depois de ativar") contra
// arquivos de verdade. O que precisa valer: o pedido vira estado da conta uma
// vez so', sobrevive a' atualizacao que apaga o arquivo do instalador, e nunca
// faz voltar um modelo que a pessoa ja' tinha dado por concluido.

let raiz: string
let pastaDoApp: string
let userData: string
beforeEach(() => {
  raiz = mkdtempSync(join(tmpdir(), 'eterzion-instalador-'))
  pastaDoApp = join(raiz, 'Programs', 'eterzion-studio')
  userData = join(raiz, 'Roaming', 'eterzion-studio')
  mkdirSync(pastaDoApp, { recursive: true })
})
afterEach(() => rmSync(raiz, { recursive: true, force: true }))

// O mesmo conteudo que o customInstall do installer.nsh grava.
function instaladorMarcou(): void {
  writeFileSync(
    join(pastaDoApp, 'installer-options.json'),
    '{"downloadModelsAfterActivation":true}'
  )
}

describe('instaladorPediuModelos', () => {
  it('le o arquivo que o instalador grava', () => {
    instaladorMarcou()
    expect(instaladorPediuModelos(pastaDoApp)).toBe(true)
  })

  it('sem o arquivo, ou com ele corrompido, nao pede nada', () => {
    expect(instaladorPediuModelos(pastaDoApp)).toBe(false)
    writeFileSync(join(pastaDoApp, 'installer-options.json'), '{corrompido')
    expect(instaladorPediuModelos(pastaDoApp)).toBe(false)
    writeFileSync(
      join(pastaDoApp, 'installer-options.json'),
      '{"downloadModelsAfterActivation":"sim"}'
    )
    expect(instaladorPediuModelos(pastaDoApp)).toBe(false)
  })
})

describe('registrarPedidoDoInstalador', () => {
  it('o pedido vira estado da conta', () => {
    instaladorMarcou()
    expect(registrarPedidoDoInstalador(pastaDoApp, userData)).toBe('pendente')
    expect(lerEstado(userData)).toBe('pendente')
  })

  it('continua pendente depois que a atualizacao apaga o arquivo do instalador', () => {
    instaladorMarcou()
    registrarPedidoDoInstalador(pastaDoApp, userData)
    rmSync(join(pastaDoApp, 'installer-options.json'))
    expect(registrarPedidoDoInstalador(pastaDoApp, userData)).toBe('pendente')
  })

  it('concluido nao volta a pendente, nem com o instalador pedindo de novo', () => {
    // Quem removeu um modelo pela tela de Componentes nao quer ve-lo voltar.
    gravarEstado(userData, 'concluido')
    instaladorMarcou()
    expect(registrarPedidoDoInstalador(pastaDoApp, userData)).toBe('concluido')
  })

  it('instalacao sem o pedido (caixa desmarcada, ou versao antiga) nao cria estado', () => {
    expect(registrarPedidoDoInstalador(pastaDoApp, userData)).toBeNull()
    expect(lerEstado(userData)).toBeNull()
  })
})

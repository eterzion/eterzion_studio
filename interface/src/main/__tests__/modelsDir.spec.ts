// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { localDataDir, migrarPastaDeModelos } from '../modelsDir'

// Contra o sistema de arquivos de verdade, numa pasta temporaria: o que pode
// dar errado aqui e' justamente rename, pasta vazia e permissao, que um mock
// descreveria do jeito que se imagina e nao do jeito que o sistema faz.

let raiz: string
beforeEach(() => {
  raiz = mkdtempSync(join(tmpdir(), 'eterzion-modelos-'))
})
afterEach(() => {
  rmSync(raiz, { recursive: true, force: true })
})

function modelo(dir: string, nome = 'realesrgan.pth', conteudo = 'pesos'): void {
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, nome), conteudo)
}

describe('localDataDir', () => {
  it('Windows: %LOCALAPPDATA%, que nao viaja com o perfil movel', () => {
    const d = localDataDir({
      platform: 'win32',
      env: {
        LOCALAPPDATA: 'C:\\Users\\u\\AppData\\Local',
        APPDATA: 'C:\\Users\\u\\AppData\\Roaming'
      },
      homedir: 'C:\\Users\\u'
    })
    expect(d).toBe(join('C:\\Users\\u\\AppData\\Local', 'eterzion-studio'))
    expect(d).not.toContain('Roaming')
  })

  it('Windows sem LOCALAPPDATA cai no caminho padrao, e nao no Roaming', () => {
    const d = localDataDir({ platform: 'win32', env: {}, homedir: 'C:\\Users\\u' })
    expect(d).toBe(join('C:\\Users\\u', 'AppData', 'Local', 'eterzion-studio'))
  })

  it('Linux: $XDG_DATA_HOME quando absoluto', () => {
    const d = localDataDir({
      platform: 'linux',
      env: { XDG_DATA_HOME: '/dados' },
      homedir: '/home/u'
    })
    expect(d).toBe(join('/dados', 'eterzion-studio'))
  })

  it('Linux: ~/.local/share sem XDG_DATA_HOME, ou com um relativo', () => {
    // A especificacao XDG manda ignorar caminho relativo.
    for (const env of [{}, { XDG_DATA_HOME: 'relativo/x' }]) {
      const d = localDataDir({ platform: 'linux', env, homedir: '/home/u' })
      expect(d).toBe(join('/home/u', '.local', 'share', 'eterzion-studio'))
    }
  })
})

describe('migrarPastaDeModelos', () => {
  it('move a pasta antiga para a nova, com o conteudo intacto', () => {
    const antiga = join(raiz, 'Roaming', 'eterzion-studio', 'models')
    const nova = join(raiz, 'Local', 'eterzion-studio', 'models')
    modelo(antiga, 'a.pth', 'AAA')
    modelo(join(antiga, 'voz'), 'b.onnx', 'BBB')

    const m = migrarPastaDeModelos(antiga, nova)

    expect(m).toEqual({ dir: nova, resultado: 'movida' })
    expect(existsSync(antiga)).toBe(false)
    expect(readFileSync(join(nova, 'a.pth'), 'utf8')).toBe('AAA')
    expect(readFileSync(join(nova, 'voz', 'b.onnx'), 'utf8')).toBe('BBB')
  })

  it('move mesmo quando uma abertura anterior ja criou a pasta nova vazia', () => {
    // No Windows, rename sobre uma pasta existente falha com EPERM.
    const antiga = join(raiz, 'antiga')
    const nova = join(raiz, 'nova')
    modelo(antiga)
    mkdirSync(nova)

    expect(migrarPastaDeModelos(antiga, nova).resultado).toBe('movida')
    expect(existsSync(join(nova, 'realesrgan.pth'))).toBe(true)
  })

  it('sem pasta antiga, cria a nova e segue', () => {
    const nova = join(raiz, 'Local', 'eterzion-studio', 'models')
    expect(migrarPastaDeModelos(join(raiz, 'nao-existe'), nova)).toEqual({
      dir: nova,
      resultado: 'nada-a-mover'
    })
    expect(existsSync(nova)).toBe(true)
  })

  it('ja migrada: usa a nova e nao toca na antiga', () => {
    const antiga = join(raiz, 'antiga')
    const nova = join(raiz, 'nova')
    modelo(nova, 'novo.pth')
    modelo(antiga, 'velho.pth')

    expect(migrarPastaDeModelos(antiga, nova)).toEqual({ dir: nova, resultado: 'ja-migrada' })
    // Nunca apaga modelo: se as duas tem conteudo, a antiga fica onde esta.
    expect(existsSync(join(antiga, 'velho.pth'))).toBe(true)
  })

  it('segunda abertura depois da migracao nao faz nada', () => {
    const antiga = join(raiz, 'antiga')
    const nova = join(raiz, 'nova')
    modelo(antiga)
    migrarPastaDeModelos(antiga, nova)
    expect(migrarPastaDeModelos(antiga, nova).resultado).toBe('ja-migrada')
  })

  it('se nao consegue mover, usa a antiga nesta sessao em vez de perder os modelos', () => {
    // O destino nao pode ser criado: o "pai" dele e' um arquivo. Simula o
    // rename recusado sem depender de permissao do sistema.
    const antiga = join(raiz, 'antiga')
    modelo(antiga)
    writeFileSync(join(raiz, 'bloqueio'), 'x')
    const nova = join(raiz, 'bloqueio', 'models')

    const m = migrarPastaDeModelos(antiga, nova)

    expect(m.resultado).toBe('mantida-antiga')
    expect(m.dir).toBe(antiga)
    expect(existsSync(join(antiga, 'realesrgan.pth'))).toBe(true)
  })
})

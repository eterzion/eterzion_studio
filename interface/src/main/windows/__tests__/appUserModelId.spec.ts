// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import {
  APP_USER_MODEL_ID,
  reconcileShortcuts,
  shortcutDirs,
  type ShortcutDeps,
  type ShortcutInfo
} from '../appUserModelId'

// O id da janela e o id que o instalador grava nos atalhos precisam ser o
// mesmo. Quando divergem nada quebra de forma visivel: o app abre, so' que a
// janela ganha um icone proprio na barra de tarefas, separado do atalho fixado,
// e a notificacao de "job concluido" pode nao aparecer. Por isso o teste, e nao
// a leitura do codigo, e' quem garante.

const EXE = 'C:\\Users\\u\\AppData\\Local\\Programs\\eterzion-studio\\eterzion-studio.exe'

/** Sistema de arquivos falso: pasta -> { nome do arquivo -> atalho }. */
function sistema(pastas: Record<string, Record<string, ShortcutInfo | 'erro'>>): {
  deps: ShortcutDeps
  escritos: Map<string, string>
} {
  const escritos = new Map<string, string>()
  const deps: ShortcutDeps = {
    listDir(dir) {
      const p = pastas[dir]
      if (!p) throw new Error(`ENOENT: ${dir}`)
      return Object.keys(p)
    },
    readShortcutLink(path) {
      for (const [dir, arquivos] of Object.entries(pastas)) {
        for (const [nome, info] of Object.entries(arquivos)) {
          if (join(dir, nome) === path) {
            if (info === 'erro') throw new Error('atalho corrompido')
            return info
          }
        }
      }
      throw new Error(`nao e' atalho: ${path}`)
    },
    writeShortcutLink(path, _target, id) {
      escritos.set(path, id)
    }
  }
  return { deps, escritos }
}

describe('APP_USER_MODEL_ID', () => {
  it(`e' igual ao appId do electron-builder.yml, que o instalador grava nos atalhos`, () => {
    const yml = readFileSync(resolve(process.cwd(), 'electron-builder.yml'), 'utf8')
    const appId = /^appId:\s*(\S+)\s*$/m.exec(yml)?.[1]
    expect(appId, 'appId ausente no electron-builder.yml').toBeTruthy()
    expect(APP_USER_MODEL_ID).toBe(appId)
  })

  it('o id antigo nao sobrou em nenhum arquivo do processo principal', () => {
    // Foi uma string solta em index.ts que divergiu. Se ela voltar, por copia
    // de um exemplo antigo, este teste aponta o arquivo. Procura o id como
    // literal de codigo (entre aspas), e nao citado em comentario -- o
    // appUserModelId.ts cita o id antigo entre crases para contar a historia.
    const literal = /['"]com\.astrosupscale\.app['"]/
    const raiz = resolve(process.cwd(), 'src/main')
    const achados: string[] = []
    const varrer = (dir: string): void => {
      for (const nome of readdirSync(dir)) {
        const p = join(dir, nome)
        if (statSync(p).isDirectory()) {
          if (nome !== '__tests__') varrer(p)
        } else if (/\.(ts|js)$/.test(nome) && literal.test(readFileSync(p, 'utf8'))) {
          achados.push(p)
        }
      }
    }
    varrer(raiz)
    expect(achados).toEqual([])
  })
})

describe('reconcileShortcuts', () => {
  const MENU = 'C:\\menu'

  it('regrava o atalho do app que ainda carrega o id antigo', () => {
    const { deps, escritos } = sistema({
      [MENU]: { 'Eterzion Studio.lnk': { target: EXE, appUserModelId: 'com.astrosupscale.app' } }
    })
    const r = reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(r.atualizados).toEqual([join(MENU, 'Eterzion Studio.lnk')])
    expect(escritos.get(join(MENU, 'Eterzion Studio.lnk'))).toBe(APP_USER_MODEL_ID)
  })

  it('reconhece o executavel mesmo com outra caixa de letra no caminho', () => {
    // O Windows nao diferencia maiusculas no caminho; o atalho pode ter sido
    // gravado com uma caixa e o process.execPath vir com outra.
    const { deps, escritos } = sistema({
      [MENU]: { 'a.lnk': { target: EXE.toUpperCase(), appUserModelId: 'velho' } }
    })
    reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(escritos.size).toBe(1)
  })

  it('nao reescreve atalho que ja esta certo', () => {
    // Roda a cada abertura do app; sem isto, reescreveria o arquivo toda vez.
    const { deps, escritos } = sistema({
      [MENU]: { 'a.lnk': { target: EXE, appUserModelId: APP_USER_MODEL_ID } }
    })
    const r = reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(escritos.size).toBe(0)
    expect(r.atualizados).toEqual([])
  })

  it('nunca toca atalho que aponta para outro programa', () => {
    const { deps, escritos } = sistema({
      [MENU]: {
        'Outro.lnk': { target: 'C:\\Program Files\\Outro\\outro.exe', appUserModelId: 'x' }
      }
    })
    reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(escritos.size).toBe(0)
  })

  it(`ignora o que nao e' atalho`, () => {
    const { deps, escritos } = sistema({ [MENU]: { 'desktop.ini': { target: EXE } } })
    reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(escritos.size).toBe(0)
  })

  it(`pasta ausente nao e' falha`, () => {
    // Quem nunca fixou o app na barra de tarefas nao tem a pasta de fixados.
    const { deps } = sistema({})
    const r = reconcileShortcuts(['C:\\nao-existe'], EXE, APP_USER_MODEL_ID, deps)
    expect(r).toEqual({ atualizados: [], falhas: [] })
  })

  it('um atalho ilegivel vira falha registrada e nao interrompe os outros', () => {
    const { deps, escritos } = sistema({
      [MENU]: {
        'quebrado.lnk': 'erro',
        'Eterzion Studio.lnk': { target: EXE, appUserModelId: 'velho' }
      }
    })
    const r = reconcileShortcuts([MENU], EXE, APP_USER_MODEL_ID, deps)
    expect(r.falhas.map((f) => f.path)).toEqual([join(MENU, 'quebrado.lnk')])
    expect(escritos.has(join(MENU, 'Eterzion Studio.lnk'))).toBe(true)
  })
})

describe('shortcutDirs', () => {
  it('cobre Menu Iniciar, area de trabalho e barra de tarefas', () => {
    const dirs = shortcutDirs('C:\\Users\\u\\AppData\\Roaming', 'D:\\OneDrive\\Desktop')
    expect(dirs).toContain(
      join('C:\\Users\\u\\AppData\\Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    )
    // A area de trabalho vem de app.getPath('desktop'), e nao de %USERPROFILE%,
    // porque ela pode estar redirecionada para o OneDrive.
    expect(dirs).toContain('D:\\OneDrive\\Desktop')
    expect(dirs.some((d) => d.endsWith(join('User Pinned', 'TaskBar')))).toBe(true)
  })
})

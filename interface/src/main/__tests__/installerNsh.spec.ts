// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { instaladorPediuModelos } from '../installerOptions'

// O instalador assistido (build/installer.nsh) so' e' compilado no build do
// Windows, que leva minutos -- e com `warningsAsErrors` ligado, uma LangString
// faltando em um idioma derruba o build inteiro. Estes testes pegam o mesmo
// erro em segundos, e fixam a regra que um descuido tornaria cara: a
// desinstalacao nunca apaga a identidade da licenca.

const raiz = process.cwd()
const nsh = readFileSync(resolve(raiz, 'build/installer.nsh'), 'utf8')
const yml = readFileSync(resolve(raiz, 'electron-builder.yml'), 'utf8')

// Idioma do app (src/renderer/src/i18n/locales) -> codigo do electron-builder
// -> constante do NSIS. `zh-Hans` vira `zh_CN` porque o electron-builder nao
// reconhece `zh_Hans`; o espanhol vira SpanishInternational no template.
const IDIOMAS: Record<string, [string, string]> = {
  en: ['en_US', 'LANG_ENGLISH'],
  'pt-BR': ['pt_BR', 'LANG_PORTUGUESEBR'],
  'pt-PT': ['pt_PT', 'LANG_PORTUGUESE'],
  es: ['es_ES', 'LANG_SPANISHINTERNATIONAL'],
  fr: ['fr_FR', 'LANG_FRENCH'],
  de: ['de_DE', 'LANG_GERMAN'],
  it: ['it_IT', 'LANG_ITALIAN'],
  ja: ['ja_JP', 'LANG_JAPANESE'],
  ko: ['ko_KR', 'LANG_KOREAN'],
  ru: ['ru_RU', 'LANG_RUSSIAN'],
  'zh-Hans': ['zh_CN', 'LANG_SIMPCHINESE']
}

function installerLanguages(): string[] {
  const bloco = /^ {2}installerLanguages:\n((?: {4}- .+\n)+)/m.exec(yml)?.[1] ?? ''
  return [...bloco.matchAll(/- (\S+)/g)].map((m) => m[1])
}

describe('idiomas do instalador', () => {
  it('sao exatamente os do app', () => {
    const locales = readdirSync(resolve(raiz, 'src/renderer/src/i18n/locales'))
      .filter((f) => f.endsWith('.json'))
      .map((f) => f.replace(/\.json$/, ''))
      .sort()
    // Um idioma novo no app sem par aqui cai no ingles do instalador.
    expect(Object.keys(IDIOMAS).sort()).toEqual(locales)
    expect(installerLanguages().sort()).toEqual(
      Object.values(IDIOMAS)
        .map(([c]) => c)
        .sort()
    )
  })

  it('o ingles vem primeiro, porque e o que o NSIS usa quando o idioma do Windows nao esta na lista', () => {
    expect(installerLanguages()[0]).toBe('en_US')
  })

  it('toda LangString existe em todos os idiomas, uma vez so', () => {
    const porId = new Map<string, string[]>()
    for (const m of nsh.matchAll(/^\s*LangString (\w+) \$\{(\w+)\} "/gm)) {
      porId.set(m[1], [...(porId.get(m[1]) ?? []), m[2]])
    }
    expect(porId.size).toBeGreaterThan(0)
    const esperado = Object.values(IDIOMAS)
      .map(([, c]) => c)
      .sort()
    for (const [id, langs] of porId) {
      expect(langs.sort(), `LangString ${id}`).toEqual(esperado)
    }
  })

  it('todo texto usado com $(...) tem LangString', () => {
    const definidas = new Set([...nsh.matchAll(/LangString (\w+) /g)].map((m) => m[1]))
    const usadas = [...nsh.matchAll(/\$\((ez\w+)\)/g)].map((m) => m[1])
    expect(usadas.length).toBeGreaterThan(0)
    for (const id of usadas) expect(definidas, id).toContain(id)
  })
})

describe('desinstalacao', () => {
  const limpeza = /!macro customUnInstall([\s\S]*?)!macroend/.exec(nsh)?.[1] ?? ''

  it('nunca apaga a identidade da licenca', () => {
    // %LOCALAPPDATA%\AstrosUpscale guarda a ativacao. Apaga-la faria uma
    // reinstalacao gastar outra vaga da licenca.
    expect(limpeza).not.toBe('')
    const apagados = [...limpeza.matchAll(/^\s*RMDir \/r "([^"]+)"/gm)].map((m) => m[1])
    expect(apagados.length).toBeGreaterThan(0)
    for (const p of apagados) expect(p.toLowerCase()).not.toContain('astrosupscale')
  })

  it('so apaga caminhos literais, com o nome da pasta escrito', () => {
    // Um RMDir /r montado de variavel vazia viraria "$LOCALAPPDATA\" -- o
    // AppData inteiro.
    for (const m of limpeza.matchAll(/^\s*RMDir \/r "([^"]+)"/gm)) {
      expect(m[1]).toMatch(/^\$(APPDATA|LOCALAPPDATA)\\eterzion-studio(-worker|-updater)?$/)
    }
  })

  it('nao apaga nada numa atualizacao', () => {
    expect(limpeza).toMatch(/\$\{ifNot\} \$\{isUpdated\}/)
  })
})

describe('pedido de baixar os modelos', () => {
  it('o que o instalador grava e exatamente o que o app le', () => {
    // Os dois lados se falam por um arquivo. Renomear a chave de um lado so'
    // deixaria a caixa do instalador sem efeito, sem erro em lugar nenhum.
    const conteudo = /FileWrite \$0 '([^']+)'/.exec(nsh)?.[1]
    expect(conteudo, 'FileWrite do installer-options.json nao encontrado').toBeTruthy()
    expect(nsh).toContain('$INSTDIR\\installer-options.json')

    const pasta = mkdtempSync(join(tmpdir(), 'eterzion-contrato-'))
    try {
      writeFileSync(join(pasta, 'installer-options.json'), conteudo!)
      expect(instaladorPediuModelos(pasta)).toBe(true)
    } finally {
      rmSync(pasta, { recursive: true, force: true })
    }
  })
})

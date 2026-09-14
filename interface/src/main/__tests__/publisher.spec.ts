// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Quem publica o app, como cada sistema o mostra.
//
// No Windows o nome vem do `author` do package.json: o electron-builder o
// grava como "Publisher" em Aplicativos instalados, como CompanyName do
// executavel e no copyright. No Linux vem de `vendor` e `maintainer` do
// electron-builder.yml. Sao dois lugares para a mesma informacao, e eles ja
// divergiram: o .deb saia como "Eterzion" enquanto o Windows mostrava o nome
// de uma pessoa. Nada acusa, porque os dois instalam normalmente.

const raiz = process.cwd()
const pkg = JSON.parse(readFileSync(resolve(raiz, 'package.json'), 'utf8')) as { author: unknown }
const yml = readFileSync(resolve(raiz, 'electron-builder.yml'), 'utf8')

function campoLinux(nome: string): string | undefined {
  // Campo de primeiro nivel dentro do bloco `linux:` (dois espacos de recuo).
  const bloco = /^linux:\n((?: {2}.*\n|\s*\n)+)/m.exec(yml)?.[1] ?? ''
  return new RegExp(`^ {2}${nome}:\\s*(.+?)\\s*$`, 'm').exec(bloco)?.[1]
}

describe('publisher', () => {
  it('o Windows publica como Eterzion', () => {
    expect(pkg.author).toBe('Eterzion')
  })

  it('Windows e Linux mostram o mesmo publisher', () => {
    expect(campoLinux('vendor')).toBe(pkg.author)
    // O .deb exige mantenedor com e-mail; o nome dele e' o mesmo publisher.
    expect(campoLinux('maintainer')).toMatch(new RegExp(`^${String(pkg.author)} <[^>]+@[^>]+>$`))
  })

  it('o copyright nao esta fixado com outro nome', () => {
    // Sem `copyright` no electron-builder.yml, o padrao e' "Copyright © <ano>
    // <author>" -- acompanha o author. Um valor fixo aqui voltaria a divergir
    // na proxima troca.
    const fixo = /^copyright:\s*(.+)$/m.exec(yml)?.[1]
    if (fixo) expect(fixo).toContain(String(pkg.author))
  })
})

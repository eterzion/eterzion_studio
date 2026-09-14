import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// O CSP do renderer viaja dentro do pacote: o que for liberado aqui vale para
// toda copia instalada ate a proxima versao, e o que for esquecido aqui fica
// liberado sem ninguem notar -- uma origem a mais nao quebra nada, entao nada
// denuncia.
//
// Foi o que aconteceu com `http://127.0.0.1:8766`. Ficou em connect-src como
// "o servico de licencas", mas o renderer nunca falou com ele: a licenca
// passa pelo backend, do lado do servidor. E `assets.ericinacio.com` ficou em
// img-src meses depois de o dominio deixar de existir.
//
// Por isso o teste fixa a lista inteira, e nao so a presenca do que se usa.
// Acrescentar uma origem passa a exigir mudar este arquivo -- e explicar por que.

function csp(): string {
  // A partir da raiz do projeto, como no teste do logo: sob o Vitest,
  // `import.meta.url` nao tem esquema `file:`.
  const html = readFileSync(resolve(process.cwd(), 'src/renderer/index.html'), 'utf8')
  const valor = /content="([^"]*default-src[^"]*)"/.exec(html)?.[1]
  expect(valor, 'CSP nao encontrado em index.html').toBeTruthy()
  return valor!
}

function diretiva(nome: string): string[] {
  const corpo = new RegExp(`(?:^|;)\\s*${nome} ([^;]*)`).exec(csp())?.[1]
  expect(corpo, `${nome} ausente no CSP`).toBeTruthy()
  return corpo!.trim().split(/\s+/)
}

describe('CSP do renderer', () => {
  it('connect-src libera so a propria origem e a API local', () => {
    // Os dois marcadores sao trocados no build pelas portas de desenvolvimento
    // e do pacote (electron.vite.config.ts). Nada alem deles.
    expect(diretiva('connect-src')).toEqual([
      "'self'",
      '%ASTROS_API_ORIGIN%',
      '%ASTROS_API_WS_ORIGIN%'
    ])
  })

  it('img-src libera so o CDN atual, alem das fontes locais', () => {
    expect(diretiva('img-src')).toEqual([
      "'self'",
      'data:',
      'eterzion-media:',
      'https://cdn.eterzion.com'
    ])
  })

  it('nenhuma diretiva aponta para a porta 8766', () => {
    expect(csp()).not.toContain('8766')
  })
})

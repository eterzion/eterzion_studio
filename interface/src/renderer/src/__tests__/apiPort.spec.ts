import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * A porta que o renderer chama é inlinada em tempo de build
 * (`electron.vite.config.ts`), e a que o backend usa vive no processo
 * principal. Elas divergiram: o app empacotado chamava 8050 enquanto a API
 * subia em 8051, e TODA requisição falhava — com a tela de licença dizendo
 * "verifique sua conexão de internet", o backend rodando ao lado respondendo
 * 200, e "Try again" nunca resolvendo, porque a porta chamada estava vazia.
 *
 * O cabeçalho do `electron.vite.config.ts` diz que quatro coisas precisam
 * concordar. Este teste verifica duas delas, em vez de confiar que quem editar
 * repare no comentário.
 */
describe('porta da API', () => {
  const raiz = resolve(__dirname, '../../../..')
  const ler = (caminho: string): string => readFileSync(resolve(raiz, caminho), 'utf8')

  it('o config inlina a porta EMPACOTADA no build, não a de desenvolvimento', () => {
    const config = ler('electron.vite.config.ts')
    const define = /__ASTROS_API_PORT__:\s*JSON\.stringify\(([\s\S]*?)\)/.exec(config)?.[1]

    expect(define, 'define de __ASTROS_API_PORT__ não encontrado').toBeTruthy()
    expect(define).toContain('PACKAGED_API_PORT')
    expect(define).toContain("command === 'build'")
  })

  it('a porta empacotada do config é a mesma que o processo principal usa', () => {
    const doConfig = /const PACKAGED_API_PORT = '(\d+)'/.exec(ler('electron.vite.config.ts'))?.[1]
    const doMain = /API_PORT = process\.env\.ASTROS_API_PORT \|\| '(\d+)'/.exec(
      ler('src/main/apiProcess.ts')
    )?.[1]

    expect(doConfig, 'PACKAGED_API_PORT não encontrado no config').toBeTruthy()
    expect(doMain, 'API_PORT não encontrado em apiProcess.ts').toBeTruthy()
    expect(doConfig).toBe(doMain)
  })
})

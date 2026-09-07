import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Cada módulo tem de resolver para o SEU acento.
 *
 * `image`, `video` e `audio` eram colapsados em `var(--primary)`, e só
 * `compression` mantinha cor própria — por isso apenas a tela de Compressão
 * combinava com o cartão e o item de menu que a abriam. O `HomeView.vue` já
 * afirmava o contrário no comentário dele, e a afirmação era verdadeira para
 * um dos quatro.
 *
 * O tema claro nunca teve o problema: as regras `[data-theme='light']` têm
 * especificidade maior e já davam a cor certa. Era defeito do tema escuro, que
 * é o padrão — e por isso invisível para quem lesse só o fim do arquivo.
 */
describe('acentos por módulo', () => {
  const raiz = resolve(__dirname, '../../../..')
  const css = readFileSync(resolve(raiz, 'src/renderer/src/assets/theme.css'), 'utf8')

  /** Corpo da PRIMEIRA regra do módulo — a base. As de `[data-theme='light']`
   *  vêm depois no arquivo e são correções de contraste, não a definição. */
  const bloco = (modulo: string): string => {
    const seletor = `[data-module='${modulo}'] {`
    const inicio = css.indexOf(seletor)
    expect(inicio, `regra de ${seletor} não encontrada`).toBeGreaterThan(-1)
    return css.slice(inicio + seletor.length, css.indexOf('}', inicio))
  }

  it.each([
    ['image', '--accent-image'],
    ['video', '--accent-video'],
    ['audio', '--accent-audio'],
    ['compression', '--accent-compression']
  ])('%s usa %s', (modulo, token) => {
    expect(bloco(modulo)).toContain(`--color-primary: var(${token})`)
  })

  it('nenhum módulo cai na cor da marca', () => {
    // `var(--primary)` aqui significaria o módulo perdendo a identidade dele —
    // exatamente o estado que este teste existe para impedir.
    for (const modulo of ['image', 'video', 'audio', 'compression']) {
      expect(bloco(modulo)).not.toContain('var(--primary)')
    }
  })
})

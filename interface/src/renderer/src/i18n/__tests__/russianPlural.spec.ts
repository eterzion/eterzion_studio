import { describe, expect, it } from 'vitest'
import { i18n, russianPlural } from '../index'

describe('russianPlural', () => {
  it.each([
    [1, 0],
    [21, 0],
    [101, 0],
    [2, 1],
    [4, 1],
    [23, 1],
    [0, 2],
    [5, 2],
    [11, 2],
    [12, 2],
    [14, 2],
    [111, 2],
    [25, 2]
  ])('%i -> forma %i', (n, forma) => {
    expect(russianPlural(n, 3)).toBe(forma)
  })

  it('com duas formas na mensagem, segue a regra padrao', () => {
    expect(russianPlural(1, 2)).toBe(0)
    expect(russianPlural(3, 2)).toBe(1)
  })

  it('e esta registrado para o russo', () => {
    const { t, locale } = i18n.global
    const antes = locale.value
    locale.value = 'ru'
    try {
      expect(t('license.offlineDays', 1)).toContain('1 день')
      expect(t('license.offlineDays', 3)).toContain('3 дня')
      expect(t('license.offlineDays', 5)).toContain('5 дней')
    } finally {
      locale.value = antes
    }
  })
})

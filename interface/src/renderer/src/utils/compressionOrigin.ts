import type { MediaKind } from '../constants/compression'

// De onde a configuracao da Central veio: um preset, um registro do historico
// ("Repetir"), ou nenhum dos dois. O backend resolve os dois no modo Basico, e
// recusa um que seja de outra midia -- entao a tela nao pode continuar mandando
// o preset de video depois que a pessoa abriu uma imagem. Antes o id so' era
// guardado e ignorado, e o descuido nao aparecia; com o backend resolvendo, ele
// viraria recusa.

export interface OrigemDaConfiguracao {
  presetId: string | null
  /** Tipo de midia do preset selecionado, ou null se nao ha' preset. */
  presetKind: MediaKind | null
  historyId: string | null
  historyKind: MediaKind | null
}

/** O que sobra da origem quando o tipo de midia passa a ser `kind`. */
export function origemParaMidia(
  origem: OrigemDaConfiguracao,
  kind: MediaKind
): Pick<OrigemDaConfiguracao, 'presetId' | 'historyId'> {
  return {
    presetId: origem.presetId && origem.presetKind === kind ? origem.presetId : null,
    historyId: origem.historyId && origem.historyKind === kind ? origem.historyId : null
  }
}

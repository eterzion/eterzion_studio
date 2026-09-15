import type { EnhanceSettings } from '../components/video/VideoEnhancePanel.vue'
import type { VideoEditSet } from '../composables/useVideoEdits'

// "Aplicar esta configuracao a todos" no Video, como na Imagem.
//
// Vai o que vale para qualquer video: a melhoria (tipo de conteudo, escala,
// perfil, dispositivo), os ajustes de cor, os efeitos, o audio, a rotacao e o
// espelhamento. Fica o que e' de cada arquivo: o recorte (pixels daquele
// quadro), o trecho (segundos daquele video) e o tamanho de saida derivado do
// recorte. Copiar esses levaria o corte de 00:10 a 00:20 de um clipe de 15
// segundos para um de 5, ou um recorte para fora do quadro de outro video.
//
// O tamanho personalizado da escala e' em pixels da origem; vai como fator,
// recalculado para as dimensoes de cada video -- a mesma regra da Imagem.

export interface VideoConfig {
  edits: VideoEditSet
  enhance: EnhanceSettings
  width: number | null
  height: number | null
}

/** Copia profunda. Nao `structuredClone`: os objetos chegam como proxies
 *  reativos do Vue, que ele recusa (DataCloneError) -- e dentro de um clique a
 *  falha era silenciosa. Os campos sao todos simples, JSON basta. */
function copia<T>(valor: T): T {
  return JSON.parse(JSON.stringify(valor)) as T
}

/** Arredonda para par: os encoders recusam dimensao impar em yuv420p. */
function par(n: number): number {
  return Math.max(2, Math.round(n / 2) * 2)
}

export function copiarConfiguracao(origem: VideoConfig, destino: VideoConfig): void {
  const { customWidth, customHeight, ...melhoria } = origem.enhance
  Object.assign(destino.enhance, copia(melhoria))
  if (
    origem.enhance.scale === 'custom' &&
    customWidth &&
    customHeight &&
    origem.width &&
    origem.height &&
    destino.width &&
    destino.height
  ) {
    destino.enhance.customWidth = par(destino.width * (customWidth / origem.width))
    destino.enhance.customHeight = par(destino.height * (customHeight / origem.height))
  } else {
    destino.enhance.customWidth = null
    destino.enhance.customHeight = null
  }

  copiarEdicoes(origem.edits, destino.edits)
}

/** So' as edicoes: ajustes, efeitos, audio, rotacao e espelhamento. Recorte e
 *  trecho ficam os do destino. A Imagem usa esta parte no "Aplicar a todos". */
export function copiarEdicoes(origem: VideoEditSet, destino: VideoEditSet): void {
  Object.assign(destino.adjustments, copia(origem.adjustments))
  Object.assign(destino.effects, copia(origem.effects))
  Object.assign(destino.audio, copia(origem.audio))
  destino.transform.rotation_degrees = origem.transform.rotation_degrees
  destino.transform.flip_horizontal = origem.transform.flip_horizontal
  destino.transform.flip_vertical = origem.transform.flip_vertical
}

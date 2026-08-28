// specs/008-compression-centre — os tipos de mídia da Central e os dois modos.
//
// Registro, não condicional. FR-004 exige que acrescentar um tipo de mídia no
// futuro não obrigue a mexer nos existentes: quem itera esta lista ganha o novo
// tipo sem alteração, e quem ramifica por `if (kind === 'image')` espalhado pela
// tela teria que ser caçado um a um.
//
// Os rótulos são chaves de i18n resolvidas no ponto de uso (Princípio XIV) — o
// valor é o que viaja para a API, e é a única coisa aqui que o backend conhece.

export type MediaKind = 'image' | 'video' | 'audio' | 'animation'

/** Básico é o padrão, e isso é constitucional, não estético: a condição 2 da
 *  exceção do Princípio V (constituição v4.0.0) exige que quem nunca abrir o
 *  modo Avançado jamais encontre um nome de codec. */
export type CompressionMode = 'basic' | 'advanced'

export const DEFAULT_COMPRESSION_MODE: CompressionMode = 'basic'

export interface MediaKindEntry {
  value: MediaKind
  /** Chave de i18n, resolvida onde é exibida. */
  labelKey: string
}

export const COMPRESSION_MEDIA_KINDS: MediaKindEntry[] = [
  { value: 'image', labelKey: 'compression.media.image' },
  { value: 'video', labelKey: 'compression.media.video' },
  { value: 'audio', labelKey: 'compression.media.audio' },
  { value: 'animation', labelKey: 'compression.media.animation' }
]

export const DEFAULT_MEDIA_KIND: MediaKind = 'image'

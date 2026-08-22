// specs/008-compression-centre — T029: o estado das configurações, por tipo de mídia.
//
// Duas decisões carregam o resto do arquivo:
//
// **Um estado por tipo de mídia, não um compartilhado.** Trocar de Imagem para
// Vídeo e voltar tem que devolver o que a pessoa tinha ajustado; um estado único
// com campos que só valem para um tipo produziria `quality: 70` viajando para um
// pedido de áudio, onde o backend o recusaria com razão.
//
// **`auto`/`original` como padrão de todo campo técnico** (FR-039). O padrão não
// é um valor bonito escolhido por nós — é a ausência de escolha, que deixa o
// backend resolver a partir do que a máquina tem. Um padrão concreto (`h264`,
// `48000`) seria uma decisão nossa disfarçada de default, e quebraria em toda
// máquina onde aquilo não existe.
import { computed, reactive, ref } from 'vue'
import {
  DEFAULT_COMPRESSION_MODE,
  DEFAULT_MEDIA_KIND,
  type CompressionMode,
  type MediaKind
} from '../constants/compression'
import type { CompressionSettings, SizeTarget } from '../services/compression'

/** O valor que significa "decida você". Uma string e não `null` porque ela
 *  aparece no `<select>` como opção legítima — "Automático" é uma escolha que a
 *  pessoa faz, e o `null` some do controle. */
export const AUTO = 'auto'
export const ORIGINAL = 'original'

/** Campos com `auto`/`original` são omitidos do pedido: mandar `'auto'` obrigaria
 *  o backend a conhecer a convenção da interface, e ausente já quer dizer
 *  exatamente isso no schema. */
const SENTINELS = new Set<unknown>([AUTO, ORIGINAL, '', null, undefined])

function defaultsFor(kind: MediaKind): CompressionSettings {
  switch (kind) {
    case 'image':
      return { output_format: 'keep', quality: 80, metadata_policy: 'essential_only' }
    case 'video':
      return {
        container: AUTO,
        video_codec: AUTO,
        audio_codec: AUTO,
        quality: 70,
        rate_mode: AUTO,
        fps: ORIGINAL,
        resolution: ORIGINAL
      }
    case 'audio':
      return { output_format: AUTO, quality: 70, sample_rate: ORIGINAL, channels: ORIGINAL }
    case 'animation':
      return { output_format: AUTO, quality: 70, max_colors: AUTO, fps: ORIGINAL }
  }
}

export function useCompressionSettings() {
  const mediaKind = ref<MediaKind>(DEFAULT_MEDIA_KIND)
  const mode = ref<CompressionMode>(DEFAULT_COMPRESSION_MODE)

  // Um objeto por tipo, criado uma vez. `reactive` e não `ref` porque o que muda
  // são campos de dentro, e um `ref` obrigaria a substituir o objeto inteiro a
  // cada tecla digitada.
  const byKind = reactive<Record<MediaKind, CompressionSettings>>({
    image: defaultsFor('image'),
    video: defaultsFor('video'),
    audio: defaultsFor('audio'),
    animation: defaultsFor('animation')
  })

  const targetByKind = reactive<Record<MediaKind, SizeTarget | null>>({
    image: null,
    video: null,
    audio: null,
    animation: null
  })

  const settings = computed<CompressionSettings>(() => byKind[mediaKind.value])
  const target = computed<SizeTarget | null>(() => targetByKind[mediaKind.value])

  function set(field: string, value: unknown): void {
    byKind[mediaKind.value][field] = value
  }

  function setTarget(value: SizeTarget | null): void {
    targetByKind[mediaKind.value] = value
  }

  function reset(kind: MediaKind = mediaKind.value): void {
    byKind[kind] = defaultsFor(kind)
    targetByKind[kind] = null
  }

  /** Aplica um preset **por cima** dos padrões, não por cima do que estava.
   *
   *  Mesclar com o estado atual deixaria resíduo do preset anterior: escolher
   *  "Discord 8 MB" e depois "Máxima qualidade" manteria campos do primeiro que
   *  o segundo não menciona, e o resultado não seria nenhum dos dois. */
  function applyPreset(kind: MediaKind, presetSettings: CompressionSettings): void {
    byKind[kind] = { ...defaultsFor(kind), ...presetSettings }
  }

  /** O que de fato viaja: sem sentinelas, e sem campo técnico quando o modo é
   *  Básico.
   *
   *  A segunda parte é constitucional (condição 2 da exceção do Princípio V) e o
   *  backend recusa de qualquer forma — mas filtrar aqui evita que um campo
   *  deixado para trás por uma troca de modo transforme um pedido válido em 422
   *  que a pessoa não causou. */
  const payload = computed<CompressionSettings>(() => {
    const origem = settings.value
    const saida: CompressionSettings = {}
    for (const [chave, valor] of Object.entries(origem)) {
      if (SENTINELS.has(valor)) continue
      if (mode.value === 'basic' && ADVANCED_ONLY.has(chave)) continue
      saida[chave] = valor
    }
    return saida
  })

  return {
    mediaKind,
    mode,
    settings,
    target,
    payload,
    set,
    setTarget,
    reset,
    applyPreset
  }
}

/** Espelha `_ADVANCED_ONLY_FIELDS` de `app/compression/runner.py`. As duas
 *  listas são verificadas uma contra a outra em `compressionSettings.spec.ts`. */
export const ADVANCED_ONLY = new Set<string>([
  'video_codec',
  'audio_codec',
  'container',
  'crf',
  'rate_mode',
  'video_bitrate_bps',
  'max_bitrate_bps',
  'cbr',
  'encoding_preset',
  'encoder_preference',
  'codec',
  'bitrate_mode',
  'sample_rate',
  'channels',
  'png_compress_level',
  'chroma_subsampling',
  'progressive',
  'effort',
  'speed',
  'dither',
  'max_colors'
])

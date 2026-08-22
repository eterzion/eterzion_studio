<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CompressionMedia } from '../../services/compression'

// specs/008-compression-centre — T025f: o que se sabe do arquivo, antes de processar.
//
// **Uma linha só existe quando o campo foi sondado** (FR-008, FR-010). Um traço
// no lugar de um bitrate parece um valor medido que por acaso é vazio; a linha
// ausente diz a verdade, que é "ninguém mediu isto". A diferença importa porque
// a pessoa decide a configuração a partir daqui.
//
// Nenhum nome de encoder aparece. O que se mostra é o codec do contêiner
// (`h264`, `opus`) — o que o arquivo **é**, não com o que poderia ter sido
// feito (Princípio V).

const props = defineProps<{ media: CompressionMedia }>()

const { t, n } = useI18n()

interface Row {
  key: string
  value: string
}

const rows = computed<Row[]>(() => {
  const m = props.media
  const linhas: Row[] = [{ key: 'size', value: bytes(m.size_bytes) }]

  push(linhas, 'resolution', m.width && m.height ? `${m.width} × ${m.height}` : null)
  push(linhas, 'duration', m.duration_seconds != null ? duration(m.duration_seconds) : null)
  push(
    linhas,
    'frameRate',
    m.frame_rate != null
      ? m.frame_rate_is_variable
        // Um número exato para uma taxa variável seria uma afirmação falsa: o
        // arquivo não tem "uma" taxa, e apresentá-la limpa esconde justamente o
        // que a pessoa precisaria saber.
        ? t('compression.info.frameRateVariable', { value: n(round(m.frame_rate, 2)) })
        : `${n(round(m.frame_rate, 2))} fps`
      : null
  )
  push(linhas, 'videoCodec', m.video_codec ? m.video_codec.toUpperCase() : null)
  push(linhas, 'videoBitrate', m.video_bitrate_bps != null ? bitrate(m.video_bitrate_bps) : null)
  push(linhas, 'audioCodec', m.audio_codec ? m.audio_codec.toUpperCase() : null)
  push(linhas, 'audioBitrate', m.audio_bitrate_bps != null ? bitrate(m.audio_bitrate_bps) : null)
  push(linhas, 'sampleRate', m.sample_rate != null ? `${n(m.sample_rate)} Hz` : null)
  push(linhas, 'channels', m.channels != null ? channels(m.channels) : null)
  push(linhas, 'alpha', m.has_alpha ? t('compression.info.alphaYes') : null)

  return linhas
})

/** Mono e estéreo têm nome; o resto é contagem. Uma pluralização não daria
 *  conta disto — "1 canal / 2 canais" seria correto e diria menos do que a
 *  pessoa reconhece. */
function channels(quantidade: number): string {
  if (quantidade === 1) return t('compression.info.channelsMono')
  if (quantidade === 2) return t('compression.info.channelsStereo')
  return t('compression.info.channelsCount', { count: quantidade })
}

function push(linhas: Row[], key: string, value: string | null): void {
  if (value !== null) linhas.push({ key, value })
}

function round(value: number, casas: number): number {
  const fator = 10 ** casas
  return Math.round(value * fator) / fator
}

/** Decimal (1 kB = 1000 B), igual ao que o sistema de arquivos e o alvo de
 *  tamanho usam — misturar as duas convenções faria "8 MB" significar coisas
 *  diferentes em dois pontos da mesma tela. */
function bytes(valor: number): string {
  const unidades = ['B', 'kB', 'MB', 'GB']
  let n = valor
  let i = 0
  while (n >= 1000 && i < unidades.length - 1) {
    n /= 1000
    i++
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${unidades[i]}`
}

function bitrate(bps: number): string {
  return bps >= 1_000_000 ? `${(bps / 1_000_000).toFixed(1)} Mbps` : `${Math.round(bps / 1000)} kbps`
}

function duration(segundos: number): string {
  const total = Math.round(segundos)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const dois = (v: number): string => String(v).padStart(2, '0')
  return h > 0 ? `${h}:${dois(m)}:${dois(s)}` : `${m}:${dois(s)}`
}
</script>

<template>
  <dl class="file-info">
    <div v-for="row in rows" :key="row.key" class="info-row">
      <dt>{{ t(`compression.info.${row.key}`) }}</dt>
      <dd>{{ row.value }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.file-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--fs-label-sm);
}

.info-row dt {
  color: var(--text-tertiary);
}

.info-row dd {
  margin: 0;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
</style>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytesDecimal } from '../../utils/formatBytes'
import { api, hasNativeApi } from '../../services/native'
import type { CompressionMedia } from '../../services/compression'

// specs/008-compression-centre — T067: alternar original ⇄ resultado (FR-056).
//
// **Um player só, que troca de fonte.** Dois players lado a lado funcionam para
// imagem e vídeo, onde os olhos comparam em paralelo; ouvir duas trilhas ao mesmo
// tempo não compara nada. A comparação de áudio é sequencial por natureza, e o
// que ela precisa é que a troca **não perca a posição** — voltar ao começo a cada
// alternância obrigaria a pessoa a procurar de novo o trecho que estava julgando,
// e é sempre um trecho específico que revela a diferença.
//
// Os números aparecem juntos porque metade do julgamento é "vale a pena?": uma
// perda audível que cortou o arquivo em quatro é uma decisão diferente da mesma
// perda que cortou 5%.

const props = defineProps<{
  sourcePath: string
  outputPath: string | null
  media: CompressionMedia | null
  outputBytes: number | null
  /** O que a compressão de fato aplicou — codec e formato do resultado. */
  applied: Record<string, unknown> | null
}>()

const { t } = useI18n()

const lado = ref<'antes' | 'depois'>('antes')
const player = ref<HTMLAudioElement | null>(null)

const pronto = computed(() => Boolean(props.outputPath && hasNativeApi))

const src = computed(() => {
  if (!hasNativeApi) return ''
  const caminho = lado.value === 'depois' && props.outputPath ? props.outputPath : props.sourcePath
  return api.toFileUrl(caminho)
})

/** A posição sobrevive à troca.
 *
 *  Trocar o `src` de um `<audio>` zera `currentTime`, então a posição é
 *  guardada antes e restaurada quando os metadados do novo arquivo carregam —
 *  antes disso, atribuir `currentTime` não tem efeito. */
let posicaoGuardada = 0

function alternar(): void {
  const atual = player.value
  if (atual) posicaoGuardada = atual.currentTime
  lado.value = lado.value === 'antes' ? 'depois' : 'antes'
}

function aoCarregar(): void {
  const atual = player.value
  if (!atual || posicaoGuardada <= 0) return
  // Um resultado mais curto que a origem existe (trim não, mas arredondamento
  // de duração sim); passar do fim faria o player parar em vez de continuar.
  atual.currentTime = Math.min(posicaoGuardada, atual.duration || posicaoGuardada)
}

// Um resultado novo recomeça a comparação do original: manter "depois"
// selecionado apontaria para um arquivo que acabou de ser substituído.
watch(
  () => props.outputPath,
  () => {
    lado.value = 'antes'
    posicaoGuardada = 0
  }
)

interface Linha {
  chave: string
  antes: string
  depois: string
}

const linhas = computed<Linha[]>(() => {
  const m = props.media
  const aplicado = props.applied ?? {}
  const saida: Linha[] = [
    {
      chave: 'size',
      antes: formatBytesDecimal(m?.size_bytes ?? null),
      depois: formatBytesDecimal(props.outputBytes)
    }
  ]

  const codecDepois = typeof aplicado.codec === 'string' ? aplicado.codec.toUpperCase() : '—'
  saida.push({
    chave: 'codec',
    antes: m?.audio_codec ? m.audio_codec.toUpperCase() : '—',
    depois: codecDepois
  })

  // Duração e taxa de amostragem só aparecem quando foram sondadas: um traço no
  // lugar de um número parece medido e vazio (FR-010).
  if (m?.duration_seconds != null) {
    saida.push({
      chave: 'duration',
      antes: duracao(m.duration_seconds),
      depois: duracao(m.duration_seconds)
    })
  }
  if (m?.sample_rate != null) {
    const escolhida = aplicado.options as Record<string, unknown> | undefined
    const depoisHz = typeof escolhida?.ar === 'number' ? escolhida.ar : m.sample_rate
    saida.push({
      chave: 'sampleRate',
      antes: `${(m.sample_rate / 1000).toFixed(1)} kHz`,
      depois: `${(depoisHz / 1000).toFixed(1)} kHz`
    })
  }
  if (m?.audio_bitrate_bps != null) {
    saida.push({
      chave: 'bitrate',
      antes: bitrate(m.audio_bitrate_bps),
      depois: bitrateDepois(aplicado)
    })
  }
  return saida
})

function bitrateDepois(aplicado: Record<string, unknown>): string {
  if (aplicado.lossless === true) return t('compression.audio.losslessTag')
  const opcoes = aplicado.options as Record<string, unknown> | undefined
  const bits = opcoes?.['b:a']
  return typeof bits === 'number' ? bitrate(bits) : '—'
}

function bitrate(bps: number): string {
  return `${Math.round(bps / 1000)} kbps`
}

function duracao(segundos: number): string {
  const total = Math.round(segundos)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<template>
  <div class="audio-comparison">
    <div class="player-area">
      <div class="side-toggle" role="group" :aria-label="t('compression.compare.view')">
        <button
          type="button"
          :class="{ active: lado === 'antes' }"
          @click="lado !== 'antes' && alternar()"
        >
          {{ t('compression.compare.before') }}
        </button>
        <button
          type="button"
          :class="{ active: lado === 'depois' }"
          :disabled="!pronto"
          @click="lado !== 'depois' && alternar()"
        >
          {{ t('compression.compare.after') }}
        </button>
      </div>

      <audio ref="player" :src="src" controls @loadedmetadata="aoCarregar" />

      <p v-if="!pronto" class="pending">{{ t('compression.compare.pending') }}</p>
      <p v-else class="keeps-position">{{ t('compression.compare.keepsPosition') }}</p>
    </div>

    <table class="numbers">
      <thead>
        <tr>
          <th></th>
          <th>{{ t('compression.compare.before') }}</th>
          <th>{{ t('compression.compare.after') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="linha in linhas" :key="linha.chave">
          <th scope="row">{{ t(`compression.info.${linha.chave}`) }}</th>
          <td>{{ linha.antes }}</td>
          <td>{{ linha.depois }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.audio-comparison {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: var(--space-3);
}

.player-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  width: min(480px, 100%);
}

.side-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
}

.side-toggle button {
  padding: var(--space-1) var(--space-2-5);
  border: none;
  border-radius: calc(var(--radius-sm) - 2px);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.side-toggle button.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.side-toggle button:disabled {
  opacity: 0.45;
  cursor: default;
}

audio {
  width: 100%;
}

.pending,
.keeps-position {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.numbers {
  border-collapse: collapse;
  font-size: var(--fs-label-sm);
}

.numbers th,
.numbers td {
  padding: 2px var(--space-2);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.numbers thead th {
  color: var(--text-tertiary);
  font-weight: var(--fw-medium);
}

.numbers tbody th {
  text-align: left;
  color: var(--text-tertiary);
  font-weight: var(--fw-regular);
}

.numbers td {
  color: var(--text-secondary);
}

.numbers td:last-child {
  color: var(--color-primary);
}
</style>

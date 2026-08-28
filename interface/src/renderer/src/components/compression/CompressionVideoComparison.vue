<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { formatBytesDecimal } from '../../utils/formatBytes'
import { api, hasNativeApi } from '../../services/native'

// specs/008-compression-centre — T059: original e comprimido, no mesmo instante.
//
// **A sincronia é o componente inteiro.** Dois players independentes obrigariam
// a pessoa a alinhá-los à mão para comparar o mesmo quadro, e comparar dois
// instantes diferentes não diz nada sobre a compressão — diz sobre o conteúdo.
// É no mesmo quadro que a diferença entre qualidade 55 e 75 aparece.
//
// Sincronizar é mais delicado do que parece porque **um `timeupdate` que ajusta
// o outro player faz o outro emitir `timeupdate` de volta**. Sem uma trava, os
// dois se corrigem em laço e o vídeo engasga. A trava abaixo é o que impede
// isso; ela existe por ter acontecido, não por precaução.

const props = defineProps<{
  sourcePath: string
  outputPath: string | null
  originalBytes: number
  outputBytes: number | null
}>()

const { t } = useI18n()

const antes = ref<HTMLVideoElement | null>(null)
const depois = ref<HTMLVideoElement | null>(null)
const tocando = ref(false)

/** Verdadeiro enquanto um player está sendo ajustado pelo outro. Sem isto o eco
 *  do `timeupdate` volta e os dois ficam se corrigindo. */
let ajustando = false

const pronto = computed(() => Boolean(props.outputPath && hasNativeApi))

const antesSrc = computed(() => (hasNativeApi ? api.toFileUrl(props.sourcePath) : ''))
const depoisSrc = computed(() =>
  hasNativeApi && props.outputPath ? api.toFileUrl(props.outputPath) : ''
)

// Um resultado novo recomeça os dois do zero. Deixar o comprimido carregar no
// meio enquanto o original segue de onde estava é a dessincronia que este
// componente existe para evitar.
watch(
  () => props.outputPath,
  () => {
    tocando.value = false
    aplicar((v) => {
      v.pause()
      v.currentTime = 0
    })
  }
)

function aplicar(acao: (v: HTMLVideoElement) => void): void {
  for (const player of [antes.value, depois.value]) if (player) acao(player)
}

function alternar(): void {
  tocando.value = !tocando.value
  aplicar((v) => (tocando.value ? void v.play().catch(() => undefined) : v.pause()))
}

/** O ajuste só acontece quando os dois divergem mais que um limiar.
 *
 *  Corrigir a cada milissegundo faria o player corrigido travar continuamente —
 *  atribuir `currentTime` num `<video>` força uma busca, e uma busca por quadro
 *  é o mesmo que não reproduzir. O limiar é maior que um quadro a 24 fps e menor
 *  que qualquer desalinhamento perceptível. */
const LIMIAR_SEGUNDOS = 0.08

function sincronizarDe(origem: 'antes' | 'depois'): void {
  if (ajustando || !pronto.value) return
  const lider = origem === 'antes' ? antes.value : depois.value
  const seguidor = origem === 'antes' ? depois.value : antes.value
  if (!lider || !seguidor) return
  if (Math.abs(seguidor.currentTime - lider.currentTime) < LIMIAR_SEGUNDOS) return

  ajustando = true
  seguidor.currentTime = lider.currentTime
  // Liberado no próximo tique do laço de eventos: o `seeked` do seguidor
  // dispara antes, e é justamente ele que a trava precisa cobrir.
  setTimeout(() => {
    ajustando = false
  }, 0)
}
</script>

<template>
  <div class="video-comparison">
    <div class="stage" :class="{ single: !pronto }">
      <figure>
        <video
          ref="antes"
          :src="antesSrc"
          muted
          preload="metadata"
          @timeupdate="sincronizarDe('antes')"
        />
        <figcaption>
          {{ t('compression.compare.before') }} · {{ formatBytesDecimal(originalBytes) }}
        </figcaption>
      </figure>

      <figure v-if="pronto">
        <video
          ref="depois"
          :src="depoisSrc"
          muted
          preload="metadata"
          @timeupdate="sincronizarDe('depois')"
        />
        <figcaption>
          {{ t('compression.compare.after') }} · {{ formatBytesDecimal(outputBytes) }}
        </figcaption>
      </figure>
    </div>

    <div class="controls">
      <button type="button" class="play" @click="alternar">
        {{ tocando ? t('compression.compare.pause') : t('compression.compare.play') }}
      </button>
      <span v-if="!pronto" class="pending">{{ t('compression.compare.pending') }}</span>
      <span v-else class="synced">{{ t('compression.compare.synced') }}</span>
    </div>
  </div>
</template>

<style scoped>
.video-comparison {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  height: 100%;
  min-height: 0;
}

.stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.stage.single {
  grid-template-columns: 1fr;
}

figure {
  margin: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  overflow: hidden;
}

video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  background: var(--surface-1);
  border-radius: var(--radius-md);
}

figcaption {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.play {
  padding: var(--space-1) var(--space-2-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.play:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.pending,
.synced {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>

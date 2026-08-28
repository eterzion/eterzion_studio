<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CompareSlider from '../CompareSlider.vue'
import { useViewportPanZoom } from '../../composables/useViewportPanZoom'
import { formatBytesDecimal } from '../../utils/formatBytes'
import { api, hasNativeApi } from '../../services/native'

// specs/008-compression-centre — T045: antes e depois, com o mesmo enquadramento.
//
// **Zoom e deslocamento compartilhados** entre as duas imagens. Duas
// visualizações independentes obrigariam a pessoa a alinhá-las à mão para
// comparar o mesmo detalhe, e é justamente no detalhe que a diferença entre
// qualidade 60 e 80 aparece — comparar dois enquadramentos diferentes não diz
// nada sobre a compressão.
//
// Reusa `CompareSlider` e `useViewportPanZoom` das telas de Imagem e Vídeo em
// vez de reimplementá-los: o gesto de comparar é o mesmo, e uma segunda
// implementação divergiria no primeiro ajuste que só uma delas recebesse.

const props = defineProps<{
  sourcePath: string
  outputPath: string | null
  originalBytes: number
  outputBytes: number | null
}>()

const { t } = useI18n()

// O composable foi escrito para um "job" do editor; a Central tem os mesmos dois
// caminhos com outros nomes, e adaptá-los aqui é mais honesto que alargar a
// interface dele para um terceiro formato.
const jobLike = computed(() => ({
  id: 'compression-preview',
  sourcePath: props.sourcePath,
  status: props.outputPath ? 'done' : 'idle',
  lastExportPath: props.outputPath ?? undefined
}))

const {
  zoom,
  zoomLevels,
  viewMode,
  mediaStyle,
  resetView,
  onWheelZoom,
  onPanDown,
  onPanMove,
  onPanUp,
  beforeSrc,
  afterSrc
} = useViewportPanZoom(jobLike)

const sideBySide = computed(() => viewMode.value === 'side-by-side')

/** Sem resultado ainda não há o que comparar, e mostrar a origem dos dois lados
 *  sugeriria que a compressão não mudou nada. */
const ready = computed(() => Boolean(props.outputPath && hasNativeApi))
</script>

<template>
  <div class="comparison">
    <div class="comparison-toolbar">
      <div class="zoom-controls" role="group" :aria-label="t('compression.compare.zoom')">
        <button
          v-for="nivel in zoomLevels"
          :key="nivel"
          type="button"
          class="zoom-button"
          :class="{ active: zoom === nivel }"
          @click="zoom = nivel"
        >
          {{ nivel }}%
        </button>
        <button type="button" class="zoom-button" @click="resetView">
          {{ t('compression.compare.reset') }}
        </button>
      </div>

      <div class="view-controls" role="group" :aria-label="t('compression.compare.view')">
        <button
          type="button"
          class="zoom-button"
          :class="{ active: !sideBySide }"
          @click="viewMode = 'slider'"
        >
          {{ t('compression.compare.slider') }}
        </button>
        <button
          type="button"
          class="zoom-button"
          :class="{ active: sideBySide }"
          @click="viewMode = 'side-by-side'"
        >
          {{ t('compression.compare.sideBySide') }}
        </button>
      </div>
    </div>

    <div
      class="comparison-stage"
      @wheel.prevent="onWheelZoom"
      @pointerdown="onPanDown"
      @pointermove="onPanMove"
      @pointerup="onPanUp"
      @pointerleave="onPanUp"
    >
      <template v-if="ready">
        <div v-if="sideBySide" class="side-by-side">
          <figure>
            <img :src="beforeSrc" :style="mediaStyle" alt="" />
            <figcaption>
              {{ t('compression.compare.before') }} · {{ formatBytesDecimal(originalBytes) }}
            </figcaption>
          </figure>
          <figure>
            <img :src="afterSrc" :style="mediaStyle" alt="" />
            <figcaption>
              {{ t('compression.compare.after') }} · {{ formatBytesDecimal(outputBytes) }}
            </figcaption>
          </figure>
        </div>

        <CompareSlider
          v-else
          :before-src="beforeSrc"
          :after-src="afterSrc"
          :media-style="mediaStyle"
        />
      </template>

      <img
        v-else-if="hasNativeApi"
        :src="api.toFileUrl(sourcePath)"
        class="single-preview"
        alt=""
      />
      <p v-else class="comparison-empty">{{ t('compression.compare.pending') }}</p>
    </div>
  </div>
</template>

<style scoped>
.comparison {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  height: 100%;
  min-height: 0;
}

.comparison-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.zoom-controls,
.view-controls {
  display: flex;
  gap: var(--space-1);
}

.zoom-button {
  padding: 2px var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  cursor: pointer;
}

.zoom-button:hover {
  color: var(--text-primary);
}

.zoom-button.active {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.comparison-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--surface-1);
}

.side-by-side {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  width: 100%;
  height: 100%;
}

.side-by-side figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  overflow: hidden;
}

.side-by-side img,
.single-preview {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.side-by-side figcaption {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* Mesma razão do vídeo: comparar dois recortes minúsculos não compara nada. */
@media (max-width: 900px) {
  .side-by-side {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 1fr;
  }
}

.comparison-empty {
  margin: 0;
  font-size: var(--fs-body-sm);
  color: var(--text-tertiary);
}
</style>

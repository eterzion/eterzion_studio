<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft } from '@lucide/vue'
import MediaEditorShell, { type EditorItem } from '../components/MediaEditorShell.vue'
import UploadZone from '../components/UploadZone.vue'
import CompressionMediaTabs from '../components/compression/CompressionMediaTabs.vue'
import CompressionModeToggle from '../components/compression/CompressionModeToggle.vue'
import CompressionFileInfo from '../components/compression/CompressionFileInfo.vue'
import CompressionInputQueue from '../components/compression/CompressionInputQueue.vue'
import { useCompressionQueue } from '../composables/useCompressionQueue'
import { useCompressionSettings } from '../composables/useCompressionSettings'
import { useCompressionEstimate } from '../composables/useCompressionEstimate'
import { api, hasNativeApi } from '../services/native'
import type { MediaKind } from '../constants/compression'

// specs/008-compression-centre — T026: a casca em duas colunas.
//
// À esquerda o que a pessoa trouxe (pré-visualização, fila, informações do
// arquivo); à direita o que ela decide. É a mesma forma que as telas de Imagem e
// Vídeo já estabeleceram, e reusar `MediaEditorShell` não é economia de código:
// é o que impede a Central de virar uma tela com regras próprias dentro do mesmo
// aplicativo.
//
// O que já vale aqui e não pode regredir: **o modo padrão é Básico** (FR-038), e
// isso é constitucional — a condição 2 da exceção do Princípio V exige que quem
// nunca abrir o Avançado jamais encontre um nome de codec.
//
// Os controles por tipo de mídia chegam na Fase 3. Enquanto não chegam, a tela
// não finge tê-los: nenhum botão sem função.

defineEmits<{ back: [] }>()

const { t } = useI18n()

const queue = useCompressionQueue()
const { mediaKind, mode, target, payload } = useCompressionSettings()

const activeHandle = computed(() => queue.active.value?.media?.handle_id ?? null)

const { loading: estimating, stop: stopEstimating } = useCompressionEstimate({
  handleId: activeHandle,
  mediaKind,
  settings: payload,
  target
})

onBeforeUnmount(stopEstimating)

// Selecionar um arquivo troca a aba para o tipo que ele **é**, não o contrário.
// O tipo veio do conteúdo (FR-007), e deixar a aba discordar do arquivo
// selecionado ofereceria controles de vídeo para um MP3.
watch(
  () => queue.active.value?.media?.media_kind,
  (kind) => {
    if (kind) mediaKind.value = kind as MediaKind
  }
)

const shellItems = computed<EditorItem[]>(() =>
  queue.items.value.map((item) => ({
    id: item.id,
    fileName: item.fileName,
    sourcePath: item.path,
    statusLabel:
      item.status === 'ready'
        ? t(`compression.media.${item.media?.media_kind ?? 'image'}`)
        : t(`compression.queue.status.${item.status}`),
    // `animation` não existe no shell, que só desenha três ícones; um GIF é uma
    // imagem para efeito de miniatura, e é assim que ele aparece.
    kind: shellKind(item.media?.media_kind)
  }))
)

function shellKind(kind: string | undefined): 'image' | 'video' | 'audio' {
  if (kind === 'video' || kind === 'audio') return kind
  return 'image'
}

const previewPath = computed(() => queue.active.value?.path ?? null)
const previewKind = computed(() => queue.active.value?.media?.media_kind ?? null)
</script>

<template>
  <div class="compression-view" data-module="compression">
    <header class="compression-header">
      <button type="button" class="back-button" @click="$emit('back')">
        <ArrowLeft :size="16" />
        {{ t('compression.back') }}
      </button>
      <div class="header-text">
        <h1>{{ t('compression.title') }}</h1>
        <p>{{ t('compression.subtitle') }}</p>
      </div>
      <CompressionModeToggle v-model="mode" />
    </header>

    <CompressionMediaTabs v-model="mediaKind" :label="t('compression.title')" />

    <UploadZone
      v-if="!queue.items.value.length"
      class="compression-dropzone"
      :loading="queue.importing.value"
      :title="t('compression.upload.title')"
      :subtitle="t('compression.upload.subtitle')"
      :formats="['PNG', 'JPG', 'WEBP', 'MP4', 'MKV', 'MP3', 'GIF']"
      @files-dropped="queue.addDropped"
      @pick-files="queue.pick"
      @pick-folder="queue.pick"
    />

    <MediaEditorShell
      v-else
      :items="shellItems"
      :active-id="queue.activeId.value"
      :add-label="t('compression.queue.add')"
      @select="queue.select"
      @remove="queue.remove"
      @add="queue.pick"
    >
      <template #preview>
        <img
          v-if="hasNativeApi && previewPath && previewKind !== 'video' && previewKind !== 'audio'"
          :src="api.toFileUrl(previewPath)"
          class="preview-media"
          alt=""
        />
        <video
          v-else-if="hasNativeApi && previewPath && previewKind === 'video'"
          :src="api.toFileUrl(previewPath)"
          class="preview-media"
          controls
        />
        <audio
          v-else-if="hasNativeApi && previewPath && previewKind === 'audio'"
          :src="api.toFileUrl(previewPath)"
          class="preview-audio"
          controls
        />
        <p v-else class="preview-empty">{{ t('compression.upload.selectPrompt') }}</p>
      </template>

      <template #panel>
        <div class="panel-stack">
          <CompressionInputQueue
            :items="queue.items.value"
            :active-id="queue.activeId.value"
            @select="queue.select"
            @remove="queue.remove"
            @add="queue.pick"
            @clear="queue.clear"
          />

          <CompressionFileInfo v-if="queue.active.value?.media" :media="queue.active.value.media" />

          <p class="panel-pending">
            {{ t('compression.comingSoon', { media: t(`compression.media.${mediaKind}`) }) }}
          </p>
          <p v-if="estimating" class="panel-pending">{{ t('compression.estimate.loading') }}</p>
        </div>
      </template>
    </MediaEditorShell>
  </div>
</template>

<style scoped>
.compression-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  height: 100vh;
  overflow: hidden;
  background: var(--surface-0);
}

.compression-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-text {
  flex: 1;
  min-width: 0;
}

.compression-header h1 {
  font-size: var(--fs-h3);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  margin: 0;
}

.compression-header p {
  margin: var(--space-1) 0 0;
  font-size: var(--fs-body-sm);
  color: var(--text-secondary);
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label);
  cursor: pointer;
}

.back-button:hover {
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.compression-dropzone {
  flex: 1;
  min-height: 0;
}

.preview-media {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-audio {
  width: min(480px, 90%);
}

.preview-empty,
.panel-pending {
  margin: 0;
  font-size: var(--fs-body-sm);
  color: var(--text-tertiary);
}

.panel-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Zap } from '@lucide/vue'
import MediaEditorShell, { type EditorItem } from '../components/MediaEditorShell.vue'
import UploadZone from '../components/UploadZone.vue'
import AppButton from '../components/atoms/AppButton.vue'
import ProgressBar from '../components/atoms/ProgressBar.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import CompressionMediaTabs from '../components/compression/CompressionMediaTabs.vue'
import CompressionModeToggle from '../components/compression/CompressionModeToggle.vue'
import CompressionFileInfo from '../components/compression/CompressionFileInfo.vue'
import CompressionInputQueue from '../components/compression/CompressionInputQueue.vue'
import CompressionPresetSelector from '../components/compression/CompressionPresetSelector.vue'
import CompressionEstimatePanel from '../components/compression/CompressionEstimate.vue'
import CompressionSummary from '../components/compression/CompressionSummary.vue'
import CompressionComparison from '../components/compression/CompressionComparison.vue'
import CompressionResult from '../components/compression/CompressionResult.vue'
import CompressionExportPanel from '../components/compression/CompressionExportPanel.vue'
import ImageCompressionSettings from '../components/compression/ImageCompressionSettings.vue'
import { useCompressionQueue } from '../composables/useCompressionQueue'
import { useCompressionSettings } from '../composables/useCompressionSettings'
import { useCompressionEstimate } from '../composables/useCompressionEstimate'
import { useCompressionJob } from '../composables/useCompressionJob'
import {
  getCapabilities,
  listPresets,
  type CapabilityEntry,
  type CompressionCapabilities,
  type CompressionExport,
  type CompressionPreset
} from '../services/compression'
import { api, hasNativeApi } from '../services/native'
import type { MediaKind } from '../constants/compression'

// specs/008-compression-centre — a Central, com Imagem funcionando ponta a ponta.
//
// À esquerda o que a pessoa trouxe; à direita o que ela decide. É a forma que as
// telas de Imagem e Vídeo já estabeleceram, e reusar `MediaEditorShell` não é
// economia de código: é o que impede a Central de virar uma tela com regras
// próprias dentro do mesmo aplicativo.
//
// Duas regras que não podem regredir:
//
// **O modo padrão é Básico** (FR-038), e é constitucional — a condição 2 da
// exceção do Princípio V exige que quem nunca abrir o Avançado jamais encontre
// um nome de codec.
//
// **Vídeo, áudio e GIF ainda não comprimem**, e a tela diz isso em vez de
// oferecer um botão que falha. Um botão sem função é pior que a sua ausência: a
// pessoa monta as configurações inteiras antes de descobrir.

defineEmits<{ back: [] }>()

const { t } = useI18n()

const queue = useCompressionQueue()
const { mediaKind, mode, settings, target, payload, set, setTarget, applyPreset } =
  useCompressionSettings()
const job = useCompressionJob()

const capabilities = ref<CompressionCapabilities | null>(null)
const presets = ref<CompressionPreset[]>([])
const selectedPreset = ref<string | null>(null)
const presetModified = ref(false)

const exportOptions = ref<CompressionExport>({
  directory: null,
  naming_pattern: '{filename}_compressed',
  conflict_policy: 'rename',
  apply_to_all: false
})

const activeHandle = computed(() => queue.active.value?.media?.handle_id ?? null)
const activeMedia = computed(() => queue.active.value?.media ?? null)

const {
  estimate,
  loading: estimating,
  error: estimateError,
  stop: stopEstimating
} = useCompressionEstimate({
  handleId: activeHandle,
  mediaKind,
  settings: payload,
  target
})

onMounted(async () => {
  // As capacidades vêm de sonda funcional no backend. Sem elas a tela ofereceria
  // formatos que esta máquina não grava, e a falha chegaria no meio da
  // exportação em vez de antes da escolha (FR-043).
  try {
    capabilities.value = await getCapabilities()
  } catch {
    capabilities.value = null
  }
  try {
    presets.value = (await listPresets()).presets
  } catch {
    presets.value = []
  }
})

onBeforeUnmount(() => {
  stopEstimating()
  job.stop()
})

watch(
  () => queue.active.value?.media?.media_kind,
  (kind) => {
    // Selecionar um arquivo troca a aba para o tipo que ele **é**, não o
    // contrário: deixar a aba discordar ofereceria controles de vídeo para um MP3.
    if (kind) mediaKind.value = kind as MediaKind
  }
)

// Mexer numa configuração desfaz a afirmação "isto é o preset X". Um preset que
// continua selecionado enquanto os valores já são outros é falso sobre o que vai
// acontecer.
watch(payload, () => {
  if (selectedPreset.value) presetModified.value = true
})

const presetsForKind = computed(() =>
  presets.value.filter((p) => p.media_kind === mediaKind.value)
)

function choosePreset(id: string | null): void {
  selectedPreset.value = id
  presetModified.value = false
  if (!id) return
  const preset = presets.value.find((p) => p.id === id)
  if (preset) applyPreset(mediaKind.value, preset.settings)
}

const imageFormats = computed<CapabilityEntry[]>(() => capabilities.value?.image.formats ?? [])

/** Só Imagem comprime nesta fase. As demais chegam nas fases 4, 5 e 6. */
const supported = computed(() => mediaKind.value === 'image')

const canRun = computed(
  () => Boolean(activeHandle.value) && supported.value && !job.running.value
)

async function run(): Promise<void> {
  if (!activeHandle.value) return
  await job.run({
    handleId: activeHandle.value,
    mediaKind: mediaKind.value,
    settings: payload.value,
    target: target.value,
    mode: mode.value,
    presetId: selectedPreset.value,
    export: exportOptions.value
  })
}

function reveal(path: string): void {
  if (hasNativeApi) void api.showItemInFolder(path)
}

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
        <CompressionComparison
          v-if="previewPath && previewKind === 'image'"
          :source-path="previewPath"
          :output-path="job.result.value?.outputPath ?? null"
          :original-bytes="activeMedia?.size_bytes ?? 0"
          :output-bytes="job.result.value?.outputSizeBytes ?? null"
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

          <CompressionFileInfo v-if="activeMedia" :media="activeMedia" />

          <template v-if="supported">
            <CompressionPresetSelector
              :presets="presetsForKind"
              :model-value="selectedPreset"
              :modified="presetModified"
              :disabled="job.running.value"
              @update:model-value="choosePreset"
            />

            <ImageCompressionSettings
              :settings="settings"
              :target="target"
              :mode="mode"
              :formats="imageFormats"
              :disabled="job.running.value"
              @set="set"
              @update:target="setTarget"
            />

            <CompressionEstimatePanel
              :estimate="estimate"
              :loading="estimating"
              :error="estimateError"
            />

            <CompressionSummary :settings="payload" :media-kind="mediaKind" :mode="mode" />

            <CollapsiblePanel :title="t('compression.export.title')" :default-open="false">
              <CompressionExportPanel v-model="exportOptions" />
            </CollapsiblePanel>

            <AppButton
              variant="primary"
              :disabled="!canRun"
              :loading="job.running.value"
              @click="run"
            >
              <Zap :size="15" />
              {{ t('compression.run') }}
            </AppButton>

            <ProgressBar v-if="job.running.value" :value="job.progress.value" />

            <p v-if="job.error.value" class="panel-error">
              {{ t(`compression.refusal.${job.error.value}`) }}
            </p>

            <CompressionResult v-if="job.result.value" :result="job.result.value" @reveal="reveal" />
          </template>

          <p v-else class="panel-pending">
            {{ t('compression.comingSoon', { media: t(`compression.media.${mediaKind}`) }) }}
          </p>
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

.panel-error {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-warning);
}

.panel-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>

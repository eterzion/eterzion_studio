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
import VideoCompressionSettings from '../components/compression/VideoCompressionSettings.vue'
import CompressionVideoComparison from '../components/compression/CompressionVideoComparison.vue'
import AudioCompressionSettings from '../components/compression/AudioCompressionSettings.vue'
import CompressionAudioComparison from '../components/compression/CompressionAudioComparison.vue'
import AnimationCompressionSettings from '../components/compression/AnimationCompressionSettings.vue'
import CompressionQueue from '../components/compression/CompressionQueue.vue'
import CompressionHistory from '../components/compression/CompressionHistory.vue'
import { useCompressionQueue } from '../composables/useCompressionQueue'
import { useCompressionSettings } from '../composables/useCompressionSettings'
import { useCompressionEstimate } from '../composables/useCompressionEstimate'
import { useCompressionJob } from '../composables/useCompressionJob'
import { useCompressionBatch, type BatchRequest } from '../composables/useCompressionBatch'
import {
  clearHistory,
  createPreset,
  deleteHistoryEntry,
  deletePreset,
  duplicatePreset,
  getCapabilities,
  listHistory,
  listPresets,
  updatePreset,
  type CapabilityEntry,
  type CompressionCapabilities,
  type CompressionExport,
  type CompressionHistoryEntry,
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
// Os quatro tipos comprimem. O que ainda não existe — lote, presets do usuário e
// histórico — chega nas fases seguintes, e a tela não finge tê-los.

defineEmits<{ back: [] }>()

const { t } = useI18n()

const queue = useCompressionQueue()
const { mediaKind, mode, settings, target, payload, set, setTarget, applyPreset } =
  useCompressionSettings()
const job = useCompressionJob()
const batch = useCompressionBatch()

const capabilities = ref<CompressionCapabilities | null>(null)
const presets = ref<CompressionPreset[]>([])
const history = ref<CompressionHistoryEntry[]>([])
const selectedPreset = ref<string | null>(null)
const presetModified = ref(false)

const exportOptions = ref<CompressionExport>({
  directory: null,
  naming_pattern: '{filename}_compressed',
  conflict_policy: 'rename'
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
  await Promise.all([refreshPresets(), refreshHistory()])
})

async function refreshPresets(): Promise<void> {
  try {
    presets.value = (await listPresets()).presets
  } catch {
    presets.value = []
  }
}

async function refreshHistory(): Promise<void> {
  try {
    history.value = (await listHistory()).entries
  } catch {
    history.value = []
  }
}

onBeforeUnmount(() => {
  stopEstimating()
  job.stop()
  batch.stop()
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

const presetsForKind = computed(() => presets.value.filter((p) => p.media_kind === mediaKind.value))

function choosePreset(id: string | null): void {
  selectedPreset.value = id
  presetModified.value = false
  if (!id) return
  const preset = presets.value.find((p) => p.id === id)
  if (preset) applyPreset(mediaKind.value, preset.settings)
}

const imageFormats = computed<CapabilityEntry[]>(() => capabilities.value?.image.formats ?? [])

/** Quantos arquivos prontos existem do tipo aberto agora. Comprimir "todos"
 *  significa todos os do tipo em foco — misturar tipos numa passada aplicaria a
 *  um MP3 as configurações montadas para uma imagem. */
const readyOfKind = computed(() =>
  queue.ready.value.filter((i) => i.media?.media_kind === mediaKind.value)
)

const busy = computed(() => job.running.value || batch.running.value)
const canRun = computed(() => Boolean(activeHandle.value) && !busy.value)
const canRunAll = computed(() => readyOfKind.value.length > 1 && !busy.value)

function batchRequests(): BatchRequest[] {
  return readyOfKind.value.map((item) => ({
    queueId: item.id,
    fileName: item.fileName,
    handleId: item.media!.handle_id,
    mediaKind: mediaKind.value,
    // As mesmas configurações para todos — é o que "aplicar a todos" quer dizer
    // (FR-035). Configuração individual continua sendo comprimir um por vez.
    settings: payload.value,
    target: target.value,
    mode: mode.value,
    presetId: selectedPreset.value,
    export: exportOptions.value
  }))
}

async function runAll(): Promise<void> {
  await batch.run(batchRequests())
  await refreshHistory()
}

async function retryFailed(): Promise<void> {
  await batch.retryFailed(batchRequests())
  await refreshHistory()
}

async function run(): Promise<void> {
  if (!activeHandle.value) return
  await runAndRecord({
    handleId: activeHandle.value,
    mediaKind: mediaKind.value,
    settings: payload.value,
    target: target.value,
    mode: mode.value,
    presetId: selectedPreset.value,
    export: exportOptions.value
  })
}

/** Comprime e recarrega o histórico.
 *
 *  O backend grava a entrada; esta chamada é só para a lista na tela refletir o
 *  que acabou de acontecer sem exigir que a pessoa reabra a Central. */
async function runAndRecord(pedido: Parameters<typeof job.run>[0]): Promise<void> {
  await job.run(pedido)
  await refreshHistory()
}

async function savePreset(name: string): Promise<void> {
  const proprio = presets.value.find((p) => p.id === selectedPreset.value && p.origin === 'user')
  try {
    const salvo = proprio
      ? await updatePreset(proprio.id, { name, settings: payload.value })
      : await createPreset({ name, media_kind: mediaKind.value, settings: payload.value })
    await refreshPresets()
    selectedPreset.value = salvo.id
    // Salvar torna o preset e as configurações a mesma coisa de novo.
    presetModified.value = false
  } catch {
    await refreshPresets()
  }
}

async function duplicateExisting(pedido: { id: string; name: string }): Promise<void> {
  try {
    const copia = await duplicatePreset(pedido.id, pedido.name)
    await refreshPresets()
    selectedPreset.value = copia.id
    presetModified.value = false
  } catch {
    await refreshPresets()
  }
}

async function removePreset(id: string): Promise<void> {
  try {
    await deletePreset(id)
  } finally {
    if (selectedPreset.value === id) selectedPreset.value = null
    await refreshPresets()
  }
}

/** Repetir parte do **snapshot** da entrada, nunca do preset (FR-063).
 *
 *  O preset pode ter mudado desde a execução, e repetir por ele produziria um
 *  resultado diferente do que a própria entrada exibe. */
function repeatFromHistory(entry: CompressionHistoryEntry): void {
  mediaKind.value = entry.media_kind
  applyPreset(entry.media_kind, entry.settings_snapshot)
  // Nenhum preset fica selecionado: o que está na tela agora veio do histórico,
  // e apontar para um preset afirmaria uma origem que pode não bater.
  selectedPreset.value = null
  presetModified.value = false
}

async function removeHistoryEntry(id: string): Promise<void> {
  try {
    await deleteHistoryEntry(id)
  } finally {
    await refreshHistory()
  }
}

async function clearAllHistory(): Promise<void> {
  try {
    await clearHistory()
  } finally {
    await refreshHistory()
  }
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
        <CompressionVideoComparison
          v-else-if="previewPath && previewKind === 'video'"
          :source-path="previewPath"
          :output-path="job.result.value?.outputPath ?? null"
          :original-bytes="activeMedia?.size_bytes ?? 0"
          :output-bytes="job.result.value?.outputSizeBytes ?? null"
        />
        <CompressionAudioComparison
          v-else-if="previewPath && previewKind === 'audio'"
          :source-path="previewPath"
          :output-path="job.result.value?.outputPath ?? null"
          :media="activeMedia"
          :output-bytes="job.result.value?.outputSizeBytes ?? null"
          :applied="job.result.value?.applied ?? null"
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

          <CompressionPresetSelector
            :presets="presetsForKind"
            :model-value="selectedPreset"
            :modified="presetModified"
            :disabled="job.running.value"
            @update:model-value="choosePreset"
            @save="savePreset"
            @duplicate="duplicateExisting"
            @remove="removePreset"
          />

          <ImageCompressionSettings
            v-if="mediaKind === 'image'"
            :settings="settings"
            :target="target"
            :mode="mode"
            :formats="imageFormats"
            :disabled="job.running.value"
            @set="set"
            @update:target="setTarget"
          />

          <VideoCompressionSettings
            v-else-if="mediaKind === 'video'"
            :settings="settings"
            :target="target"
            :mode="mode"
            :capabilities="capabilities"
            :disabled="job.running.value"
            @set="set"
            @update:target="setTarget"
          />

          <AudioCompressionSettings
            v-else-if="mediaKind === 'audio'"
            :settings="settings"
            :target="target"
            :mode="mode"
            :capabilities="capabilities"
            :disabled="job.running.value"
            @set="set"
            @update:target="setTarget"
          />

          <AnimationCompressionSettings
            v-else
            :settings="settings"
            :target="target"
            :mode="mode"
            :capabilities="capabilities"
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

          <AppButton
            v-if="canRunAll"
            variant="outline"
            :disabled="busy"
            :loading="batch.running.value"
            @click="runAll"
          >
            {{ t('compression.batch.runAll', readyOfKind.length) }}
          </AppButton>

          <ProgressBar v-if="job.running.value" :value="job.progress.value" />

          <div v-if="job.error.value" class="panel-error">
            <p class="error-message">{{ t(`compression.refusal.${job.error.value}`) }}</p>

            <!-- A saída da ferramenta é indispensável para diagnosticar e
                 ilegível para decidir (FR-065). Recolhida: quem precisa copiar
                 para um relatório encontra; quem só quer saber o que aconteceu
                 lê a frase de cima. -->
            <details v-if="job.errorDetailText.value" class="error-details">
              <summary>{{ t('compression.error.showDetail') }}</summary>
              <pre>{{ job.errorDetailText.value }}</pre>
            </details>
          </div>

          <CompressionResult v-if="job.result.value" :result="job.result.value" @reveal="reveal" />
          <CompressionQueue
            v-if="batch.items.value.length"
            :items="batch.items.value"
            :running="batch.running.value"
            :overall-progress="batch.overallProgress.value"
            :saved-bytes="batch.savedBytes.value"
            :original-bytes="batch.originalBytes.value"
            :failed-count="batch.failed.value.length"
            :finished-count="batch.finished.value"
            @cancel-item="batch.cancelItem"
            @cancel-all="batch.cancelAll"
            @retry-failed="retryFailed"
            @reveal="reveal"
          />
          <CompressionHistory
            :entries="history"
            @repeat="repeatFromHistory"
            @remove="removeHistoryEntry"
            @clear="clearAllHistory"
            @reveal="reveal"
          />
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
  /* `flex: 1` porque `.app-shell` é um flex row: sem isto a tela encolhe até a
     largura do conteúdo e sobra metade da janela em preto. É o que Imagem,
     Vídeo e Áudio já fazem — a Central era a única sem. `min-width: 0` deixa os
     filhos com texto longo encolherem em vez de esticar a coluna. */
  flex: 1;
  min-width: 0;
}

.compression-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

/* Num notebook estreito o subtítulo é a primeira coisa dispensável: o título e
   o alternador de modo precisam caber, e a explicação da tela não. */
@media (max-width: 760px) {
  .compression-header p {
    display: none;
  }
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
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.error-message {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-warning);
}

.error-details summary {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  cursor: pointer;
}

.error-details pre {
  margin: var(--space-1) 0 0;
  padding: var(--space-1-5);
  max-height: 160px;
  overflow: auto;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: var(--fs-label-sm);
  white-space: pre-wrap;
  word-break: break-word;
}

.panel-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import RangeSlider from '../components/RangeSlider.vue'
import { profileOptions, deviceOptions } from '../constants/processing'
import CompareSlider from '../components/CompareSlider.vue'
import ComparisonStats from '../components/ComparisonStats.vue'
import AppSelect from '../components/AppSelect.vue'
import TechnicalDetails from '../components/TechnicalDetails.vue'
import NumberStepper from '../components/NumberStepper.vue'
import ModeTabs from '../components/ModeTabs.vue'
import ImageInfoPanel from '../components/ImageInfoPanel.vue'
import AppButton from '../components/atoms/AppButton.vue'
import ProgressBar from '../components/atoms/ProgressBar.vue'
import AppSpinner from '../components/atoms/AppSpinner.vue'
import {
  Minus,
  Plus,
  Maximize2,
  Cpu,
  Expand,
  ChartNoAxesColumn,
  Link,
  Unlink,
  Upload,
  FolderOpen,
  FileOutput,
  SlidersHorizontal,
  X,
  AlertCircle,
  XCircle,
  Columns2,
  GalleryHorizontal,
  RotateCcw,
  Sparkles
} from '@lucide/vue'
import { api, hasNativeApi } from '../services/native'
import { type ContentType, type Profile } from '../services/api'
import { errorCategoryCopy, getImageExportOptions, type ImageExportOptions } from '../services/api'
import { useViewportPanZoom } from '../composables/useViewportPanZoom'
import { useVideoPreviewPipeline } from '../composables/useVideoPreviewPipeline'
import {
  hasUnpreviewableEffects,
  neutralAdjustments,
  neutralEffects,
  type VideoAdjustments,
  type VideoEffects,
  type VideoTransform
} from '../composables/useVideoEdits'
import VideoAdjustmentsPanel from '../components/video/VideoAdjustmentsPanel.vue'
import VideoTransformPanel from '../components/video/VideoTransformPanel.vue'
import { useExportPanel } from '../composables/useExportPanel'
import ConflictDialog from '../components/ConflictDialog.vue'
import SavedResultCard from '../components/SavedResultCard.vue'
import {
  addFiles,
  queueState,
  getActiveJob,
  setActiveJob,
  applyConfigToAll,
  validateScaleConfig,
  estimatedOutputSize,
  estimatedOutputBytes,
  ensureCustomSizeDefaults,
  syncCustomSizeToPreset,
  effectiveCustomScale,
  MAX_OUTPUT_DIMENSION,
  MIN_DIMENSION,
  startProcessing,
  cancelProcessing,
  removeJob,
  type ImageExport,
  type Job
} from '../store/jobs'

defineEmits<{
  back: []
}>()

const { t } = useI18n()

const profiles = computed(() => profileOptions())
const devices = computed(() => deviceOptions())

const panelOpen = ref(false)

// ------------------------------- selected job ------------------------------- //
const job = computed<Job | undefined>(() => getActiveJob())
const imageJobs = computed(() => queueState.jobs)
const configuringJobs = computed(() => queueState.jobs.filter((j) => j.status === 'configuring'))

// ------------------------------- preview viewport (zoom + pan) ------------------------------- //
const {
  zoom,
  zoomLevels,
  viewMode,
  spaceHeld,
  panning,
  mediaStyle,
  resetView,
  onWheelZoom,
  onPanDown,
  onPanMove,
  onPanUp,
  beforeSrc,
  afterSrc,
  onKeyDown,
  onKeyUp
} = useViewportPanZoom(job)

// ------------------------------- content type + profile ------------------------------- //
// FR-009/FR-063: never a model name — only what the backend actually accepts as
// intent (profile_resolver.py resolves the implementation internally). The
// content-type indicator is auto-detected on file add (store/jobs.ts addFiles())
// but stays editable here — FR-096, and this editor only handles images, so the
// only two valid content types are photo <-> anime_image.
const importError = ref<string | null>(null)

const contentTypeOptions = computed<{ value: ContentType; label: string; description: string }[]>(
  // "Sem modelo" leads the list because it is the choice that changes the most
  // about what happens — everything below it runs a model, it does not. The
  // selected value still comes from detection; only the order is fixed here.
  () => [
    {
      value: 'no_model',
      label: t('imageEditor.noModelLabel'),
      description: t('imageEditor.noModelDescription')
    },
    {
      value: 'photo',
      label: t('imageEditor.photoLabel'),
      description: t('imageEditor.photoDescription')
    },
    {
      value: 'anime_image',
      label: t('imageEditor.animeLabel'),
      description: t('imageEditor.animeDescription')
    },
    {
      value: 'pixel_art',
      label: t('imageEditor.pixelArtLabel'),
      description: t('imageEditor.pixelArtDescription')
    }
  ]
)

// The descriptions carry what the field hints used to say, so removing those
// lines costs no information — they are read while choosing instead of after.

// Quais formatos a tela oferece. Quais deles a MÁQUINA consegue escrever é
// outra pergunta, e quem responde é GET /image/export-options — a exportação
// re-codifica pelo OpenCV, e builds de OpenCV diferem em quais codecs carregam
// (WebP e TIFF são opcionais; headless não é a mesma build que a completa).
// Oferecer um que a build não escreve faz a exportação falhar depois da escolha,
// que é o que o Princípio XIII proíbe. Mesmo desenho do painel de vídeo.
const OFFERED_EXPORT_FORMATS = ['png', 'jpg', 'webp'] as const

const imageExportOptions = ref<ImageExportOptions | null>(null)

onMounted(async () => {
  try {
    imageExportOptions.value = await getImageExportOptions()
  } catch {
    // Null quer dizer "ainda não sei", e aí nada é desabilitado: bloquear a
    // exportação porque a consulta falhou seria pior do que deixar tentar.
    imageExportOptions.value = null
  }
})

function formatIsAvailable(value: string): boolean {
  const known = imageExportOptions.value?.formats.find((f) => f.value === value)
  return known ? known.available : true
}

const exportFormatOptions = computed(() => [
  { value: 'keep', label: t('destination.keepFormat'), disabled: false, description: undefined },
  ...OFFERED_EXPORT_FORMATS.map((value) => ({
    value,
    label: `.${value}`,
    disabled: !formatIsAvailable(value),
    // Chave, nunca o nome da biblioteca — o Princípio V vale nesta superfície
    // como em qualquer outra.
    description: formatIsAvailable(value) ? undefined : t('imageEditor.formatUnavailable')
  }))
])

const noExportFormatAvailable = computed(() =>
  OFFERED_EXPORT_FORMATS.every((value) => !formatIsAvailable(value))
)

// Se o formato escolhido não pode ser escrito aqui, cair num que pode em vez de
// deixar o botão pronto para falhar.
watch(exportFormatOptions, (options) => {
  const atual = exportacao.value.format
  if (atual === 'keep' || formatIsAvailable(atual)) return
  const usable = options.find((option) => !option.disabled && option.value !== 'keep')
  if (usable) exportacao.value.format = usable.value as ImageExport['format']
})

// A qualidade so' existe em JPEG e WebP. Em PNG nao ha' o que escolher, e um
// controle que nao faz nada e' pior que a sua ausencia.
const exportIsLossy = computed(() => {
  const formato =
    exportacao.value.format === 'keep'
      ? (/\.([^.]+)$/.exec(job.value?.fileName ?? '')?.[1] ?? '').toLowerCase()
      : exportacao.value.format
  return ['jpg', 'jpeg', 'webp'].includes(formato)
})

const qualityProfileOptions = computed(() =>
  (['fast', 'balanced', 'quality'] as const).map((value) => ({
    value,
    label: t(`imageEditor.qualityProfile.${value}`)
  }))
)
const conflictOptions = computed(() => [
  { value: 'rename', label: t('destination.conflict.rename') },
  { value: 'overwrite', label: t('destination.conflict.overwrite') },
  { value: 'ask', label: t('destination.conflict.ask') }
])

// ------------------------------- ajustes, efeitos e transformacao ------------------------------- //
// Os mesmos paineis e os mesmos filtros do Video, aplicados ao resultado depois
// do modelo (app/exportacao_de_imagem.py). A previa e' o shader do Video, que
// reproduz o eq/hue do FFmpeg -- agora tambem sobre uma imagem, com girar e
// espelhar.
// Os `<chave>_enabled` sao booleanos e os valores sao numeros; a chave decide
// qual, como no Video (VideoEditorView.vue).
function setAdjustment(key: keyof VideoAdjustments, value: number | boolean): void {
  if (!job.value) return
  const adjustments = job.value.edits.adjustments
  if (typeof value === 'boolean') (adjustments[key] as boolean) = value
  else (adjustments[key] as number) = value
}
function setEffect(key: keyof VideoEffects, value: number | boolean): void {
  if (!job.value) return
  const effects = job.value.edits.effects
  if (typeof value === 'boolean') (effects[key] as boolean) = value
  else (effects[key] as number) = value
}
function setTransform(patch: Partial<VideoTransform>): void {
  if (job.value) Object.assign(job.value.edits.transform, patch)
}
function resetAdjustments(): void {
  if (job.value) Object.assign(job.value.edits.adjustments, neutralAdjustments())
}
function resetEffects(): void {
  if (job.value) Object.assign(job.value.edits.effects, neutralEffects())
}

const previewPipeline = useVideoPreviewPipeline()
const previewSource = ref<HTMLImageElement | null>(null)
const previewCanvas = ref<HTMLCanvasElement | null>(null)

/** A previa so' entra quando ha' o que mostrar -- sem ajuste, a imagem
 *  original, sem passar pela GPU. */
const previewActive = computed(() => {
  const j = job.value
  if (!j || j.status === 'done' || !previewPipeline.supported.value) return false
  const e = j.edits
  return (
    JSON.stringify(e.adjustments) !== JSON.stringify(neutralAdjustments()) ||
    e.transform.rotation_degrees !== 0 ||
    e.transform.flip_horizontal ||
    e.transform.flip_vertical
  )
})

function startPreview(): void {
  if (previewSource.value && previewCanvas.value) {
    previewPipeline.start(previewSource.value, previewCanvas.value)
  }
}

watch(
  () => [previewActive.value, job.value?.id] as const,
  async ([ativa]) => {
    await nextTick()
    if (ativa) startPreview()
    else previewPipeline.stop()
  }
)

watch(
  () => job.value?.edits,
  (edits) => {
    if (!edits) return
    previewPipeline.apply(edits.adjustments)
    previewPipeline.geometry(edits.transform)
  },
  { deep: true, immediate: true }
)

const editsNeedDisclosure = computed(() =>
  job.value ? hasUnpreviewableEffects(job.value.edits) : false
)
// Elapsed-time ticker for the processing panel (spec 5.2: elapsed time alongside
// progress, since the model step can be long).
const nowTick = ref(Date.now())
let tickTimer: ReturnType<typeof setInterval> | undefined

const elapsedLabel = computed(() => {
  const startedAt = job.value?.processingStartedAt
  if (!startedAt || job.value?.status !== 'processing') return null
  const seconds = Math.max(0, Math.floor((nowTick.value - startedAt) / 1000))
  return seconds >= 60 ? `${Math.floor(seconds / 60)}min ${seconds % 60}s` : `${seconds}s`
})

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  tickTimer = setInterval(() => (nowTick.value = Date.now()), 1000)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  if (tickTimer) clearInterval(tickTimer)
})

// ------------------------------- scale config helpers ------------------------------- //
type ScaleMode = 'preset' | 'custom'

const scaleModeOptions = computed(() => [
  { value: 'preset', label: t('imageEditor.modePreset') },
  { value: 'custom', label: t('imageEditor.modeCustom') }
])

/** Whether this job will run a model at all — the content type decides. */
const usesModel = computed(() => {
  const ct = job.value?.scaleConfig.contentType
  return ct !== 'pixel_art' && ct !== 'no_model'
})

function switchScaleMode(j: Job, mode: 'preset' | 'custom'): void {
  const from = j.scaleConfig.mode
  j.scaleConfig.mode = mode
  // Arriving at Medida exata from Ampliar starts at the size Ampliar was going
  // to produce: switching between two ways of saying "how big" should not
  // change how big. ensureCustomSizeDefaults alone did not do it — it returns
  // early once the fields hold anything at all, so a value left from an
  // earlier visit survived and the 4x the person had just chosen was ignored.
  if (mode === 'custom' && from === 'preset') syncCustomSizeToPreset(j)
  else if (mode === 'custom') ensureCustomSizeDefaults(j)
}

function setPresetFactor(j: Job, factor: 2 | 4): void {
  j.scaleConfig.presetFactor = factor
  syncCustomSizeToPreset(j)
}

function onCustomWidthInput(j: Job, raw: string): void {
  const value = Number(raw)
  j.scaleConfig.customWidth = value || null
  if (j.scaleConfig.lockAspectRatio && value && j.sourceMeta.width && j.sourceMeta.height) {
    j.scaleConfig.customHeight = Math.round(value * (j.sourceMeta.height / j.sourceMeta.width))
  }
}
function onCustomHeightInput(j: Job, raw: string): void {
  const value = Number(raw)
  j.scaleConfig.customHeight = value || null
  if (j.scaleConfig.lockAspectRatio && value && j.sourceMeta.width && j.sourceMeta.height) {
    j.scaleConfig.customWidth = Math.round(value * (j.sourceMeta.width / j.sourceMeta.height))
  }
}

function toggleAspectLock(j: Job): void {
  j.scaleConfig.lockAspectRatio = !j.scaleConfig.lockAspectRatio
  // Re-locking snaps the height back to the source aspect ratio, taking width as truth.
  if (
    j.scaleConfig.lockAspectRatio &&
    j.scaleConfig.customWidth &&
    j.sourceMeta.width &&
    j.sourceMeta.height
  ) {
    j.scaleConfig.customHeight = Math.round(
      j.scaleConfig.customWidth * (j.sourceMeta.height / j.sourceMeta.width)
    )
  }
}

const validity = computed(() => (job.value ? validateScaleConfig(job.value) : { valid: false }))
const estimate = computed(() => (job.value ? estimatedOutputSize(job.value) : null))
const estimateBytes = computed(() => (job.value ? estimatedOutputBytes(job.value) : null))

const customFactor = computed(() => {
  const j = job.value
  if (!j || j.scaleConfig.mode !== 'custom') return null
  return effectiveCustomScale(j)
})

// The resolved implementation always runs at the chosen preset factor (2x/4x);
// a custom target beyond that is reached by interpolation on top of its output
// — worth telling the user, even though the specific model is never named here.
const customBeyondNative = computed(() => {
  const j = job.value
  const factor = customFactor.value
  if (!j || factor == null) return false
  // The warning is about asking a model for more than the factor it was
  // trained at, so the surplus comes from interpolation. Pixel art runs no
  // model and has no native factor: repeating pixels gives the same result at
  // any whole multiple, and the sentence would be describing something that
  // does not happen.
  const ct = j.scaleConfig.contentType
  if (ct === 'pixel_art' || ct === 'no_model') return false
  return factor > j.scaleConfig.presetFactor + 0.01
})

async function process(j: Job): Promise<void> {
  await startProcessing(j, {
    exportacao: { ...exportacao.value },
    filename: exportFilename.value,
    perguntarConflito: pergunta.perguntar
  })
}

/** Cada imagem com o nome do proprio original: um nome digitado vale para a
 *  imagem ativa, e repetido em todas so' geraria conflitos. */
async function processAll(): Promise<void> {
  for (const j of configuringJobs.value) {
    const v = validateScaleConfig(j)
    if (v.valid) {
      void startProcessing(j, {
        exportacao: { ...exportacao.value },
        perguntarConflito: pergunta.perguntar
      })
    }
  }
}

function reprocess(j: Job): void {
  j.status = 'configuring'
  j.outputPath = undefined
}

async function cancel(j: Job): Promise<void> {
  await cancelProcessing(j)
}

// ------------------------------- export (chosen before processing) ------------------------------- //
const { exportacao, exportFilename, pergunta, pickExportFolder } = useExportPanel()

// O nome digitado e' de uma imagem; trocar de imagem volta ao nome do original.
watch(
  () => job.value?.id,
  () => (exportFilename.value = null)
)

// ------------------------------- import / queue ------------------------------- //
async function importFiles(): Promise<void> {
  if (!hasNativeApi) return
  const result = await api.selectFiles(['image'])
  if (result.canceled) return
  importError.value = result.rejected.length
    ? t('importing.rejected', result.rejected.length)
    : null
  const upload = await addFiles(result.files)
  if (!job.value && upload.added[0]) setActiveJob(upload.added[0].id)
}

// Empty-state upload — same intake as the old HomeView drop zone (pick/drop/
// folder/paste all land in the same store/jobs.ts queue), now local to this
// tab instead of requiring a detour through Home first.
const uploading = ref(false)

function reportImportResult(result: {
  added: { id: string }[]
  rejected: { name: string; reason: string }[]
  duplicates: string[]
}): void {
  if (result.rejected.length) {
    importError.value = result.rejected.map((r) => `${r.name}: ${r.reason}`).join(' · ')
  } else if (!result.added.length && result.duplicates.length) {
    importError.value = t('importing.alreadyQueued', { files: result.duplicates.join(', ') })
  } else {
    importError.value = null
  }
  if (result.added.length) setActiveJob(result.added[0].id)
}

async function pickFiles(): Promise<void> {
  if (!hasNativeApi) {
    importError.value = t('importing.filesDesktopOnly')
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFiles(['image'])
    if (result.canceled) return
    reportImportResult(await addFiles(result.files))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : t('importing.pickFilesFailed')
  } finally {
    uploading.value = false
  }
}

async function pickFolder(): Promise<void> {
  if (!hasNativeApi) {
    importError.value = t('importing.folderDesktopOnly')
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFolder(['image'])
    if (result.canceled) return
    if (result.files.length === 0) {
      importError.value = t('importing.noImagesInFolder')
      return
    }
    reportImportResult(await addFiles(result.files))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : t('importing.pickFolderFailed')
  } finally {
    uploading.value = false
  }
}

async function handleFilesDropped(dropped: File[]): Promise<void> {
  if (!hasNativeApi) {
    importError.value = t('importing.dropDesktopOnly')
    return
  }
  uploading.value = true
  try {
    const described = await Promise.all(
      dropped.map((file) => api.statPath(api.getPathForFile(file)))
    )
    reportImportResult(await addFiles(described.filter((d) => d !== null)))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : 'Falha ao importar os arquivos.'
  } finally {
    uploading.value = false
  }
}

// Spec 3.1: "Colar imagem (Ctrl+V) → verifica clipboard → salva temp file → cria Job" —
// only wired while this tab has no active job, matching HomeView's old scope
// (once editing a specific image, Ctrl+V isn't expected to import a new one).
async function handlePaste(event: ClipboardEvent): Promise<void> {
  if (!hasNativeApi || job.value) return
  const item = Array.from(event.clipboardData?.items ?? []).find((i) => i.type.startsWith('image/'))
  if (!item) return
  const blob = item.getAsFile()
  if (!blob) return
  try {
    const buffer = await blob.arrayBuffer()
    const ext = item.type === 'image/jpeg' ? '.jpg' : item.type === 'image/webp' ? '.webp' : '.png'
    const path = await api.saveTempImage(buffer, ext)
    const described = await api.statPath(path)
    if (described) reportImportResult(await addFiles([described]))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : 'Falha ao colar a imagem.'
  }
}

onMounted(() => window.addEventListener('paste', handlePaste))
onUnmounted(() => window.removeEventListener('paste', handlePaste))
</script>

<template>
  <div class="editor-view" data-module="image">
    <TopBar :title="job?.fileName ?? t('actions.noImageSelected')" show-back @back="$emit('back')">
      <template #actions>
        <AppButton variant="outline" @click="importFiles">
          <template #icon><Upload :size="15" /></template>
          {{ t('actions.import') }}
        </AppButton>
        <AppButton variant="outline" :disabled="!configuringJobs.length" @click="processAll">
          <template #icon><Sparkles :size="15" /></template>
          {{ t('actions.processAll') }}
        </AppButton>
      </template>
    </TopBar>

    <div v-if="!job" class="empty-state">
      <div class="empty-state-inner">
        <UploadZone
          class="upload-fill"
          :error="importError"
          :loading="uploading"
          @pick-files="pickFiles"
          @pick-folder="pickFolder"
          @files-dropped="handleFilesDropped"
        />
      </div>
    </div>

    <div v-else class="editor-body">
      <div class="preview-area">
        <div class="preview-canvas" :class="{ panning }" @wheel.prevent="onWheelZoom">
          <div v-if="spaceHeld" class="pan-surface">
            <img
              :src="afterSrc"
              :alt="t('imageEditor.after')"
              class="viewport-img"
              :style="mediaStyle"
              draggable="false"
            />
          </div>
          <div
            v-else-if="job.status !== 'done'"
            class="pan-surface"
            @pointerdown="onPanDown"
            @pointermove="onPanMove"
            @pointerup="onPanUp"
          >
            <!-- crossorigin: o shader le os pixels, e o protocolo de midia e'
                 outra origem (o mesmo do <video> do Video). -->
            <img
              v-show="!previewActive"
              ref="previewSource"
              :src="beforeSrc"
              alt=""
              class="viewport-img"
              :style="mediaStyle"
              crossorigin="anonymous"
              draggable="false"
              @load="previewActive && startPreview()"
            />
            <canvas
              v-show="previewActive"
              ref="previewCanvas"
              class="viewport-img"
              :style="mediaStyle"
            />
          </div>
          <CompareSlider
            v-else-if="viewMode === 'slider'"
            :before-src="beforeSrc"
            :after-src="afterSrc"
            :media-style="mediaStyle"
          />
          <div
            v-else
            class="side-by-side"
            @pointerdown="onPanDown"
            @pointermove="onPanMove"
            @pointerup="onPanUp"
          >
            <div class="side-pane">
              <span class="side-label">{{ t('imageEditor.before') }}</span>
              <img
                :src="beforeSrc"
                :alt="t('imageEditor.before')"
                class="viewport-img"
                :style="mediaStyle"
                draggable="false"
              />
            </div>
            <div class="side-pane">
              <span class="side-label">{{ t('imageEditor.after') }}</span>
              <img
                :src="afterSrc"
                :alt="t('imageEditor.after')"
                class="viewport-img"
                :style="mediaStyle"
                draggable="false"
              />
            </div>
          </div>
        </div>

        <p v-if="job.status === 'done'" class="hold-space-hint">
          {{ t('imageEditor.holdSpace') }}
        </p>

        <div class="preview-footer">
          <div class="zoom-toolbar">
            <div class="zoom-controls">
              <button class="zoom-btn" type="button" @click="zoom = Math.max(10, zoom - 10)">
                <Minus :size="14" />
              </button>
              <span class="zoom-value">{{ zoom }}%</span>
              <button class="zoom-btn" type="button" @click="zoom = Math.min(400, zoom + 10)">
                <Plus :size="14" />
              </button>
            </div>
            <div class="zoom-presets">
              <button
                v-for="level in zoomLevels"
                :key="level"
                class="preset-btn"
                :class="{ active: zoom === level }"
                type="button"
                @click="zoom = level"
              >
                {{ level }}%
              </button>
              <button class="preset-btn" type="button" @click="resetView">
                <Maximize2 :size="12" /> {{ t('imageEditor.fit') }}
              </button>
            </div>
            <div v-if="job.status === 'done'" class="view-mode-toggle">
              <button
                class="mode-btn"
                :class="{ active: viewMode === 'slider' }"
                type="button"
                :title="t('imageEditor.sliderView')"
                @click="viewMode = 'slider'"
              >
                <GalleryHorizontal :size="14" />
              </button>
              <button
                class="mode-btn"
                :class="{ active: viewMode === 'side-by-side' }"
                type="button"
                :title="t('imageEditor.sideBySide')"
                @click="viewMode = 'side-by-side'"
              >
                <Columns2 :size="14" />
              </button>
            </div>
          </div>
        </div>

        <div class="thumb-strip">
          <!-- A wrapper div, not a <button>: the remove control is itself a
               button and nesting buttons is invalid HTML. -->
          <div
            v-for="j in imageJobs"
            :key="j.id"
            class="thumb-card"
            :class="{ active: j.id === job.id }"
          >
            <button class="thumb-select" type="button" @click="setActiveJob(j.id)">
              <img v-if="hasNativeApi" :src="api.toFileUrl(j.sourcePath)" alt="" />
              <div class="thumb-meta">
                <span class="thumb-name">{{ j.fileName }}</span>
                <span class="thumb-dims">{{ j.status }}</span>
              </div>
            </button>
            <button
              class="thumb-remove"
              type="button"
              :title="`Remover ${j.fileName}`"
              :aria-label="`Remover ${j.fileName}`"
              @click="removeJob(j.id)"
            >
              <X :size="12" />
            </button>
          </div>
          <button class="thumb-add" type="button" @click="importFiles">
            <Plus :size="16" />
            <span>Adicionar imagem</span>
          </button>
        </div>
      </div>

      <button class="drawer-trigger" type="button" @click="panelOpen = true">
        <SlidersHorizontal :size="16" /> Ajustes
      </button>

      <div v-if="panelOpen" class="panel-backdrop" @click="panelOpen = false" />

      <aside class="side-panel" :class="{ open: panelOpen }">
        <div class="panel-drawer-header">
          <span>Ajustes</span>
          <AppButton variant="ghost" icon-only @click="panelOpen = false">
            <template #icon><X :size="18" /></template>
          </AppButton>
        </div>

        <p v-if="importError" class="banner-error"><AlertCircle :size="14" /> {{ importError }}</p>

        <!-- ---------------------------- CONFIGURING / ERROR / CANCELLED ---------------------------- -->
        <template
          v-if="
            job.status === 'configuring' || job.status === 'error' || job.status === 'cancelled'
          "
        >
          <div v-if="job.status === 'error'" class="banner-error-block">
            <p class="banner-error">
              <AlertCircle :size="14" />
              <span>
                {{
                  job.errorCategory
                    ? errorCategoryCopy(job.errorCategory, job.errorReason).message
                    : job.errorMessage
                }}
                <template v-if="job.errorCategory">
                  {{ errorCategoryCopy(job.errorCategory, job.errorReason).action }}</template
                >
              </span>
            </p>
            <TechnicalDetails
              v-if="job.errorCategory && job.errorMessage"
              :summary="t('imageEditor.technicalDetails')"
              :text="job.errorDetail || job.errorMessage"
            />
          </div>
          <p v-if="job.status === 'cancelled'" class="banner-info">
            <XCircle :size="14" /> {{ t('imageEditor.cancelled') }}
          </p>

          <!-- One panel, not three: each of these is a single select, and split
               across three collapsibles they cost more header than content. They
               also share a condition — all three only choose or tune a model
               pass, and Original mode resolves no model (it travels as scale
               '1x'), so none of them applies there. Ajustes below stays separate:
               its filters run in both modes. -->
          <CollapsiblePanel
            :title="t('imageEditor.processingTitle')"
            :description="t('imageEditor.processingDescription')"
            :icon="Cpu"
          >
            <div class="field">
              <label class="field-label">{{ t('imageEditor.detectedContent') }}</label>
              <AppSelect
                :model-value="job.scaleConfig.contentType"
                :options="contentTypeOptions"
                :placeholder="t('imageEditor.detecting')"
                @update:model-value="(v) => (job!.scaleConfig.contentType = v as ContentType)"
              />
            </div>

            <!-- Esforço e dispositivo descrevem COMO o modelo roda, e sem
                 modelo não descrevem nada. O tipo de conteúdo continua aqui: é
                 por ele que se sai de "Sem modelo", e escondê-lo junto deixava
                 a escolha sem volta. -->
            <div v-if="usesModel" class="field">
              <label class="field-label">{{ t('imageEditor.effort') }}</label>
              <AppSelect
                :model-value="job.scaleConfig.profile"
                :options="profiles"
                @update:model-value="(v) => (job!.scaleConfig.profile = v as Profile)"
              />
            </div>

            <div v-if="usesModel" class="field">
              <label class="field-label">{{ t('imageEditor.whereToProcess') }}</label>
              <AppSelect
                :model-value="job.scaleConfig.device"
                :options="devices"
                @update:model-value="(v) => (job!.scaleConfig.device = String(v))"
              />
            </div>

            <!-- Aqui, e nao em Ajustes: e' um modelo (GFPGAN), nao um filtro. -->
            <div class="toggle-row">
              <label class="field-label">{{ t('imageEditor.faceRecoveryLabel') }}</label>
              <button
                class="switch"
                :class="{ on: job.scaleConfig.faceRecovery }"
                type="button"
                @click="job.scaleConfig.faceRecovery = !job.scaleConfig.faceRecovery"
              >
                <span class="knob" />
              </button>
            </div>
            <div v-if="job.scaleConfig.faceRecovery" class="slider-field">
              <div class="slider-head">
                <label class="field-label">{{ t('videoEditor.edits.strength') }}</label>
                <span class="slider-value">{{ job.scaleConfig.faceRecoveryStrength }}</span>
              </div>
              <RangeSlider v-model="job.scaleConfig.faceRecoveryStrength" :default-value="80" />
              <p class="field-hint">
                {{ t('imageEditor.faceRecoveryHint') }}
              </p>
            </div>
          </CollapsiblePanel>

          <CollapsiblePanel
            :title="t('imageEditor.scaleTitle')"
            :description="t('imageEditor.scaleDescription')"
            :icon="Expand"
          >
            <ModeTabs
              :model-value="job.scaleConfig.mode"
              :options="scaleModeOptions"
              @update:model-value="switchScaleMode(job!, $event as ScaleMode)"
            />

            <div v-if="job.scaleConfig.mode === 'preset'" class="scale-buttons">
              <button
                v-for="s in [2, 4]"
                :key="s"
                class="scale-btn"
                :class="{ active: job.scaleConfig.presetFactor === s }"
                type="button"
                @click="setPresetFactor(job, s as 2 | 4)"
              >
                {{ s }}x
              </button>
            </div>

            <div v-else class="field">
              <div class="field-label-row">
                <label class="field-label">{{ t('imageEditor.sizeLabel') }}</label>
                <button
                  class="link-btn"
                  type="button"
                  :aria-pressed="job.scaleConfig.lockAspectRatio"
                  :title="
                    job.scaleConfig.lockAspectRatio
                      ? t('imageEditor.aspectLocked')
                      : t('imageEditor.aspectFree')
                  "
                  @click="toggleAspectLock(job)"
                >
                  <component :is="job.scaleConfig.lockAspectRatio ? Link : Unlink" :size="13" />
                  {{
                    job.scaleConfig.lockAspectRatio
                      ? t('imageEditor.locked')
                      : t('imageEditor.free')
                  }}
                </button>
              </div>
              <div class="steppers-row">
                <NumberStepper
                  :label="t('imageEditor.width')"
                  :model-value="job.scaleConfig.customWidth ?? job.sourceMeta.width ?? 0"
                  :min="MIN_DIMENSION"
                  :max="MAX_OUTPUT_DIMENSION"
                  @update:model-value="(v) => onCustomWidthInput(job!, String(v))"
                />
                <NumberStepper
                  :label="t('imageEditor.height')"
                  :model-value="job.scaleConfig.customHeight ?? job.sourceMeta.height ?? 0"
                  :min="MIN_DIMENSION"
                  :max="MAX_OUTPUT_DIMENSION"
                  @update:model-value="(v) => onCustomHeightInput(job!, String(v))"
                />
              </div>
              <div v-if="customFactor" class="scale-multiplier">
                <span class="scale-multiplier-label">{{
                  t('imageEditor.resolutionMultiplier')
                }}</span>
                <span class="scale-multiplier-value">{{ customFactor.toFixed(1) }}×</span>
              </div>
              <p v-if="!job.scaleConfig.lockAspectRatio" class="field-warning">
                {{ t('imageEditor.willDistort') }}
              </p>
              <p v-if="customBeyondNative" class="field-warning">
                {{ t('imageEditor.beyondNative', { factor: job.scaleConfig.presetFactor }) }}
              </p>
            </div>

            <ImageInfoPanel
              :original-width="job.sourceMeta.width"
              :original-height="job.sourceMeta.height"
              :new-width="estimate?.width ?? null"
              :new-height="estimate?.height ?? null"
              :estimated-bytes="estimateBytes"
            />
            <p v-if="!validity.valid" class="field-warning">{{ validity.reason }}</p>
          </CollapsiblePanel>

          <!-- Shown in every mode, unlike the three above: these filters are real
               OpenCV post-processing, and in Original mode they ARE the
               processing. See Upscaler.process_without_model(). -->
          <VideoAdjustmentsPanel
            :adjustments="job.edits.adjustments"
            :effects="job.edits.effects"
            :shows-disclosure="editsNeedDisclosure"
            :disclosure-text="t('imageEditor.notInLivePreview')"
            @reset-adjustments="resetAdjustments"
            @reset-effects="resetEffects"
            @update-adjustment="setAdjustment"
            @update-effect="setEffect"
          />

          <VideoTransformPanel
            image
            :transform="job.edits.transform"
            :trim="null"
            :source-width="job.sourceMeta.width"
            :source-height="job.sourceMeta.height"
            :format-time="() => ''"
            @update-transform="setTransform"
          />

          <CollapsiblePanel
            :title="t('imageEditor.exportTitle')"
            :description="t('imageEditor.exportDescription')"
            :icon="FileOutput"
          >
            <div class="field">
              <label class="field-label">{{ t('imageEditor.format') }}</label>
              <AppSelect
                :model-value="exportacao.format"
                :options="exportFormatOptions"
                :disabled="noExportFormatAvailable"
                @update:model-value="(v) => (exportacao.format = v as ImageExport['format'])"
              />
            </div>

            <!-- No momento em que ajuda: antes de escolher, não depois de
                 falhar. Mesmo desenho do painel de vídeo. -->
            <p v-if="noExportFormatAvailable" class="banner-error">
              <AlertCircle :size="14" /> {{ t('imageEditor.noFormatAvailable') }}
            </p>

            <div v-if="exportIsLossy" class="field">
              <label class="field-label">{{ t('imageEditor.quality') }}</label>
              <AppSelect
                :model-value="exportacao.profile"
                :options="qualityProfileOptions"
                @update:model-value="(v) => (exportacao.profile = v as Profile)"
              />
            </div>

            <div class="field">
              <label class="field-label">{{ t('imageEditor.destinationFolder') }}</label>
              <div class="folder-row">
                <input
                  class="select folder-input"
                  type="text"
                  :value="exportacao.directory ?? t('imageEditor.sameAsSource')"
                  readonly
                />
                <AppButton variant="secondary" icon-only @click="pickExportFolder">
                  <template #icon><FolderOpen :size="15" /></template>
                </AppButton>
              </div>
            </div>

            <div class="field">
              <label class="field-label">{{ t('imageEditor.fileName') }}</label>
              <input
                class="select"
                type="text"
                :placeholder="job.fileName.replace(/\.[^.]+$/, '')"
                :value="exportFilename ?? ''"
                @input="exportFilename = ($event.target as HTMLInputElement).value.trim() || null"
              />
            </div>

            <div class="field">
              <label class="field-label">{{ t('imageEditor.onConflict') }}</label>
              <AppSelect
                :model-value="exportacao.conflict"
                :options="conflictOptions"
                @update:model-value="(v) => (exportacao.conflict = v as ImageExport['conflict'])"
              />
            </div>
          </CollapsiblePanel>

          <AppButton
            variant="secondary"
            class="w-full"
            :disabled="configuringJobs.length < 2"
            @click="applyConfigToAll(job)"
          >
            {{ t('imageEditor.applyToAll', { n: configuringJobs.length }) }}
          </AppButton>

          <AppButton
            variant="primary"
            size="lg"
            class="w-full"
            :disabled="!validity.valid || noExportFormatAvailable"
            @click="process(job)"
          >
            {{
              job.status === 'error' || job.status === 'cancelled'
                ? t('imageEditor.retry')
                : t('imageEditor.process')
            }}
          </AppButton>
        </template>

        <!-- ---------------------------- QUEUED / PROCESSING ---------------------------- -->
        <template v-else-if="job.status === 'queued' || job.status === 'processing'">
          <div class="processing-panel">
            <AppSpinner :size="28" />
            <p v-if="job.status === 'queued'" class="processing-label">
              {{
                job.queuePosition
                  ? t('imageEditor.queuedAt', { position: job.queuePosition })
                  : t('imageEditor.queued')
              }}
            </p>
            <p v-else class="processing-label">
              {{ t('imageEditor.processingProgress', { progress: job.progress }) }}
            </p>
            <p v-if="job.stage" class="processing-stage">{{ job.stage }}</p>
            <p v-if="elapsedLabel" class="processing-stage">
              {{ t('imageEditor.elapsed', { time: elapsedLabel }) }}
            </p>
            <ProgressBar :value="job.status === 'queued' ? 0 : job.progress" />
            <AppButton variant="outline" class="mt-2 text-state-danger" @click="cancel(job)">
              {{ t('imageEditor.cancel') }}
            </AppButton>
          </div>
        </template>

        <!-- ---------------------------- DONE ---------------------------- -->
        <template v-else-if="job.status === 'done'">
          <CollapsiblePanel
            :title="t('imageEditor.resultTitle')"
            :description="t('imageEditor.resultDescription')"
            :icon="ChartNoAxesColumn"
          >
            <ComparisonStats :job="job" />
          </CollapsiblePanel>

          <SavedResultCard v-if="job.outputPath" :path="job.outputPath" />
          <AppButton variant="ghost" class="w-full" @click="reprocess(job)">
            <template #icon><RotateCcw :size="14" /></template>
            {{ t('imageEditor.adjustAndReprocess') }}
          </AppButton>
        </template>
      </aside>
    </div>

    <ConflictDialog :caminho="pergunta.caminho.value" @responder="pergunta.responder" />
  </div>
</template>

<style scoped>
.editor-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

/* The drop zone fills the whole editor area instead of sitting as a narrow
   centered card — a bigger target is easier to drop onto, and it matches the
   Otimizar screen. UploadZone centers its own contents vertically, so no
   centering is needed here. */
.empty-state {
  flex: 1;
  display: flex;
  min-height: 0;
  color: var(--text-tertiary);
  font-size: var(--fs-label);
  padding: var(--space-4);
  text-align: center;
}

.empty-state-inner {
  flex: 1;
  display: flex;
  /* Column so the drop zone stretches to the full width (align-items defaults
     to stretch); `.upload-fill` below then gives it the full height too. */
  flex-direction: column;
  min-height: 0;
}

.upload-fill {
  flex: 1;
  min-height: 0;
}

.editor-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.preview-area {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
  gap: var(--space-3);
  min-width: 0;
}

.zoom-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-full);
  padding: 4px 6px;
}

.zoom-btn {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-1);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.zoom-btn:hover {
  background: var(--surface-3);
  color: var(--text-primary);
}

.zoom-value {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  min-width: 42px;
  text-align: center;
}

.view-mode-toggle {
  display: flex;
  gap: 4px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-full);
  padding: 4px;
}

.mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-1);
  color: var(--text-secondary);
  cursor: pointer;
}

.mode-btn.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.preview-canvas {
  flex: 1;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: radial-gradient(circle at 50% 20%, var(--surface-2), var(--surface-0));
  position: relative;
}

.preview-canvas.panning {
  cursor: grabbing;
}

.pan-surface {
  width: 100%;
  height: 100%;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
}

.pan-surface:active {
  cursor: grabbing;
}

.viewport-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  user-select: none;
}

.side-by-side {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 2px;
}

.side-pane {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--surface-1);
}

.side-pane img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.side-label {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  font-size: 11px;
  font-weight: var(--fw-semibold);
  color: #fff;
  background: rgba(11, 14, 20, 0.72);
  padding: 3px 8px;
  border-radius: var(--radius-full);
}

.hold-space-hint {
  text-align: center;
  font-size: 11px;
  color: var(--text-tertiary);
}

.preview-footer {
  display: flex;
  justify-content: center;
}

.zoom-presets {
  display: flex;
  gap: 4px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-full);
  padding: 4px;
}

.preset-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: var(--fw-medium);
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  white-space: nowrap;
}

.preset-btn.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.thumb-strip {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
}

.thumb-card {
  position: relative;
  width: 92px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 2px solid var(--surface-border);
  background: var(--surface-2);
}

/* Fills the card so the whole thumbnail stays one big click target for
   selecting; the remove control sits on top of it in the corner. */
.thumb-select {
  display: block;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
}

.thumb-remove {
  position: absolute;
  top: 3px;
  right: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: var(--radius-sm);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity var(--transition-fast),
    background var(--transition-fast);
}

/* Revealed on hover/focus so the strip stays clean, but never hidden from
   keyboard users (:focus-visible) or on touch, where hover never fires. */
.thumb-card:hover .thumb-remove,
.thumb-remove:focus-visible {
  opacity: 1;
}

@media (hover: none) {
  .thumb-remove {
    opacity: 1;
  }
}

.thumb-remove:hover {
  background: var(--color-danger);
}

.thumb-card.active {
  border-color: var(--color-primary);
}

.thumb-card img {
  width: 100%;
  height: 60px;
  object-fit: cover;
  display: block;
}

.thumb-meta {
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
}

.thumb-name {
  font-size: 10px;
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumb-dims {
  font-size: 9px;
  color: var(--text-tertiary);
  text-transform: capitalize;
}

.thumb-add {
  width: 92px;
  flex-shrink: 0;
  /* No fixed height: the tile stretches to whatever the file cards beside it
     end up being, instead of guessing 88px and standing shorter than them. */
  align-self: stretch;
  border: 1px dashed var(--surface-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 9px;
  cursor: pointer;
}

.thumb-add:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.side-panel {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid var(--surface-border-soft);
  background: var(--surface-0);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  overflow-y: auto;
}

/* flex-shrink:0 for CollapsiblePanel instances lives in CollapsiblePanel.vue itself
   (not here as ".side-panel > *") — Vue's scoped CSS doesn't attach this component's
   scope attribute to a bare "*" combinator, so that selector would tie in specificity
   with (and can lose to) any width/flex rule the child sets on its own root, by
   source order. Native elements below (p/button/div) are tagged with this component's
   own scope attribute directly, so they don't need the same treatment. */
.banner-error,
.banner-error-block,
.banner-info,
.processing-panel,
.panel-drawer-header {
  flex-shrink: 0;
}

.banner-error {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  font-size: var(--fs-caption);
  color: var(--color-danger);
  min-width: 0;
}

.banner-error span,
.banner-error-block {
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
}

.banner-error-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.banner-info {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.field-label {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
}

.badge {
  font-size: 9px;
  font-weight: var(--fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
  background: var(--surface-3);
  padding: 1px 6px;
  border-radius: var(--radius-full);
}

.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-hint {
  /* Pulled up against the control it explains: with the panel's own 16px gap it
     floated equidistant between the two, belonging to neither. */
  margin-top: calc(var(--space-2) * -1);
  font-size: 11px;
  line-height: 1.35;
  color: var(--text-tertiary);
}

.model-option {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0;
}

.model-option-line1 {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.model-option-label {
  overflow-wrap: break-word;
  word-break: break-word;
  white-space: normal;
}

.model-option-org {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow-wrap: break-word;
  word-break: break-word;
}

.model-summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
}

.model-summary-desc {
  font-size: var(--fs-caption);
  color: var(--text-primary);
  line-height: 1.4;
  overflow-wrap: break-word;
}

.model-summary-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.model-summary-org {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scale-multiplier {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  padding: 8px var(--space-3);
}

.scale-multiplier-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.scale-multiplier-value {
  font-size: 18px;
  font-weight: var(--fw-semibold);
  color: var(--color-primary);
  font-family: var(--font-mono);
}

.field-warning {
  font-size: 11px;
  color: var(--color-warning);
}

.field-note {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.device-hint {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  margin-top: 6px;
}

.select {
  width: 100%;
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: var(--fs-label);
}

.scale-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

.scale-btn {
  padding: 8px 0;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.scale-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--on-primary);
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  padding: 3px 10px;
  font-size: 11px;
  font-weight: var(--fw-medium);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.link-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.link-btn[aria-pressed='true'] {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.link-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.steppers-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.slider-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.slider-field.disabled {
  opacity: 0.55;
}

.slider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.slider-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.switch {
  width: 34px;
  height: 20px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--surface-3);
  position: relative;
  cursor: pointer;
}

.switch:disabled {
  cursor: not-allowed;
}

.switch.on {
  background: var(--color-primary);
}

.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-sm);
  background: #fff;
  transition: transform var(--transition-fast);
}

.switch.on .knob {
  transform: translateX(14px);
}

/* Rounded rectangle, not a pill: this row wraps to a second line, and a
   full-radius container reads as a broken capsule the moment it does. */

.folder-row {
  display: flex;
  gap: var(--space-2);
}

.folder-input {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.processing-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
  text-align: center;
}

.processing-label {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.processing-stage {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

@media (max-width: 1000px) {
  .side-panel {
    width: 280px;
  }
}

.drawer-trigger {
  display: none;
}

.panel-backdrop {
  display: none;
}

.panel-drawer-header {
  display: none;
}

@media (max-width: 900px) {
  .drawer-trigger {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
    position: absolute;
    bottom: var(--space-3);
    right: var(--space-3);
    z-index: 3;
    background: var(--color-primary);
    color: var(--on-primary);
    border: none;
    border-radius: var(--radius-full);
    padding: 10px 16px;
    font-size: var(--fs-label);
    font-weight: var(--fw-semibold);
    box-shadow: var(--shadow-md);
    cursor: pointer;
  }

  .panel-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 9;
  }

  .side-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 320px;
    max-width: 88vw;
    border-left: 1px solid var(--surface-border);
    box-shadow: var(--shadow-md);
    transform: translateX(100%);
    transition: transform 220ms ease;
    z-index: 10;
  }

  .side-panel.open {
    transform: translateX(0);
  }

  .panel-drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: var(--fs-label);
    font-weight: var(--fw-semibold);
    color: var(--text-primary);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--surface-border-soft);
    margin-bottom: var(--space-1);
  }
}
</style>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import RangeSlider from '../components/RangeSlider.vue'
import CompareSlider from '../components/CompareSlider.vue'
import ComparisonStats from '../components/ComparisonStats.vue'
import BatchExportModal from '../components/BatchExportModal.vue'
import AppSelect from '../components/AppSelect.vue'
import TechnicalDetails from '../components/TechnicalDetails.vue'
import ResolutionStepper from '../components/ResolutionStepper.vue'
import ImageInfoPanel from '../components/ImageInfoPanel.vue'
import {
  Minus,
  Plus,
  Maximize2,
  Cpu,
  MonitorCog,
  Expand,
  ChartNoAxesColumn,
  Link,
  Unlink,
  Upload,
  Download,
  FolderOpen,
  Loader2,
  SlidersHorizontal,
  X,
  AlertCircle,
  XCircle,
  Columns2,
  GalleryHorizontal,
  RotateCcw
} from '@lucide/vue'
import { api, hasNativeApi } from '../api'
import { settingsState } from '../store/settings'
import { previewDenoise, type ContentType, type DenoisePreview, type Profile } from '../backend'
import { ERROR_CATEGORY_COPY } from '../backend'
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
  startProcessing,
  cancelProcessing,
  exportOne,
  type Job
} from '../store/jobs'

defineEmits<{
  back: []
}>()

const panelOpen = ref(false)
const showBatchModal = ref(false)

// ------------------------------- selected job ------------------------------- //
const job = computed<Job | undefined>(() => getActiveJob())
const imageJobs = computed(() => queueState.jobs)
const doneJobs = computed(() => queueState.jobs.filter((j) => j.status === 'done'))
const configuringJobs = computed(() => queueState.jobs.filter((j) => j.status === 'configuring'))

// ------------------------------- preview viewport (zoom + pan) ------------------------------- //
const zoom = ref(100)
const pan = ref({ x: 0, y: 0 })
const zoomLevels = [25, 50, 100, 200]
const viewMode = ref<'slider' | 'side-by-side'>('slider')
const spaceHeld = ref(false)

// Single viewportState shared by every preview mode (spec 6.2) — applied to the
// images via CSS transform, so slider divider/labels stay unscaled.
const mediaStyle = computed(() => ({
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value / 100})`,
  transformOrigin: 'center center'
}))

function resetView(): void {
  zoom.value = 100
  pan.value = { x: 0, y: 0 }
}

function onWheelZoom(e: WheelEvent): void {
  zoom.value = Math.min(400, Math.max(10, zoom.value - Math.sign(e.deltaY) * 10))
}

const panning = ref(false)
let panOrigin = { x: 0, y: 0, panX: 0, panY: 0 }

function onPanDown(e: PointerEvent): void {
  panning.value = true
  panOrigin = { x: e.clientX, y: e.clientY, panX: pan.value.x, panY: pan.value.y }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function onPanMove(e: PointerEvent): void {
  if (!panning.value) return
  pan.value = {
    x: panOrigin.panX + (e.clientX - panOrigin.x),
    y: panOrigin.panY + (e.clientY - panOrigin.y)
  }
}
function onPanUp(): void {
  panning.value = false
}

const beforeSrc = computed(() =>
  job.value && hasNativeApi ? api.toFileUrl(job.value.sourcePath) : ''
)
const afterSrc = computed(() => {
  if (!job.value || !hasNativeApi || job.value.status !== 'done' || !job.value.lastExportPath)
    return beforeSrc.value
  return api.toFileUrl(job.value.lastExportPath)
})

function onKeyDown(e: KeyboardEvent): void {
  if (e.code === 'Space' && job.value?.status === 'done') {
    e.preventDefault()
    spaceHeld.value = true
  }
}
function onKeyUp(e: KeyboardEvent): void {
  if (e.code === 'Space') spaceHeld.value = false
}

// ------------------------------- content type + profile ------------------------------- //
// FR-009/FR-063: never a model name — only what the backend actually accepts as
// intent (profile_resolver.py resolves the implementation internally). The
// content-type indicator is auto-detected on file add (store/jobs.ts addFiles())
// but stays editable here — FR-096, and this editor only handles images, so the
// only two valid content types are photo <-> anime_image.
const devices = ref<string[]>(['auto', 'cpu', 'cuda'])
const importError = ref<string | null>(null)

const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string; description: string }[] = [
  { value: 'photo', label: 'Foto', description: 'Fotografias reais — retratos, paisagens, produtos' },
  { value: 'anime_image', label: 'Anime/Ilustração', description: 'Arte digital, anime, ilustração com traços definidos' }
]
const contentTypeOptions = computed(() =>
  CONTENT_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label, description: o.description }))
)

const PROFILE_OPTIONS: { value: Profile; label: string; description: string }[] = [
  { value: 'fast', label: 'Rápido', description: 'Prioriza velocidade' },
  { value: 'balanced', label: 'Equilibrado', description: 'Equilíbrio entre velocidade e qualidade' },
  { value: 'quality', label: 'Qualidade', description: 'Prioriza o melhor resultado' }
]
const profileOptions = computed(() =>
  PROFILE_OPTIONS.map((o) => ({ value: o.value, label: o.label, description: o.description }))
)

const deviceOptions = computed(() =>
  devices.value.map((d) => ({ value: d, label: deviceLabels[d] ?? d }))
)
const exportFormatOptions = [
  { value: 'png', label: '.png' },
  { value: 'jpg', label: '.jpg' },
  { value: 'webp', label: '.webp' }
]
const conflictOptions = [
  { value: 'rename', label: 'Renomear automaticamente' },
  { value: 'overwrite', label: 'Sobrescrever' },
  { value: 'ask', label: 'Perguntar' }
]

// Reset the viewport whenever the user switches to another image.
watch(
  () => job.value?.id,
  () => resetView()
)

const deviceLabels: Record<string, string> = {
  auto: 'Automático',
  cpu: 'CPU',
  cuda: 'GPU (CUDA)',
  mps: 'GPU (Apple/MPS)'
}

const deviceDescriptions: Record<string, string> = {
  auto: 'Usa a GPU quando disponível e volta para a CPU automaticamente caso contrário.',
  cpu: 'Processa apenas no processador — mais lento, funciona em qualquer máquina.',
  cuda: 'Força o uso da GPU NVIDIA (CUDA) — mais rápido, requer driver compatível.',
  mps: 'Força o uso da GPU da Apple via Metal — mais rápido em Macs com chip Apple Silicon.'
}

const selectedDeviceDescription = computed(() => {
  const device = job.value?.scaleConfig.device ?? 'auto'
  return deviceDescriptions[device] ?? deviceDescriptions.auto
})

// ------------------------------- denoise filter (real OpenCV, independent of the model) ------------------------------- //
const DENOISE_PRESETS: {
  key: 'low' | 'medium' | 'high' | 'custom'
  label: string
  strength: number | null
}[] = [
  { key: 'low', label: 'Baixo', strength: 20 },
  { key: 'medium', label: 'Médio', strength: 45 },
  { key: 'high', label: 'Alto', strength: 75 },
  { key: 'custom', label: 'Personalizado', strength: null }
]
// A ref, not inferred from the numeric value — a custom value can legitimately
// coincide with a preset's number, and that shouldn't silently reassign it back
// to that preset (or hide the "Personalizado" slider the user just opened).
const denoiseActivePresetKey = ref<'low' | 'medium' | 'high' | 'custom'>('medium')
const denoisePreview = ref<DenoisePreview | null>(null)
const denoisePreviewLoading = ref(false)
const denoisePreviewError = ref<string | null>(null)
let denoisePreviewTimer: ReturnType<typeof setTimeout> | undefined
let denoisePreviewRequestId = 0

function requestDenoisePreview(): void {
  const j = job.value
  if (!j || !j.scaleConfig.denoiseFilterEnabled || !hasNativeApi) return
  clearTimeout(denoisePreviewTimer)
  denoisePreviewTimer = setTimeout(async () => {
    const requestId = ++denoisePreviewRequestId
    denoisePreviewLoading.value = true
    denoisePreviewError.value = null
    try {
      const result = await previewDenoise(j.sourcePath, j.scaleConfig.denoiseFilterStrength)
      if (requestId === denoisePreviewRequestId) denoisePreview.value = result
    } catch (error) {
      if (requestId === denoisePreviewRequestId) {
        denoisePreviewError.value =
          error instanceof Error ? error.message : 'Falha ao gerar prévia.'
      }
    } finally {
      if (requestId === denoisePreviewRequestId) denoisePreviewLoading.value = false
    }
  }, 350)
}

function setDenoisePreset(preset: {
  key: 'low' | 'medium' | 'high' | 'custom'
  strength: number | null
}): void {
  if (!job.value) return
  denoiseActivePresetKey.value = preset.key
  if (preset.strength !== null) job.value.scaleConfig.denoiseFilterStrength = preset.strength
  requestDenoisePreview()
}

function toggleDenoiseFilter(): void {
  if (!job.value) return
  job.value.scaleConfig.denoiseFilterEnabled = !job.value.scaleConfig.denoiseFilterEnabled
  denoisePreview.value = null
  if (job.value.scaleConfig.denoiseFilterEnabled) {
    const matched = DENOISE_PRESETS.find(
      (p) => p.strength === job.value!.scaleConfig.denoiseFilterStrength
    )
    denoiseActivePresetKey.value = matched?.key ?? 'custom'
    requestDenoisePreview()
  }
}

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
function switchScaleMode(j: Job, mode: 'preset' | 'custom'): void {
  j.scaleConfig.mode = mode
  if (mode === 'custom') ensureCustomSizeDefaults(j)
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
  return factor > j.scaleConfig.presetFactor + 0.01
})

async function process(j: Job): Promise<void> {
  await startProcessing(j)
}

async function processAll(): Promise<void> {
  for (const j of configuringJobs.value) {
    const v = validateScaleConfig(j)
    if (v.valid) void startProcessing(j)
  }
}

async function cancel(j: Job): Promise<void> {
  await cancelProcessing(j)
}

// ------------------------------- export (single job, post-done) ------------------------------- //
const exportFormat = ref<'png' | 'jpg' | 'webp'>(settingsState.defaultExportFormat)
const exportQuality = ref(settingsState.defaultQuality)
const exportDestFolder = ref<string | null>(settingsState.defaultOutputFolder)
const exportFilename = ref<string | null>(null)
const exportConflict = ref<'overwrite' | 'rename' | 'ask'>('rename')
const conflictPrompt = ref<{ job: Job } | null>(null)

async function runExport(j: Job): Promise<void> {
  const result = await exportOne(j, {
    format: exportFormat.value,
    quality: exportQuality.value,
    outputDir: exportDestFolder.value,
    filename: exportFilename.value,
    conflict: exportConflict.value
  })
  if (
    !result.ok &&
    j.exportError === 'Já existe um arquivo com esse nome no destino.' &&
    exportConflict.value === 'ask'
  ) {
    conflictPrompt.value = { job: j }
  }
}

async function resolveConflict(mode: 'overwrite' | 'rename'): Promise<void> {
  if (!conflictPrompt.value) return
  const j = conflictPrompt.value.job
  conflictPrompt.value = null
  await exportOne(j, {
    format: exportFormat.value,
    quality: exportQuality.value,
    outputDir: exportDestFolder.value,
    filename: exportFilename.value,
    conflict: mode
  })
}

async function pickExportFolder(): Promise<void> {
  if (!hasNativeApi) return
  const folder = await api.selectOutputFolder(exportDestFolder.value ?? undefined)
  if (folder) exportDestFolder.value = folder
}

// ------------------------------- import / queue ------------------------------- //
async function importFiles(): Promise<void> {
  if (!hasNativeApi) return
  const result = await api.selectFiles()
  if (result.canceled) return
  importError.value = result.rejected.length
    ? `${result.rejected.length} arquivo(s) não puderam ser importados (formato não suportado ou ilegível).`
    : null
  const upload = await addFiles(result.files)
  if (!job.value && upload.added[0]) setActiveJob(upload.added[0].id)
}

// Empty-state upload — same intake as the old HomeView drop zone (pick/drop/
// folder/paste all land in the same store/jobs.ts queue), now local to this
// tab instead of requiring a detour through Home first.
const uploading = ref(false)

function reportImportResult(result: { added: { id: string }[]; rejected: { name: string; reason: string }[]; duplicates: string[] }): void {
  if (result.rejected.length) {
    importError.value = result.rejected.map((r) => `${r.name}: ${r.reason}`).join(' · ')
  } else if (!result.added.length && result.duplicates.length) {
    importError.value = `Este(s) arquivo(s) já está(ão) na fila: ${result.duplicates.join(', ')}.`
  } else {
    importError.value = null
  }
  if (result.added.length) setActiveJob(result.added[0].id)
}

async function pickFiles(): Promise<void> {
  if (!hasNativeApi) {
    importError.value = 'Seleção de arquivos disponível apenas no aplicativo desktop.'
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFiles()
    if (result.canceled) return
    reportImportResult(await addFiles(result.files))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : 'Falha ao selecionar arquivos.'
  } finally {
    uploading.value = false
  }
}

async function pickFolder(): Promise<void> {
  if (!hasNativeApi) {
    importError.value = 'Seleção de pasta disponível apenas no aplicativo desktop.'
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFolder()
    if (result.canceled) return
    if (result.files.length === 0) {
      importError.value = 'Nenhuma imagem compatível foi encontrada nessa pasta.'
      return
    }
    reportImportResult(await addFiles(result.files))
  } catch (error) {
    importError.value = error instanceof Error ? error.message : 'Falha ao selecionar a pasta.'
  } finally {
    uploading.value = false
  }
}

async function handleFilesDropped(dropped: File[]): Promise<void> {
  if (!hasNativeApi) {
    importError.value = 'Arraste e solte disponível apenas no aplicativo desktop.'
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
  <div class="editor-view">
    <TopBar :title="job?.fileName ?? 'Nenhuma imagem selecionada'" show-back @back="$emit('back')">
      <template #actions>
        <button class="btn-outline" type="button" @click="importFiles">
          <Upload :size="15" /> Importar
        </button>
        <button
          class="btn-outline"
          type="button"
          :disabled="!configuringJobs.length"
          @click="processAll"
        >
          Processar todos
        </button>
        <button
          class="btn-outline"
          type="button"
          :disabled="!doneJobs.length"
          @click="showBatchModal = true"
        >
          <Download :size="15" /> Exportar tudo
        </button>
      </template>
    </TopBar>

    <div v-if="!job" class="empty-state">
      <div class="empty-state-inner">
        <UploadZone
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
              alt="Depois"
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
            <img
              :src="beforeSrc"
              alt=""
              class="viewport-img"
              :style="mediaStyle"
              draggable="false"
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
              <span class="side-label">Antes</span>
              <img
                :src="beforeSrc"
                alt="Antes"
                class="viewport-img"
                :style="mediaStyle"
                draggable="false"
              />
            </div>
            <div class="side-pane">
              <span class="side-label">Depois</span>
              <img
                :src="afterSrc"
                alt="Depois"
                class="viewport-img"
                :style="mediaStyle"
                draggable="false"
              />
            </div>
          </div>
        </div>

        <p v-if="job.status === 'done'" class="hold-space-hint">
          Segure Espaço para alternar rapidamente antes/depois
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
                <Maximize2 :size="12" /> Ajustar
              </button>
            </div>
            <div v-if="job.status === 'done'" class="view-mode-toggle">
              <button
                class="mode-btn"
                :class="{ active: viewMode === 'slider' }"
                type="button"
                title="Slider antes/depois"
                @click="viewMode = 'slider'"
              >
                <GalleryHorizontal :size="14" />
              </button>
              <button
                class="mode-btn"
                :class="{ active: viewMode === 'side-by-side' }"
                type="button"
                title="Lado a lado"
                @click="viewMode = 'side-by-side'"
              >
                <Columns2 :size="14" />
              </button>
            </div>
          </div>
        </div>

        <div class="thumb-strip">
          <button
            v-for="j in imageJobs"
            :key="j.id"
            class="thumb-card"
            :class="{ active: j.id === job.id }"
            type="button"
            @click="setActiveJob(j.id)"
          >
            <img v-if="hasNativeApi" :src="api.toFileUrl(j.sourcePath)" alt="" />
            <div class="thumb-meta">
              <span class="thumb-name">{{ j.fileName }}</span>
              <span class="thumb-dims">{{ j.status }}</span>
            </div>
          </button>
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
          <button class="drawer-close" type="button" @click="panelOpen = false">
            <X :size="18" />
          </button>
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
                    ? ERROR_CATEGORY_COPY[job.errorCategory].message
                    : job.errorMessage
                }}
                <template v-if="job.errorCategory">
                  {{ ERROR_CATEGORY_COPY[job.errorCategory].action }}</template
                >
              </span>
            </p>
            <TechnicalDetails
              v-if="job.errorCategory && job.errorMessage"
              summary="Detalhes técnicos"
              :text="job.errorMessage"
            />
          </div>
          <p v-if="job.status === 'cancelled'" class="banner-info">
            <XCircle :size="14" /> Processamento cancelado.
          </p>

          <CollapsiblePanel
            title="Tipo de conteúdo"
            description="Detectado automaticamente — corrija se estiver errado"
            :icon="Cpu"
          >
            <div class="field">
              <AppSelect
                :model-value="job.scaleConfig.contentType"
                :options="contentTypeOptions"
                placeholder="Detectando…"
                @update:model-value="(v) => (job!.scaleConfig.contentType = v as ContentType)"
              />
            </div>
          </CollapsiblePanel>

          <CollapsiblePanel
            title="Perfil"
            description="Rápido, Equilibrado ou Qualidade — nunca troca o que processa a imagem, só o quanto se esforça"
            :icon="ChartNoAxesColumn"
          >
            <div class="field">
              <AppSelect
                :model-value="job.scaleConfig.profile"
                :options="profileOptions"
                @update:model-value="(v) => (job!.scaleConfig.profile = v as Profile)"
              />
            </div>
          </CollapsiblePanel>

          <CollapsiblePanel
            title="Dispositivo de processamento"
            description="Onde o modelo roda — GPU acelera, CPU é o padrão de compatibilidade"
            :icon="MonitorCog"
          >
            <div class="field">
              <AppSelect
                :model-value="job.scaleConfig.device"
                :options="deviceOptions"
                @update:model-value="(v) => (job!.scaleConfig.device = String(v))"
              />
              <p class="device-hint">{{ selectedDeviceDescription }}</p>
            </div>
          </CollapsiblePanel>

          <CollapsiblePanel title="Escala" description="Tamanho final da imagem" :icon="Expand">
            <div class="scale-mode-tabs">
              <button
                class="mode-tab"
                :class="{ active: job.scaleConfig.mode === 'preset' }"
                type="button"
                @click="switchScaleMode(job, 'preset')"
              >
                Predefinido
              </button>
              <button
                class="mode-tab"
                :class="{ active: job.scaleConfig.mode === 'custom' }"
                type="button"
                @click="switchScaleMode(job, 'custom')"
              >
                Customizado
              </button>
            </div>

            <div v-if="job.scaleConfig.mode === 'preset'" class="scale-buttons">
              <button
                v-for="s in [2, 4]"
                :key="s"
                class="scale-btn"
                :class="{ active: job.scaleConfig.presetFactor === s }"
                type="button"
                @click="
                  job.scaleConfig.presetFactor = s as 2 | 4;
                  syncCustomSizeToPreset(job)
                "
              >
                {{ s }}x
              </button>
            </div>

            <div v-else class="field">
              <div class="field-label-row">
                <label class="field-label">Largura e altura</label>
                <button
                  class="link-btn"
                  type="button"
                  :aria-pressed="job.scaleConfig.lockAspectRatio"
                  :title="
                    job.scaleConfig.lockAspectRatio
                      ? 'Proporção travada — clique para destravar'
                      : 'Proporção livre — clique para travar'
                  "
                  @click="toggleAspectLock(job)"
                >
                  <component :is="job.scaleConfig.lockAspectRatio ? Link : Unlink" :size="13" />
                  {{ job.scaleConfig.lockAspectRatio ? 'Travada' : 'Livre' }}
                </button>
              </div>
              <div class="steppers-row">
                <ResolutionStepper
                  label="Largura"
                  :model-value="job.scaleConfig.customWidth ?? job.sourceMeta.width ?? 0"
                  :min="job.sourceMeta.width ?? 1"
                  :max="MAX_OUTPUT_DIMENSION"
                  @update:model-value="(v) => onCustomWidthInput(job!, String(v))"
                />
                <ResolutionStepper
                  label="Altura"
                  :model-value="job.scaleConfig.customHeight ?? job.sourceMeta.height ?? 0"
                  :min="job.sourceMeta.height ?? 1"
                  :max="MAX_OUTPUT_DIMENSION"
                  @update:model-value="(v) => onCustomHeightInput(job!, String(v))"
                />
              </div>
              <div v-if="customFactor" class="scale-multiplier">
                <span class="scale-multiplier-label">Multiplicador de resolução</span>
                <span class="scale-multiplier-value">{{ customFactor.toFixed(1) }}×</span>
              </div>
              <p v-if="!job.scaleConfig.lockAspectRatio" class="field-warning">
                A imagem será distorcida.
              </p>
              <p v-if="customBeyondNative" class="field-warning">
                Alvo acima do fator nativo ({{ job.scaleConfig.presetFactor }}x) — o excedente é
                interpolação, com menos ganho de detalhe.
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

          <CollapsiblePanel
            title="Ajustes"
            description="Ajustes finos de qualidade"
            :icon="SlidersHorizontal"
          >
            <div class="toggle-row">
              <label class="field-label">Filtro de redução de ruído</label>
              <button
                class="switch"
                :class="{ on: job.scaleConfig.denoiseFilterEnabled }"
                type="button"
                @click="toggleDenoiseFilter"
              >
                <span class="knob" />
              </button>
            </div>
            <div v-if="job.scaleConfig.denoiseFilterEnabled" class="denoise-filter-panel">
              <div class="denoise-preset-row">
                <button
                  v-for="preset in DENOISE_PRESETS"
                  :key="preset.key"
                  type="button"
                  class="preset-btn"
                  :class="{ active: denoiseActivePresetKey === preset.key }"
                  @click="setDenoisePreset(preset)"
                >
                  {{ preset.label }}
                </button>
              </div>
              <div v-if="denoiseActivePresetKey === 'custom'" class="slider-field">
                <div class="slider-head">
                  <label class="field-label">Intensidade</label>
                  <span class="slider-value">{{ job.scaleConfig.denoiseFilterStrength }}</span>
                </div>
                <RangeSlider
                  v-model="job.scaleConfig.denoiseFilterStrength"
                  :default-value="45"
                  @update:model-value="requestDenoisePreview"
                />
              </div>
              <p class="field-hint">
                Suaviza granulação e artefatos de compressão preservando bordas (non-local means,
                OpenCV) — independente do modelo escolhido.
              </p>
              <div v-if="!hasNativeApi" class="field-hint">
                Prévia indisponível fora do app desktop.
              </div>
              <div v-else class="denoise-preview">
                <Loader2 v-if="denoisePreviewLoading" :size="16" class="spin" />
                <p v-else-if="denoisePreviewError" class="field-warning">
                  {{ denoisePreviewError }}
                </p>
                <div v-else-if="denoisePreview" class="denoise-preview-images">
                  <div class="denoise-preview-item">
                    <span class="denoise-preview-label">Antes</span>
                    <img
                      :src="`data:image/png;base64,${denoisePreview.before}`"
                      alt="Antes da redução de ruído"
                    />
                  </div>
                  <div class="denoise-preview-item">
                    <span class="denoise-preview-label">Depois</span>
                    <img
                      :src="`data:image/png;base64,${denoisePreview.after}`"
                      alt="Depois da redução de ruído"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div class="slider-field">
              <div class="slider-head">
                <label class="field-label">Nitidez</label>
                <span class="slider-value">{{ job.scaleConfig.sharpen }}</span>
              </div>
              <RangeSlider v-model="job.scaleConfig.sharpen" :default-value="0" />
              <p class="field-hint">Máscara de nitidez (unsharp mask) aplicada após o upscale</p>
            </div>

            <div class="toggle-row">
              <label class="field-label">Recuperação de faces</label>
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
                <label class="field-label">Intensidade</label>
                <span class="slider-value">{{ job.scaleConfig.faceRecoveryStrength }}</span>
              </div>
              <RangeSlider v-model="job.scaleConfig.faceRecoveryStrength" :default-value="80" />
              <p class="field-hint">
                Restaura rostos detectados via GFPGAN (rede neural treinada especificamente para
                isso). Sem rosto detectável na imagem, ela permanece inalterada.
              </p>
            </div>
          </CollapsiblePanel>

          <button
            class="apply-all-btn"
            type="button"
            :disabled="configuringJobs.length < 2"
            @click="applyConfigToAll(job)"
          >
            Aplicar esta configuração a todos ({{ configuringJobs.length }})
          </button>

          <button
            class="export-btn"
            type="button"
            :disabled="!validity.valid"
            @click="process(job)"
          >
            {{
              job.status === 'error' || job.status === 'cancelled'
                ? 'Tentar novamente'
                : 'Processar'
            }}
          </button>
        </template>

        <!-- ---------------------------- QUEUED / PROCESSING ---------------------------- -->
        <template v-else-if="job.status === 'queued' || job.status === 'processing'">
          <div class="processing-panel">
            <Loader2 :size="28" class="spin" />
            <p v-if="job.status === 'queued'" class="processing-label">
              Na fila{{ job.queuePosition ? ` (posição ${job.queuePosition})` : '' }}
            </p>
            <p v-else class="processing-label">Processando… {{ job.progress }}%</p>
            <p v-if="job.stage" class="processing-stage">{{ job.stage }}</p>
            <p v-if="elapsedLabel" class="processing-stage">Tempo decorrido: {{ elapsedLabel }}</p>
            <div class="progress-track">
              <div
                class="progress-fill"
                :style="{ width: (job.status === 'queued' ? 0 : job.progress) + '%' }"
              />
            </div>
            <button class="cancel-btn" type="button" @click="cancel(job)">Cancelar</button>
          </div>
        </template>

        <!-- ---------------------------- DONE ---------------------------- -->
        <template v-else-if="job.status === 'done'">
          <CollapsiblePanel
            title="Resultado"
            description="Comparação e estatísticas do processamento"
            :icon="ChartNoAxesColumn"
          >
            <ComparisonStats :job="job" />
          </CollapsiblePanel>

          <CollapsiblePanel
            title="Exportar"
            description="Formato, destino e nome do arquivo final"
            :icon="Download"
          >
            <div class="field">
              <label class="field-label">Formato</label>
              <AppSelect
                :model-value="exportFormat"
                :options="exportFormatOptions"
                @update:model-value="(v) => (exportFormat = v as 'png' | 'jpg' | 'webp')"
              />
            </div>

            <div v-if="exportFormat !== 'png'" class="field">
              <div class="slider-head">
                <label class="field-label">Qualidade</label>
                <span class="slider-value">{{ exportQuality }}</span>
              </div>
              <RangeSlider v-model="exportQuality" :default-value="90" :min="1" :max="100" />
            </div>

            <div class="field">
              <label class="field-label">Pasta de destino</label>
              <div class="folder-row">
                <input
                  class="select folder-input"
                  type="text"
                  :value="exportDestFolder ?? 'Mesma pasta do original'"
                  readonly
                />
                <button class="folder-btn" type="button" @click="pickExportFolder">
                  <FolderOpen :size="15" />
                </button>
              </div>
            </div>

            <div class="field">
              <label class="field-label">Nome do arquivo</label>
              <input
                class="select"
                type="text"
                :placeholder="`${job.fileName.replace(/\\.[^.]+$/, '')}_upscaled.${exportFormat}`"
                :value="exportFilename ?? ''"
                @input="exportFilename = ($event.target as HTMLInputElement).value || null"
              />
            </div>

            <div class="field">
              <label class="field-label">Em caso de conflito</label>
              <AppSelect
                :model-value="exportConflict"
                :options="conflictOptions"
                @update:model-value="(v) => (exportConflict = v as 'overwrite' | 'rename' | 'ask')"
              />
            </div>

            <div v-if="conflictPrompt" class="conflict-prompt">
              <p>Já existe um arquivo com esse nome. O que fazer?</p>
              <div class="conflict-actions">
                <button type="button" @click="resolveConflict('rename')">Renomear</button>
                <button type="button" @click="resolveConflict('overwrite')">Sobrescrever</button>
              </div>
            </div>

            <p v-if="job.exportState === 'error' && !conflictPrompt" class="banner-error">
              <AlertCircle :size="14" /> {{ job.exportError }}
            </p>
            <p v-if="job.exportState === 'exported'" class="banner-info">
              Exportado em: {{ job.lastExportPath }}
            </p>

            <button
              class="export-btn"
              type="button"
              :disabled="job.exportState === 'exporting'"
              @click="runExport(job)"
            >
              <component
                :is="job.exportState === 'exporting' ? Loader2 : Download"
                :size="16"
                :class="{ spin: job.exportState === 'exporting' }"
              />
              {{ job.exportState === 'exporting' ? 'Exportando…' : 'Exportar' }}
            </button>

            <button class="reprocess-btn" type="button" @click="job.status = 'configuring'">
              <RotateCcw :size="14" /> Ajustar e reprocessar
            </button>
          </CollapsiblePanel>
        </template>
      </aside>
    </div>

    <BatchExportModal v-if="showBatchModal" :jobs="doneJobs" @close="showBatchModal = false" />
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

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: var(--fs-label);
  padding: var(--space-4);
  text-align: center;
}

.empty-state-inner {
  width: 100%;
  max-width: 640px;
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
  border-radius: 999px;
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
  border-radius: 999px;
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
  border-radius: 999px;
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
  border-radius: 999px;
  padding: 4px;
}

.preset-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  padding: 5px 12px;
  border-radius: 999px;
  cursor: pointer;
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
  width: 92px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 2px solid var(--surface-border);
  background: var(--surface-2);
  padding: 0;
  cursor: pointer;
  text-align: left;
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
  height: 88px;
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
.apply-all-btn,
.export-btn,
.processing-panel,
.panel-drawer-header {
  flex-shrink: 0;
}

.banner-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
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
  gap: 6px;
}

.banner-info {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.badge {
  font-size: 9px;
  font-weight: var(--fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
  background: var(--surface-3);
  padding: 1px 6px;
  border-radius: 999px;
}

.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-hint {
  font-size: 11px;
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

.scale-mode-tabs {
  display: flex;
  gap: 4px;
  background: var(--surface-3);
  border-radius: var(--radius-sm);
  padding: 3px;
}

.mode-tab {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
}

.mode-tab.active {
  background: var(--surface-1);
  color: var(--text-primary);
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
  color: #fff;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  border-radius: 999px;
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
  gap: 6px;
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
  border-radius: 999px;
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
  border-radius: 50%;
  background: #fff;
  transition: transform var(--transition-fast);
}

.switch.on .knob {
  transform: translateX(14px);
}

.denoise-filter-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.denoise-preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: 999px;
  padding: 4px;
}

.denoise-preview {
  display: flex;
  justify-content: center;
  padding: var(--space-2) 0;
}

.denoise-preview-images {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  width: 100%;
}

.denoise-preview-item {
  flex: 1;
  min-width: 100px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.denoise-preview-item img {
  width: 100%;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border-soft);
}

.denoise-preview-label {
  font-size: 11px;
  font-weight: var(--fw-medium);
  color: var(--text-tertiary);
}

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

.folder-btn {
  flex-shrink: 0;
  width: 36px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  cursor: pointer;
}

.folder-btn:hover {
  color: var(--text-primary);
}

.apply-all-btn {
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  padding: 9px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  cursor: pointer;
}

.apply-all-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.export-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px;
  border-radius: var(--radius-sm);
  border: none;
  background: var(--color-primary);
  color: #fff;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.export-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.export-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.reprocess-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--surface-border-soft);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  padding: 8px;
  font-size: var(--fs-caption);
  cursor: pointer;
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

.progress-track {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 200ms ease;
}

.cancel-btn {
  margin-top: var(--space-2);
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  color: var(--color-danger);
  border-radius: var(--radius-sm);
  padding: 8px 16px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.conflict-prompt {
  background: var(--color-warning-soft);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  font-size: var(--fs-caption);
  color: var(--text-primary);
}

.conflict-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.conflict-actions button {
  flex: 1;
  padding: 6px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 11px;
  cursor: pointer;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.btn-outline {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.btn-outline:hover:not(:disabled) {
  background: var(--surface-2);
}

.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
    gap: 6px;
    position: absolute;
    bottom: var(--space-3);
    right: var(--space-3);
    z-index: 3;
    background: var(--color-primary);
    color: #fff;
    border: none;
    border-radius: 999px;
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

  .drawer-close {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
  }
}
</style>

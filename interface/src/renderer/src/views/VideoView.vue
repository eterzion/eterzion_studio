<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import AppButton from '../components/atoms/AppButton.vue'
import StatusBadge from '../components/atoms/StatusBadge.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell from '../components/MediaEditorShell.vue'
import ImageInfoPanel from '../components/ImageInfoPanel.vue'
import {
  Upload,
  FolderOpen,
  AlertCircle,
  ShieldAlert,
  Download,
  Cpu,
  Expand,
  CircleX
} from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  processJob as apiProcessJob,
  confirmSecondaryElements,
  getJob,
  cancelJob as apiCancelJob,
  defaultAdjustments,
  type ContentType,
  type Profile,
  type SecondaryElements
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'
import { PROFILE_OPTIONS, DEVICE_OPTIONS } from '../constants/processing'

defineEmits<{ back: [] }>()

// T049/FR-081 to FR-086: video-enhance jobs of its own (never touches
// store/jobs.ts's queueState, same reasoning as CompressConvertView.vue —
// video needs its own secondary-elements confirmation step that image jobs
// never go through).
type LocalStatus =
  'configuring' | 'queued' | 'awaiting_confirmation' | 'processing' | 'done' | 'error'

interface VideoJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  contentType: ContentType
  profile: Profile
  device: string
  /** 'preset' multiplies the source; 'custom' targets an exact resolution. */
  scaleMode: 'preset' | 'custom'
  scale: '2x' | '4x'
  customWidth: number | null
  customHeight: number | null
  /** Read off the preview element once its metadata loads — a video file, unlike
      an image, carries no dimensions the picker could have told us. */
  sourceWidth: number | null
  sourceHeight: number | null
  status: LocalStatus
  progress: number
  stage: string | null
  error?: string
  outputPath?: string
  secondaryElements?: SecondaryElements | null
  createdAt: number
  /** Drops the progress socket — held so cancelling can stop it. */
  unsubscribe?: () => void
}

// T066 — mirrors store/jobs.ts's recordJob() calls, so video jobs show up in
// Histórico alongside image jobs (previously only image jobs did).
const HISTORY_STATUS: Record<LocalStatus, 'queued' | 'processing' | 'done' | 'error' | null> = {
  configuring: null,
  awaiting_confirmation: null,
  queued: 'queued',
  processing: 'processing',
  done: 'done',
  error: 'error'
}

function syncHistory(job: VideoJob): void {
  const historyStatus = HISTORY_STATUS[job.status]
  if (!historyStatus) return
  recordSimpleJob({
    id: job.id,
    sourcePath: job.file.path,
    fileName: job.file.name,
    status: historyStatus,
    mediaType: 'video',
    contentType: job.contentType,
    createdAt: job.createdAt,
    outputPath: job.outputPath,
    errorMessage: job.error
  })
}

// Described, like the Imagem screen's: the label alone does not tell you which
// one a stylised music video or a rotoscoped short belongs to.
const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string; description: string }[] = [
  {
    value: 'real_video',
    label: 'Vídeo real (filmagem)',
    description: 'Câmera, gravação de tela, qualquer imagem capturada do mundo'
  },
  {
    value: 'anime_video',
    label: 'Vídeo de anime/animação',
    description: 'Anime, desenho, motion graphics — traços definidos e cores chapadas'
  }
]

const LOSS_LABELS: Record<string, string> = {
  extra_audio_tracks: 'Trilhas de áudio extras',
  subtitles: 'Legendas embutidas',
  chapters: 'Capítulos'
}

const jobs = ref<VideoJob[]>([])
const importError = ref<string | null>(null)

// Which file the editor is showing. Mirrors ImageEditorView: the screen edits
// one file at a time while the strip keeps the rest one click away.
const activeId = ref<string | null>(null)
const activeJob = computed(() => jobs.value.find((j) => j.id === activeId.value) ?? null)

const STATUS_LABEL: Record<LocalStatus, string> = {
  configuring: 'Pronto para processar',
  queued: 'Na fila',
  awaiting_confirmation: 'Aguardando confirmação',
  processing: 'Processando',
  done: 'Concluído',
  error: 'Erro'
}

const editorItems = computed(() =>
  jobs.value.map((j) => ({
    id: j.id,
    fileName: j.file.name,
    sourcePath: j.file.path,
    statusLabel: STATUS_LABEL[j.status],
    kind: 'video' as const
  }))
)

async function addFile(described: DescribedFile): Promise<void> {
  if (described.kind !== 'Vídeo') {
    importError.value = `Formato não suportado: ${described.name}`
    return
  }
  jobs.value.push({
    id: crypto.randomUUID(),
    backendJobId: null,
    file: described,
    contentType: 'real_video',
    profile: 'fast',
    device: 'auto',
    scaleMode: 'preset',
    scale: '2x',
    customWidth: null,
    customHeight: null,
    sourceWidth: null,
    sourceHeight: null,
    status: 'configuring',
    progress: 0,
    stage: null,
    createdAt: Date.now()
  })
  activeId.value = jobs.value[jobs.value.length - 1].id
}

const { pickFiles, pickFolder, handleFilesDropped, uploading } = usePickFiles(
  addFile,
  importError,
  ['video']
)

function removeJob(job: VideoJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
  if (activeId.value === job.id) activeId.value = jobs.value[0]?.id ?? null
}

function removeById(id: string): void {
  const target = jobs.value.find((j) => j.id === id)
  if (target) removeJob(target)
}

function watchJob(job: VideoJob, backendJobId: string): void {
  job.unsubscribe = subscribeJobProgress(
    backendJobId,
    (status) => {
      job.progress = status.progress
      job.stage = status.stage
      if (status.status === 'pending_confirmation') {
        job.status = 'awaiting_confirmation'
        job.secondaryElements = status.secondary_elements
      } else if (status.status === 'done') {
        job.status = 'done'
        job.outputPath = status.output_path ?? undefined
      } else if (status.status === 'error') {
        job.status = 'error'
        job.error = status.error ?? 'Falha no processamento.'
      } else if (status.status === 'queued' || status.status === 'processing') {
        job.status = status.status
      }
      syncHistory(job)
    },
    () => {
      getJob(backendJobId)
        .then((status) => {
          if (status.status === 'pending_confirmation') {
            job.status = 'awaiting_confirmation'
            job.secondaryElements = status.secondary_elements
          } else if (status.status === 'done') {
            job.status = 'done'
            job.outputPath = status.output_path ?? undefined
          } else if (status.status === 'error') {
            job.status = 'error'
            job.error = status.error ?? 'Falha no processamento.'
          }
          syncHistory(job)
        })
        .catch(() => {
          job.status = 'error'
          job.error = 'Falha na comunicação com o servidor.'
          syncHistory(job)
        })
    }
  )
}

// Mirrors store/jobs.ts's cancelProcessing() for the Imagem screen: drop the
// socket first so no late frame revives the job, tell the backend (best-effort —
// a job that already finished server-side is not an error here), then put the
// job back where it started so it can simply be run again.
async function cancelJob(job: VideoJob): Promise<void> {
  job.unsubscribe?.()
  job.unsubscribe = undefined
  if (job.backendJobId) {
    try {
      await apiCancelJob(job.backendJobId)
    } catch {
      // best-effort — reset the local state regardless
    }
    recordSimpleJob({
      id: job.id,
      sourcePath: job.file.path,
      fileName: job.file.name,
      status: 'cancelled',
      mediaType: 'video',
      createdAt: job.createdAt
    })
  }
  job.status = 'configuring'
  job.progress = 0
  job.backendJobId = null
}

async function runJob(job: VideoJob): Promise<void> {
  job.status = 'queued'
  job.progress = 0
  job.error = undefined
  try {
    const backendJobId = await createLocalJob(
      {
        media_type: 'video',
        operation: 'enhance',
        input_path: job.file.path,
        content_type_override: job.contentType,
        profile: job.profile,
        device: job.device,
        scale: job.scale,
        // The preset still travels: it is what decides how hard the model works,
        // while custom_size names the exact frame size to land on.
        custom_size:
          job.scaleMode === 'custom' && job.customWidth && job.customHeight
            ? { width: job.customWidth, height: job.customHeight }
            : null
      },
      defaultAdjustments()
    )
    job.backendJobId = backendJobId

    // FR-085: a job with nothing to lose lands straight in `pending` — only
    // start processing once we know it's not sitting in pending_confirmation.
    const created = await getJob(backendJobId)
    if (created.status === 'pending_confirmation') {
      job.status = 'awaiting_confirmation'
      job.secondaryElements = created.secondary_elements
      watchJob(job, backendJobId)
      return
    }

    syncHistory(job)
    await apiProcessJob(backendJobId)
    watchJob(job, backendJobId)
  } catch (error) {
    job.status = 'error'
    job.error = error instanceof Error ? error.message : 'Falha ao criar o job.'
    syncHistory(job)
  }
}

async function confirmAndProcess(job: VideoJob): Promise<void> {
  if (!job.backendJobId) return
  try {
    await confirmSecondaryElements(job.backendJobId)
    job.status = 'queued'
    syncHistory(job)
    await apiProcessJob(job.backendJobId)
  } catch (error) {
    job.status = 'error'
    job.error = error instanceof Error ? error.message : 'Falha ao confirmar o job.'
    syncHistory(job)
  }
}

const configuringCount = computed(() => jobs.value.filter((j) => j.status === 'configuring').length)
const doneCount = computed(() => jobs.value.filter((j) => j.status === 'done').length)

async function runAll(): Promise<void> {
  for (const job of jobs.value) {
    if (job.status === 'configuring') await runJob(job)
  }
}

// The preview is the only place a video's real resolution shows up on this side
// (the backend probes it, but not before the job exists), so the info panel
// below is filled from it.
// The resolutions people actually ask for, rather than a free-form pair of
// numbers: every one of these is a real delivery target.
const RESOLUTION_PRESETS: { label: string; note: string; width: number; height: number }[] = [
  { label: '720p', note: 'HD · 1280 × 720', width: 1280, height: 720 },
  { label: '1080p', note: 'Full HD · 1920 × 1080', width: 1920, height: 1080 },
  { label: '1440p', note: '2K · 2560 × 1440', width: 2560, height: 1440 },
  { label: '4K', note: 'UHD · 3840 × 2160', width: 3840, height: 2160 },
  { label: '8K', note: 'UHD · 7680 × 4320', width: 7680, height: 4320 }
]

function setScaleMode(job: VideoJob, mode: 'preset' | 'custom'): void {
  job.scaleMode = mode
  // Entering Custom with nothing chosen: start from the first preset that
  // is actually an upscale for this file, so the default is never a reduction.
  if (mode === 'custom' && !job.customWidth) {
    const fallback =
      RESOLUTION_PRESETS.find((r) => !job.sourceWidth || r.width > job.sourceWidth) ??
      RESOLUTION_PRESETS[RESOLUTION_PRESETS.length - 1]
    job.customWidth = fallback.width
    job.customHeight = fallback.height
  }
}

function setResolution(job: VideoJob, width: number, height: number): void {
  job.customWidth = width
  job.customHeight = height
}

function onPreviewMetadata(event: Event): void {
  const el = event.target as HTMLVideoElement
  const j = activeJob.value
  if (!j || !el.videoWidth || !el.videoHeight) return
  j.sourceWidth = el.videoWidth
  j.sourceHeight = el.videoHeight
}

const outputSize = computed(() => {
  const j = activeJob.value
  if (!j) return null
  if (j.scaleMode === 'custom')
    return j.customWidth && j.customHeight ? { width: j.customWidth, height: j.customHeight } : null
  if (!j.sourceWidth || !j.sourceHeight) return null
  const factor = Number(j.scale.replace('x', ''))
  return { width: j.sourceWidth * factor, height: j.sourceHeight * factor }
})

// Same rough heuristic the Imagem screen uses: source bytes scaled by the
// pixel-count ratio. Good enough for a hint, and honestly labelled as one.
const estimatedBytes = computed(() => {
  const j = activeJob.value
  const out = outputSize.value
  if (!j?.sourceWidth || !j.sourceHeight || !out) return null
  return Math.round((j.file.size * (out.width * out.height)) / (j.sourceWidth * j.sourceHeight))
})

function exportAll(): void {
  if (!hasNativeApi) return
  const done = jobs.value.find((j) => j.status === 'done' && j.outputPath)
  if (done?.outputPath) api.showItemInFolder(done.outputPath)
}
</script>

<template>
  <div class="video-view" data-module="video">
    <TopBar
      :title="activeJob?.file.name ?? 'Nenhum vídeo selecionado'"
      show-back
      @back="$emit('back')"
    >
      <template #actions>
        <AppButton variant="outline" @click="pickFiles">
          <template #icon><Upload :size="15" /></template>
          Importar
        </AppButton>
        <AppButton variant="outline" :disabled="!configuringCount" @click="runAll">
          Processar todos
        </AppButton>
        <AppButton variant="outline" :disabled="!doneCount" @click="exportAll">
          <template #icon><Download :size="15" /></template>
          Exportar tudo
        </AppButton>
      </template>
    </TopBar>

    <div class="video-content">
      <!-- Only while the list has jobs: with an empty list the UploadZone below
           already surfaces the same message in its own error state. -->
      <p v-if="importError && jobs.length" class="banner-error">
        <AlertCircle :size="14" /> {{ importError }}
      </p>

      <UploadZone
        v-if="!jobs.length"
        class="upload-fill"
        :error="importError"
        :loading="uploading"
        title="Arraste vídeos aqui"
        subtitle="ou use os botões abaixo — o áudio e a duração originais são mantidos"
        :formats="['MP4', 'MKV', 'MOV', 'AVI', 'WEBM']"
        @pick-files="pickFiles"
        @pick-folder="pickFolder"
        @files-dropped="handleFilesDropped"
      />

      <MediaEditorShell
        v-else
        class="editor-shell"
        :items="editorItems"
        :active-id="activeId"
        add-label="Adicionar vídeo"
        @select="activeId = $event"
        @remove="removeById"
        @add="pickFiles"
      >
        <template #preview>
          <video
            v-if="activeJob && hasNativeApi"
            :key="activeJob.id"
            class="preview-video"
            :src="api.toFileUrl(activeJob.file.path)"
            controls
            preload="metadata"
            @loadedmetadata="onPreviewMetadata"
          />
        </template>

        <template #panel>
          <template v-if="activeJob">
            <div v-if="activeJob.status === 'configuring'" class="panel-section">
              <CollapsiblePanel
                title="Processamento"
                description="Como o vídeo é processado pelo modelo"
                :icon="Cpu"
              >
                <div class="field">
                  <label class="field-label">Conteúdo detectado</label>
                  <AppSelect
                    :model-value="activeJob.contentType"
                    :options="CONTENT_TYPE_OPTIONS"
                    @update:model-value="(v) => (activeJob!.contentType = v as ContentType)"
                  />
                </div>

                <div class="field">
                  <label class="field-label">Esforço do processamento</label>
                  <AppSelect
                    :model-value="activeJob.profile"
                    :options="PROFILE_OPTIONS"
                    @update:model-value="(v) => (activeJob!.profile = v as Profile)"
                  />
                </div>

                <div class="field">
                  <label class="field-label">Onde processar</label>
                  <AppSelect
                    :model-value="activeJob.device"
                    :options="DEVICE_OPTIONS"
                    @update:model-value="(v) => (activeJob!.device = String(v))"
                  />
                </div>
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Escala"
                description="Resolução final do vídeo"
                :icon="Expand"
              >
                <div class="scale-mode-tabs">
                  <button
                    class="mode-tab"
                    :class="{ active: activeJob.scaleMode === 'preset' }"
                    type="button"
                    @click="setScaleMode(activeJob, 'preset')"
                  >
                    Predefinido
                  </button>
                  <button
                    class="mode-tab"
                    :class="{ active: activeJob.scaleMode === 'custom' }"
                    type="button"
                    @click="setScaleMode(activeJob, 'custom')"
                  >
                    Custom
                  </button>
                </div>

                <!-- The same two buttons the Imagem screen uses, rather than a
                     dropdown: with exactly two choices, both should be visible. -->
                <div v-if="activeJob.scaleMode === 'preset'" class="scale-buttons">
                  <button
                    v-for="s in ['2x', '4x'] as const"
                    :key="s"
                    class="scale-btn"
                    :class="{ active: activeJob.scale === s }"
                    type="button"
                    @click="activeJob!.scale = s"
                  >
                    {{ s }}
                  </button>
                </div>

                <div v-else class="resolution-list">
                  <button
                    v-for="preset in RESOLUTION_PRESETS"
                    :key="preset.label"
                    class="resolution-btn"
                    :class="{ active: activeJob.customWidth === preset.width }"
                    type="button"
                    @click="setResolution(activeJob!, preset.width, preset.height)"
                  >
                    <span class="resolution-label">{{ preset.label }}</span>
                    <span class="resolution-note">{{ preset.note }}</span>
                  </button>
                  <p
                    v-if="
                      activeJob.sourceWidth &&
                      activeJob.customWidth &&
                      activeJob.customWidth < activeJob.sourceWidth
                    "
                    class="field-warning"
                  >
                    Esse alvo é menor que o vídeo original — a saída será reduzida, não ampliada.
                  </p>
                </div>
                <!-- Same readout the Imagem screen gets. The component is named
                     for where it started, but nothing in it is image-specific. -->
                <ImageInfoPanel
                  :original-width="activeJob.sourceWidth"
                  :original-height="activeJob.sourceHeight"
                  :new-width="outputSize?.width ?? null"
                  :new-height="outputSize?.height ?? null"
                  :estimated-bytes="estimatedBytes"
                />
              </CollapsiblePanel>
              <AppButton variant="primary" size="lg" @click="runJob(activeJob)"
                >Processar</AppButton
              >
            </div>

            <div v-else-if="activeJob.status === 'awaiting_confirmation'" class="job-confirm">
              <div class="confirm-header">
                <ShieldAlert :size="16" />
                <span>Este vídeo tem elementos que serão perdidos ao processar:</span>
              </div>
              <ul class="loss-list">
                <li v-for="loss in activeJob.secondaryElements?.losses ?? []" :key="loss">
                  {{ LOSS_LABELS[loss] ?? loss }}
                </li>
              </ul>
              <div class="confirm-actions">
                <AppButton variant="outline" size="sm" @click="removeJob(activeJob)">
                  Cancelar
                </AppButton>
                <AppButton variant="primary" size="sm" @click="confirmAndProcess(activeJob)">
                  Continuar mesmo assim
                </AppButton>
              </div>
            </div>

            <div v-else class="panel-section">
              <StatusBadge
                v-if="activeJob.status === 'queued' || activeJob.status === 'processing'"
                :state="activeJob.status"
                :detail="
                  activeJob.stage
                    ? `${activeJob.stage} · ${activeJob.progress}%`
                    : `${activeJob.progress}%`
                "
              />
              <AppButton
                v-if="activeJob.status === 'queued' || activeJob.status === 'processing'"
                variant="outline"
                size="sm"
                @click="cancelJob(activeJob)"
              >
                <template #icon><CircleX :size="14" /></template>
                Cancelar
              </AppButton>
              <div v-else-if="activeJob.status === 'done'" class="done-row">
                <StatusBadge state="done" />
                <AppButton
                  v-if="hasNativeApi && activeJob.outputPath"
                  variant="outline"
                  size="sm"
                  @click="api.showItemInFolder(activeJob.outputPath!)"
                >
                  <template #icon><FolderOpen :size="14" /></template>
                  Abrir pasta
                </AppButton>
              </div>
              <StatusBadge
                v-else-if="activeJob.status === 'error'"
                state="error"
                :detail="activeJob.error"
              />
            </div>
          </template>
        </template>
      </MediaEditorShell>
    </div>
  </div>
</template>

<style scoped>
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
.resolution-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.resolution-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 8px 10px;
  text-align: left;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-primary);
  cursor: pointer;
}
.resolution-btn.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.resolution-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
}
.resolution-note {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}
.field-warning {
  font-size: 11px;
  color: var(--color-warning);
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
.video-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.video-content {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* The editor lays out its own preview/strip/panel — no outer padding fighting
   it once files are loaded. */
.video-content:has(.editor-shell) {
  padding: 0;
}

/* Empty state: the drop zone takes the whole remaining area rather than being
   a short strip at the top of the screen (same treatment as the Imagem screen). */
.upload-fill {
  flex: 1;
  min-height: 0;
}
.banner-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}
.editor-shell {
  flex: 1;
  min-height: 0;
}
.preview-video {
  max-width: 100%;
  max-height: 100%;
}
.panel-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.field-label {
  font-size: var(--fs-label);
  color: var(--text-secondary);
}
.job-confirm {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
}
.confirm-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-warning, var(--text-primary));
  font-weight: 600;
  font-size: var(--fs-body-sm);
}
.loss-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--fs-body-sm);
  color: var(--text-secondary);
}
.confirm-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}
.done-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>

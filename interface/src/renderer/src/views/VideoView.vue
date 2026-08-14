<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import AppButton from '../components/atoms/AppButton.vue'
import AppSpinner from '../components/atoms/AppSpinner.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell from '../components/MediaEditorShell.vue'
import {
  Upload,
  FolderOpen,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
  Download,
  Cpu,
  Expand
} from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  processJob as apiProcessJob,
  confirmSecondaryElements,
  getJob,
  defaultAdjustments,
  type ContentType,
  type SecondaryElements
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'

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
  scale: '2x' | '4x'
  status: LocalStatus
  progress: number
  stage: string | null
  error?: string
  outputPath?: string
  secondaryElements?: SecondaryElements | null
  createdAt: number
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

const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string }[] = [
  { value: 'real_video', label: 'Vídeo real (filmagem)' },
  { value: 'anime_video', label: 'Vídeo de anime/animação' }
]

const SCALE_OPTIONS = [
  { value: '2x', label: '2x' },
  { value: '4x', label: '4x' }
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
    scale: '2x',
    status: 'configuring',
    progress: 0,
    stage: null,
    createdAt: Date.now()
  })
  activeId.value = jobs.value[jobs.value.length - 1].id
}

const { pickFiles, pickFolder, handleFilesDropped, uploading } = usePickFiles(addFile, importError)

function removeJob(job: VideoJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
  if (activeId.value === job.id) activeId.value = jobs.value[0]?.id ?? null
}

function removeById(id: string): void {
  const target = jobs.value.find((j) => j.id === id)
  if (target) removeJob(target)
}

function watchJob(job: VideoJob, backendJobId: string): void {
  subscribeJobProgress(
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
        scale: job.scale
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

function exportAll(): void {
  if (!hasNativeApi) return
  const done = jobs.value.find((j) => j.status === 'done' && j.outputPath)
  if (done?.outputPath) api.showItemInFolder(done.outputPath)
}
</script>

<template>
  <div class="video-view" data-module="video">
    <TopBar :title="activeJob?.file.name ?? 'Vídeo'" show-back @back="$emit('back')">
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
          />
        </template>

        <template #panel>
          <template v-if="activeJob">
            <div v-if="activeJob.status === 'configuring'" class="panel-section">
              <CollapsiblePanel
                title="Tipo de conteúdo"
                description="Detectado automaticamente — corrija se estiver errado"
                :icon="Cpu"
              >
                <AppSelect
                  :model-value="activeJob.contentType"
                  :options="CONTENT_TYPE_OPTIONS"
                  @update:model-value="(v) => (activeJob!.contentType = v as ContentType)"
                />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Escala"
                description="Resolução final do vídeo"
                :icon="Expand"
              >
                <AppSelect
                  :model-value="activeJob.scale"
                  :options="SCALE_OPTIONS"
                  @update:model-value="(v) => (activeJob!.scale = v as '2x' | '4x')"
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
              <div
                v-if="activeJob.status === 'queued' || activeJob.status === 'processing'"
                class="status-row"
              >
                <AppSpinner :size="16" />
                <span>{{ activeJob.stage ?? 'Processando' }} — {{ activeJob.progress }}%</span>
              </div>
              <div v-else-if="activeJob.status === 'done'" class="status-row done">
                <CheckCircle2 :size="16" />
                <span>Concluído</span>
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
              <div v-else-if="activeJob.status === 'error'" class="status-row error">
                <AlertCircle :size="16" />
                <span>{{ activeJob.error }}</span>
              </div>
            </div>
          </template>
        </template>
      </MediaEditorShell>
    </div>
  </div>
</template>

<style scoped>
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
.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.status-row.done {
  color: var(--color-success, var(--text-primary));
}
.status-row.error {
  color: var(--color-danger);
}
</style>

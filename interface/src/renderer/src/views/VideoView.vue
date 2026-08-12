<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import AppButton from '../components/atoms/AppButton.vue'
import AppSpinner from '../components/atoms/AppSpinner.vue'
import JobCard from '../components/molecules/JobCard.vue'
import EmptyState from '../components/molecules/EmptyState.vue'
import { Upload, FolderOpen, CheckCircle2, AlertCircle, ShieldAlert, Download } from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  processJob as apiProcessJob,
  confirmSecondaryElements,
  getJob,
  type ContentType,
  type SecondaryElements
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'

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
}

const { pickFiles } = usePickFiles(addFile, importError)

function removeJob(job: VideoJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
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
      {
        denoise: 50,
        deblur: 0,
        detail_recovery: 0,
        face_correction: false,
        face_recovery_strength: 80,
        denoise_filter_enabled: false,
        denoise_filter_strength: 45
      }
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
  <div class="video-view">
    <TopBar title="Vídeo">
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
      <p class="hint">
        Aumenta a resolução de vídeos quadro a quadro, preservando fps, duração e áudio originais.
      </p>
      <p v-if="importError" class="banner-error"><AlertCircle :size="14" /> {{ importError }}</p>

      <EmptyState
        v-if="!jobs.length"
        message="Nenhum vídeo importado ainda."
        action-label="Importar vídeo"
        @action="pickFiles"
      >
        <template #icon><Upload :size="15" /></template>
      </EmptyState>

      <div v-else class="job-list">
        <JobCard
          v-for="job in jobs"
          :key="job.id"
          :file-name="job.file.name"
          @remove="removeJob(job)"
        >
          <div v-if="job.status === 'configuring'" class="job-config">
            <div class="field">
              <label class="field-label">Tipo de conteúdo</label>
              <AppSelect
                :model-value="job.contentType"
                :options="CONTENT_TYPE_OPTIONS"
                @update:model-value="(v) => (job.contentType = v as ContentType)"
              />
            </div>
            <div class="field">
              <label class="field-label">Escala</label>
              <AppSelect
                :model-value="job.scale"
                :options="SCALE_OPTIONS"
                @update:model-value="(v) => (job.scale = v as '2x' | '4x')"
              />
            </div>
            <AppButton variant="primary" size="lg" @click="runJob(job)">Processar</AppButton>
          </div>

          <div v-else-if="job.status === 'awaiting_confirmation'" class="job-confirm">
            <div class="confirm-header">
              <ShieldAlert :size="16" />
              <span>Este vídeo tem elementos que serão perdidos ao processar:</span>
            </div>
            <ul class="loss-list">
              <li v-for="loss in job.secondaryElements?.losses ?? []" :key="loss">
                {{ LOSS_LABELS[loss] ?? loss }}
              </li>
            </ul>
            <div class="confirm-actions">
              <AppButton variant="outline" size="sm" @click="removeJob(job)">Cancelar</AppButton>
              <AppButton variant="primary" size="sm" @click="confirmAndProcess(job)">
                Continuar mesmo assim
              </AppButton>
            </div>
          </div>

          <div v-else class="job-status">
            <div v-if="job.status === 'queued' || job.status === 'processing'" class="status-row">
              <AppSpinner :size="16" />
              <span>{{ job.stage ?? 'Processando' }} — {{ job.progress }}%</span>
            </div>
            <div v-else-if="job.status === 'done'" class="status-row done">
              <CheckCircle2 :size="16" />
              <span>Concluído</span>
              <AppButton
                v-if="hasNativeApi && job.outputPath"
                variant="outline"
                size="sm"
                @click="api.showItemInFolder(job.outputPath!)"
              >
                <template #icon><FolderOpen :size="14" /></template>
                Abrir pasta
              </AppButton>
            </div>
            <div v-else-if="job.status === 'error'" class="status-row error">
              <AlertCircle :size="16" />
              <span>{{ job.error }}</span>
            </div>
          </div>
        </JobCard>
      </div>
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
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.hint {
  color: var(--text-secondary);
  font-size: var(--fs-body-sm);
}
.banner-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}
.job-list {
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

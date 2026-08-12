<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import AppButton from '../components/atoms/AppButton.vue'
import AppSpinner from '../components/atoms/AppSpinner.vue'
import JobCard from '../components/molecules/JobCard.vue'
import EmptyState from '../components/molecules/EmptyState.vue'
import { Upload, FolderOpen, CheckCircle2, AlertCircle, Download } from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  processJob as apiProcessJob,
  getJob,
  type MediaType
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'

// Otimizar (CompressConvertView) already has a Comprimir/Converter toggle per
// job — this view is a focused, format-only entry point to the same backend
// contract (operation: 'convert'), for users who just want to change a file's
// extension without wading through compression settings first.
type LocalStatus = 'configuring' | 'queued' | 'processing' | 'done' | 'error'

interface ConvertJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  mediaType: MediaType
  targetFormat: string
  status: LocalStatus
  progress: number
  error?: string
  outputPath?: string
  outputSizeBytes?: number
  createdAt: number
}

const HISTORY_STATUS: Record<LocalStatus, 'queued' | 'processing' | 'done' | 'error' | null> = {
  configuring: null,
  queued: 'queued',
  processing: 'processing',
  done: 'done',
  error: 'error'
}

function syncHistory(job: ConvertJob): void {
  const historyStatus = HISTORY_STATUS[job.status]
  if (!historyStatus) return
  recordSimpleJob({
    id: job.id,
    sourcePath: job.file.path,
    fileName: job.file.name,
    status: historyStatus,
    mediaType: job.mediaType,
    createdAt: job.createdAt,
    outputPath: job.outputPath,
    outputSizeBytes: job.outputSizeBytes,
    errorMessage: job.error
  })
}

const FORMATS_BY_MEDIA_TYPE: Record<MediaType, string[]> = {
  image: ['jpg', 'png', 'webp', 'avif'],
  video: ['mp4', 'mkv', 'mov', 'webm'],
  audio: ['mp3', 'm4a', 'ogg', 'opus', 'flac']
}

const KIND_TO_MEDIA_TYPE: Record<string, MediaType> = {
  Imagem: 'image',
  Vídeo: 'video',
  Áudio: 'audio'
}

const jobs = ref<ConvertJob[]>([])
const importError = ref<string | null>(null)

function formatOptions(mediaType: MediaType): { value: string; label: string }[] {
  return FORMATS_BY_MEDIA_TYPE[mediaType].map((f) => ({ value: f, label: `.${f}` }))
}

function firstOtherFormat(mediaType: MediaType, currentExt: string): string {
  const formats = FORMATS_BY_MEDIA_TYPE[mediaType]
  return formats.find((f) => f !== currentExt) ?? formats[0]
}

async function addFile(described: DescribedFile): Promise<void> {
  const mediaType = described.kind ? KIND_TO_MEDIA_TYPE[described.kind] : undefined
  if (!mediaType) {
    importError.value = `Formato não suportado: ${described.name}`
    return
  }
  const currentExt = described.ext.replace('.', '').toLowerCase()
  jobs.value.push({
    id: crypto.randomUUID(),
    backendJobId: null,
    file: described,
    mediaType,
    targetFormat: firstOtherFormat(mediaType, currentExt),
    status: 'configuring',
    progress: 0,
    createdAt: Date.now()
  })
}

const { pickFiles } = usePickFiles(addFile, importError)

function removeJob(job: ConvertJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
}

async function runJob(job: ConvertJob): Promise<void> {
  job.status = 'queued'
  job.progress = 0
  job.error = undefined
  try {
    const backendJobId = await createLocalJob(
      {
        media_type: job.mediaType,
        operation: 'convert',
        input_path: job.file.path,
        quality: null,
        output_target: {
          format: job.targetFormat,
          conflict: 'rename'
        }
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
    syncHistory(job)
    await apiProcessJob(backendJobId)

    subscribeJobProgress(
      backendJobId,
      (status) => {
        job.progress = status.progress
        if (status.status === 'done') {
          job.status = 'done'
          job.outputPath = status.output_path ?? undefined
          job.outputSizeBytes = status.output_meta?.size_bytes ?? undefined
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
            job.status =
              status.status === 'done' ? 'done' : status.status === 'error' ? 'error' : job.status
            job.outputPath = status.output_path ?? job.outputPath
            syncHistory(job)
          })
          .catch(() => {
            job.status = 'error'
            job.error = 'Falha na comunicação com o servidor.'
            syncHistory(job)
          })
      }
    )
  } catch (error) {
    job.status = 'error'
    job.error = error instanceof Error ? error.message : 'Falha ao criar o job.'
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

function fmtBytes(bytes: number | undefined): string {
  if (bytes == null) return '—'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}
</script>

<template>
  <div class="converter-view">
    <TopBar title="Converter">
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

    <div class="converter-content">
      <p class="hint">
        Converta imagens, vídeos e áudios para outro formato de arquivo, sem IA — mantém dimensões e
        duração originais, só muda o container/codec de saída.
      </p>
      <p v-if="importError" class="banner-error"><AlertCircle :size="14" /> {{ importError }}</p>

      <EmptyState
        v-if="!jobs.length"
        message="Nenhum arquivo importado ainda."
        action-label="Importar arquivo"
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
              <label class="field-label">Formato de destino</label>
              <AppSelect
                :model-value="job.targetFormat"
                :options="formatOptions(job.mediaType)"
                @update:model-value="(v) => (job.targetFormat = String(v))"
              />
            </div>

            <AppButton variant="primary" size="lg" @click="runJob(job)">Converter</AppButton>
          </div>

          <div v-else class="job-status">
            <div v-if="job.status === 'queued' || job.status === 'processing'" class="status-row">
              <AppSpinner :size="16" />
              <span>{{ job.progress }}%</span>
            </div>
            <div v-else-if="job.status === 'done'" class="status-row done">
              <CheckCircle2 :size="16" />
              <span>Concluído — {{ fmtBytes(job.outputSizeBytes) }}</span>
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
.converter-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.converter-content {
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

<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import RangeSlider from '../components/RangeSlider.vue'
import {
  Upload,
  FolderOpen,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Download
} from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../nativeBridge'
import {
  createLocalJob,
  processJob as apiProcessJob,
  subscribeJobProgress,
  getJob,
  type MediaType,
  type Operation
} from '../apiClient'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'

// This view never touches store/jobs.ts's queueState — that store's Job/ScaleConfig
// model is enhance-specific (content_type/profile). Compress/convert never invokes
// an AI model (FR-029), so it gets its own small, self-contained job list here
// instead of stretching the enhance data model to cover an unrelated operation.
type LocalStatus = 'configuring' | 'queued' | 'processing' | 'done' | 'error'

interface OptimizeJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  mediaType: MediaType
  operation: Operation
  targetFormat: string
  quality: number
  status: LocalStatus
  progress: number
  error?: string
  outputPath?: string
  outputSizeBytes?: number
  createdAt: number
}

// T066 — mirrors store/jobs.ts's recordJob() calls, so compress/convert jobs
// show up in Histórico alongside image jobs (previously only image jobs did).
const HISTORY_STATUS: Record<LocalStatus, 'queued' | 'processing' | 'done' | 'error' | null> = {
  configuring: null,
  queued: 'queued',
  processing: 'processing',
  done: 'done',
  error: 'error'
}

function syncHistory(job: OptimizeJob): void {
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

const jobs = ref<OptimizeJob[]>([])
const importError = ref<string | null>(null)

function formatOptions(mediaType: MediaType): { value: string; label: string }[] {
  return FORMATS_BY_MEDIA_TYPE[mediaType].map((f) => ({ value: f, label: `.${f}` }))
}

async function addFile(described: DescribedFile): Promise<void> {
  const mediaType = described.kind ? KIND_TO_MEDIA_TYPE[described.kind] : undefined
  if (!mediaType) {
    importError.value = `Formato não suportado: ${described.name}`
    return
  }
  jobs.value.push({
    id: crypto.randomUUID(),
    backendJobId: null,
    file: described,
    mediaType,
    operation: 'compress',
    targetFormat: described.ext.replace('.', '').toLowerCase(),
    quality: 75,
    status: 'configuring',
    progress: 0,
    createdAt: Date.now()
  })
}

const { pickFiles } = usePickFiles(addFile, importError)

function removeJob(job: OptimizeJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
}

async function runJob(job: OptimizeJob): Promise<void> {
  job.status = 'queued'
  job.progress = 0
  job.error = undefined
  try {
    const backendJobId = await createLocalJob(
      {
        media_type: job.mediaType,
        operation: job.operation,
        input_path: job.file.path,
        quality: job.operation === 'compress' ? job.quality : null,
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
  <div class="optimize-view">
    <TopBar title="Otimizar">
      <template #actions>
        <button class="btn-outline" type="button" @click="pickFiles">
          <Upload :size="15" /> Importar
        </button>
        <button class="btn-outline" type="button" :disabled="!configuringCount" @click="runAll">
          Processar todos
        </button>
        <button class="btn-outline" type="button" :disabled="!doneCount" @click="exportAll">
          <Download :size="15" /> Exportar tudo
        </button>
      </template>
    </TopBar>

    <div class="optimize-content">
      <p class="hint">
        Comprima ou converta imagens, vídeos e áudios sem IA — mantém dimensões e duração originais,
        só muda tamanho de arquivo ou formato (FR-025 a FR-030).
      </p>
      <p v-if="importError" class="banner-error"><AlertCircle :size="14" /> {{ importError }}</p>

      <div v-if="!jobs.length" class="empty-state">
        <p>Nenhum arquivo importado ainda.</p>
        <button class="primary-btn" type="button" @click="pickFiles">
          <Upload :size="15" /> Importar arquivo
        </button>
      </div>

      <div v-else class="job-list">
        <div v-for="job in jobs" :key="job.id" class="job-card">
          <div class="job-card-header">
            <span class="job-name">{{ job.file.name }}</span>
            <button class="icon-btn" type="button" title="Remover" @click="removeJob(job)">
              <XCircle :size="16" />
            </button>
          </div>

          <div v-if="job.status === 'configuring'" class="job-config">
            <div class="op-tabs">
              <button
                class="op-tab"
                :class="{ active: job.operation === 'compress' }"
                type="button"
                @click="job.operation = 'compress'"
              >
                Comprimir
              </button>
              <button
                class="op-tab"
                :class="{ active: job.operation === 'convert' }"
                type="button"
                @click="job.operation = 'convert'"
              >
                Converter
              </button>
            </div>

            <div v-if="job.operation === 'compress'" class="field">
              <div class="slider-head">
                <label class="field-label">Qualidade</label>
                <span class="slider-value">{{ job.quality }}</span>
              </div>
              <RangeSlider v-model="job.quality" :default-value="75" />
            </div>

            <div v-else class="field">
              <label class="field-label">Formato de destino</label>
              <AppSelect
                :model-value="job.targetFormat"
                :options="formatOptions(job.mediaType)"
                @update:model-value="(v) => (job.targetFormat = String(v))"
              />
            </div>

            <button class="primary-btn" type="button" @click="runJob(job)">Processar</button>
          </div>

          <div v-else class="job-status">
            <div v-if="job.status === 'queued' || job.status === 'processing'" class="status-row">
              <Loader2 :size="16" class="spin" />
              <span>{{ job.progress }}%</span>
            </div>
            <div v-else-if="job.status === 'done'" class="status-row done">
              <CheckCircle2 :size="16" />
              <span>Concluído — {{ fmtBytes(job.outputSizeBytes) }}</span>
              <button
                v-if="hasNativeApi && job.outputPath"
                class="btn-outline small"
                type="button"
                @click="api.showItemInFolder(job.outputPath!)"
              >
                <FolderOpen :size="14" /> Abrir pasta
              </button>
            </div>
            <div v-else-if="job.status === 'error'" class="status-row error">
              <AlertCircle :size="16" />
              <span>{{ job.error }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.optimize-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.optimize-content {
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
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--text-secondary);
}
.job-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.job-card {
  background: var(--surface-1);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.job-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.job-name {
  font-weight: 600;
  font-size: var(--fs-label);
}
.op-tabs {
  display: flex;
  gap: var(--space-2);
}
.op-tab {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-1);
  background: var(--surface-2);
  color: var(--text-secondary);
  cursor: pointer;
}
.op-tab.active {
  background: var(--color-primary);
  color: var(--on-primary, #fff);
  border-color: var(--color-primary);
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
.slider-head {
  display: flex;
  justify-content: space-between;
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
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.btn-outline.small {
  padding: 4px 8px;
  font-size: var(--fs-body-sm);
}
</style>

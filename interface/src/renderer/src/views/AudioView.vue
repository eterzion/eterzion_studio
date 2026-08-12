<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import { Upload, FolderOpen, Loader2, CheckCircle2, XCircle, AlertCircle, Download } from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../api'
import {
  createLocalJob,
  detectContentType,
  processJob as apiProcessJob,
  subscribeJobProgress,
  getJob,
  type ContentType
} from '../backend'
import { recordSimpleJob } from '../store/history'

// T057/FR-081-086 don't apply to audio (no secondary streams to lose) — this
// mirrors VideoView.vue's job-list shape without the confirmation step.
// IMPORTANT (FR-023 / spec.md LC-003): there is no compression-artifact
// removal implementation for audio — copy here must never claim it. This
// screen only ever describes noise reduction, loudness normalization, and
// voice-clarity/music-restoration, which are the real DSP + model steps
// audio_processor.py runs.
type LocalStatus = 'detecting' | 'configuring' | 'queued' | 'processing' | 'done' | 'error'

interface AudioJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  contentType: ContentType
  status: LocalStatus
  progress: number
  stage: string | null
  error?: string
  outputPath?: string
  createdAt: number
}

// T066 — mirrors store/jobs.ts's recordJob() calls, so audio jobs show up in
// Histórico alongside image jobs (previously only image jobs did).
const HISTORY_STATUS: Record<LocalStatus, 'queued' | 'processing' | 'done' | 'error' | null> = {
  detecting: null,
  configuring: null,
  queued: 'queued',
  processing: 'processing',
  done: 'done',
  error: 'error'
}

function syncHistory(job: AudioJob): void {
  const historyStatus = HISTORY_STATUS[job.status]
  if (!historyStatus) return
  recordSimpleJob({
    id: job.id,
    sourcePath: job.file.path,
    fileName: job.file.name,
    status: historyStatus,
    mediaType: 'audio',
    contentType: job.contentType,
    createdAt: job.createdAt,
    outputPath: job.outputPath,
    errorMessage: job.error
  })
}

const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string }[] = [
  { value: 'speech', label: 'Fala / voz' },
  { value: 'music', label: 'Música' }
]

const jobs = ref<AudioJob[]>([])
const importError = ref<string | null>(null)

async function addFile(described: DescribedFile): Promise<void> {
  if (described.kind !== 'Áudio') {
    importError.value = `Formato não suportado: ${described.name}`
    return
  }
  const job: AudioJob = {
    id: crypto.randomUUID(),
    backendJobId: null,
    file: described,
    contentType: 'speech',
    status: 'detecting',
    progress: 0,
    stage: null,
    createdAt: Date.now()
  }
  jobs.value.push(job)
  try {
    job.contentType = await detectContentType(described.path, 'audio')
  } catch {
    // Detection failure just leaves the default ('speech') — the person can
    // still correct it manually (FR-096) before processing.
  } finally {
    job.status = 'configuring'
  }
}

async function pickFiles(): Promise<void> {
  if (!hasNativeApi) {
    importError.value = 'Seleção de arquivos disponível apenas no aplicativo desktop.'
    return
  }
  const result = await api.selectFiles()
  if (result.canceled) return
  importError.value = null
  for (const f of result.files) await addFile(f)
}

function removeJob(job: AudioJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
}

async function runJob(job: AudioJob): Promise<void> {
  job.status = 'queued'
  job.progress = 0
  job.error = undefined
  try {
    const backendJobId = await createLocalJob(
      {
        media_type: 'audio',
        operation: 'enhance',
        input_path: job.file.path,
        content_type_override: job.contentType
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
        job.stage = status.stage
        if (status.status === 'done') {
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
            job.status = status.status === 'done' ? 'done' : status.status === 'error' ? 'error' : job.status
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
</script>

<template>
  <div class="audio-view">
    <TopBar title="Áudio">
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

    <div class="audio-content">
      <p class="hint">
        Reduz ruído, normaliza o volume e melhora a clareza da voz ou restaura a música,
        conforme o tipo de conteúdo detectado.
      </p>
      <p v-if="importError" class="banner-error"><AlertCircle :size="14" /> {{ importError }}</p>

      <div v-if="!jobs.length" class="empty-state">
        <p>Nenhum áudio importado ainda.</p>
        <button class="primary-btn" type="button" @click="pickFiles">
          <Upload :size="15" /> Importar áudio
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

          <div v-if="job.status === 'detecting'" class="status-row">
            <Loader2 :size="16" class="spin" />
            <span>Detectando tipo de conteúdo…</span>
          </div>

          <div v-else-if="job.status === 'configuring'" class="job-config">
            <div class="field">
              <label class="field-label">Tipo de conteúdo</label>
              <AppSelect
                :model-value="job.contentType"
                :options="CONTENT_TYPE_OPTIONS"
                @update:model-value="(v) => (job.contentType = v as ContentType)"
              />
            </div>
            <button class="primary-btn" type="button" @click="runJob(job)">Processar</button>
          </div>

          <div v-else class="job-status">
            <div v-if="job.status === 'queued' || job.status === 'processing'" class="status-row">
              <Loader2 :size="16" class="spin" />
              <span>{{ job.stage ?? 'Processando' }} — {{ job.progress }}%</span>
            </div>
            <div v-else-if="job.status === 'done'" class="status-row done">
              <CheckCircle2 :size="16" />
              <span>Concluído</span>
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
.audio-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.audio-content {
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

<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import AppButton from '../components/atoms/AppButton.vue'
import StatusBadge from '../components/atoms/StatusBadge.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell from '../components/MediaEditorShell.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import { Upload, FolderOpen, AlertCircle, Download, Cpu, CircleX } from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  detectContentType,
  processJob as apiProcessJob,
  getJob,
  cancelJob as apiCancelJob,
  defaultAdjustments,
  type ContentType,
  type Profile
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'
import { PROFILE_OPTIONS, DEVICE_OPTIONS } from '../constants/processing'

defineEmits<{ back: [] }>()

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
  profile: Profile
  device: string
  status: LocalStatus
  progress: number
  stage: string | null
  error?: string
  outputPath?: string
  createdAt: number
  /** Drops the progress socket — held so cancelling can stop it. */
  unsubscribe?: () => void
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

const CONTENT_TYPE_OPTIONS: { value: ContentType; label: string; description: string }[] = [
  {
    value: 'speech',
    label: 'Fala / voz',
    description: 'Locução, podcast, entrevista — uma voz em primeiro plano'
  },
  {
    value: 'music',
    label: 'Música',
    description: 'Faixa musical completa, com instrumentos e mixagem'
  }
]

const jobs = ref<AudioJob[]>([])
const importError = ref<string | null>(null)

// Which file the editor is showing. Mirrors ImageEditorView: the screen edits
// one file at a time while the strip keeps the rest one click away.
const activeId = ref<string | null>(null)
const activeJob = computed(() => jobs.value.find((j) => j.id === activeId.value) ?? null)

const STATUS_LABEL: Record<LocalStatus, string> = {
  detecting: 'Detectando…',
  configuring: 'Pronto para processar',
  queued: 'Na fila',
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
    kind: 'audio' as const
  }))
)

async function addFile(described: DescribedFile): Promise<void> {
  if (described.kind !== 'Áudio') {
    importError.value = `Formato não suportado: ${described.name}`
    return
  }
  jobs.value.push({
    id: crypto.randomUUID(),
    backendJobId: null,
    file: described,
    contentType: 'speech',
    profile: 'fast',
    device: 'auto',
    status: 'detecting',
    progress: 0,
    stage: null,
    createdAt: Date.now()
  })
  // Read the entry back out of `jobs.value` — that returns Vue's reactive
  // proxy, not the raw object that was pushed. Mutating the raw object
  // (which is what holding onto a `const job = {...}` before the push gives
  // you) bypasses the proxy's setter, so the template never re-renders and
  // the card stays stuck on "Detectando tipo de conteúdo…" forever.
  const job = jobs.value[jobs.value.length - 1]
  activeId.value = job.id
  try {
    job.contentType = await detectContentType(described.path, 'audio')
  } catch {
    // Detection failure just leaves the default ('speech') — the person can
    // still correct it manually (FR-096) before processing.
  } finally {
    job.status = 'configuring'
  }
}

const { pickFiles, pickFolder, handleFilesDropped, uploading } = usePickFiles(
  addFile,
  importError,
  ['audio']
)

function removeJob(job: AudioJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
  if (activeId.value === job.id) activeId.value = jobs.value[0]?.id ?? null
}

function removeById(id: string): void {
  const target = jobs.value.find((j) => j.id === id)
  if (target) removeJob(target)
}

// Mirrors store/jobs.ts's cancelProcessing() for the Imagem screen: drop the
// socket first so no late frame revives the job, tell the backend (best-effort —
// a job that already finished server-side is not an error here), then put the
// job back where it started so it can simply be run again.
async function cancelJob(job: AudioJob): Promise<void> {
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
      mediaType: 'audio',
      createdAt: job.createdAt
    })
  }
  job.status = 'configuring'
  job.progress = 0
  job.backendJobId = null
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
        content_type_override: job.contentType,
        profile: job.profile,
        device: job.device
      },
      defaultAdjustments()
    )
    job.backendJobId = backendJobId
    syncHistory(job)
    await apiProcessJob(backendJobId)

    job.unsubscribe = subscribeJobProgress(
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
</script>

<template>
  <div class="audio-view" data-module="audio">
    <TopBar
      :title="activeJob?.file.name ?? 'Nenhum áudio selecionado'"
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

    <div class="audio-content">
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
        title="Arraste áudios aqui"
        subtitle="ou use os botões abaixo — voz e música são identificadas automaticamente"
        :formats="['MP3', 'WAV', 'FLAC', 'M4A', 'OGG', 'OPUS']"
        @pick-files="pickFiles"
        @pick-folder="pickFolder"
        @files-dropped="handleFilesDropped"
      />

      <MediaEditorShell
        v-else
        class="editor-shell"
        :items="editorItems"
        :active-id="activeId"
        add-label="Adicionar áudio"
        @select="activeId = $event"
        @remove="removeById"
        @add="pickFiles"
      >
        <template #preview>
          <audio
            v-if="activeJob && hasNativeApi"
            :key="activeJob.id"
            class="preview-audio"
            :src="api.toFileUrl(activeJob.file.path)"
            controls
          />
        </template>

        <template #panel>
          <template v-if="activeJob">
            <StatusBadge v-if="activeJob.status === 'detecting'" state="detecting" />

            <div v-else-if="activeJob.status === 'configuring'" class="panel-section">
              <CollapsiblePanel
                title="Processamento"
                description="Como o áudio é processado pelo modelo"
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

              <AppButton variant="primary" size="lg" @click="runJob(activeJob)"
                >Processar</AppButton
              >
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
.audio-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.audio-content {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* The editor lays out its own preview/strip/panel — no outer padding fighting
   it once files are loaded. */
.audio-content:has(.editor-shell) {
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
.preview-audio {
  width: min(100%, 420px);
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
.done-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>

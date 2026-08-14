<script setup lang="ts">
import { computed, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import CollapsiblePanel from '../components/CollapsiblePanel.vue'
import RangeSlider from '../components/RangeSlider.vue'
import AppButton from '../components/atoms/AppButton.vue'
import AppSpinner from '../components/atoms/AppSpinner.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell from '../components/MediaEditorShell.vue'
import {
  Upload,
  FolderOpen,
  CheckCircle2,
  AlertCircle,
  Download,
  Repeat,
  SlidersHorizontal,
  Expand
} from '@lucide/vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  processJob as apiProcessJob,
  getJob,
  defaultAdjustments,
  type MediaType
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import { usePickFiles } from '../composables/usePickFiles'

defineEmits<{ back: [] }>()

// The single non-AI export screen: change format, trade quality for file size,
// and/or resize — previously split across Otimizar (quality only) and Converter
// (format only), which meant two visits to do both to one file.
//
// Never touches store/jobs.ts's queueState — that store's Job/ScaleConfig model
// is enhance-specific (content_type/profile). This path never invokes a model
// (FR-029), so it keeps its own small job list rather than stretching the
// enhance data model to cover an unrelated operation.
type LocalStatus = 'configuring' | 'queued' | 'processing' | 'done' | 'error'

interface ExportJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  mediaType: MediaType
  /** The file's own extension until the person picks another one. */
  targetFormat: string
  sourceFormat: string
  quality: number
  /** null = keep the source dimensions. Images/video only. */
  width: number | null
  height: number | null
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

function syncHistory(job: ExportJob): void {
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

function formatOptions(mediaType: MediaType): { value: string; label: string }[] {
  return FORMATS_BY_MEDIA_TYPE[mediaType].map((f) => ({ value: f, label: `.${f}` }))
}

const KIND_TO_MEDIA_TYPE: Record<string, MediaType> = {
  Imagem: 'image',
  Vídeo: 'video',
  Áudio: 'audio'
}

const jobs = ref<ExportJob[]>([])
const importError = ref<string | null>(null)

// Which file the editor is showing. Mirrors ImageEditorView: the screen edits
// one file at a time while the strip keeps the rest one click away.
const activeId = ref<string | null>(null)
const activeJob = computed(() => jobs.value.find((j) => j.id === activeId.value) ?? null)

const STATUS_LABEL: Record<LocalStatus, string> = {
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
    kind: j.mediaType
  }))
)

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
    targetFormat: described.ext.replace('.', '').toLowerCase(),
    sourceFormat: described.ext.replace('.', '').toLowerCase(),
    quality: 75,
    width: null,
    height: null,
    status: 'configuring',
    progress: 0,
    createdAt: Date.now()
  })
  activeId.value = jobs.value[jobs.value.length - 1].id
}

const { pickFiles, pickFolder, handleFilesDropped, uploading } = usePickFiles(addFile, importError)

function removeJob(job: ExportJob): void {
  jobs.value = jobs.value.filter((j) => j.id !== job.id)
  if (activeId.value === job.id) activeId.value = jobs.value[0]?.id ?? null
}

function onWidthInput(job: ExportJob, raw: string): void {
  job.width = raw ? Math.max(1, Number(raw)) : null
}

function onHeightInput(job: ExportJob, raw: string): void {
  job.height = raw ? Math.max(1, Number(raw)) : null
}

function removeById(id: string): void {
  const target = jobs.value.find((j) => j.id === id)
  if (target) removeJob(target)
}

async function runJob(job: ExportJob): Promise<void> {
  job.status = 'queued'
  job.progress = 0
  job.error = undefined
  try {
    const backendJobId = await createLocalJob(
      {
        media_type: job.mediaType,
        // Same backend contract as before: 'convert' when the container
        // changes, 'compress' when only quality/size do.
        operation: job.targetFormat === job.sourceFormat ? 'compress' : 'convert',
        input_path: job.file.path,
        quality: job.quality,
        custom_size: job.width && job.height ? { width: job.width, height: job.height } : null,
        output_target: {
          format: job.targetFormat,
          conflict: 'rename'
        }
      },
      defaultAdjustments()
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
    <TopBar :title="activeJob?.file.name ?? 'Exportar'" show-back @back="$emit('back')">
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

    <div class="optimize-content">
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
        title="Arraste arquivos aqui"
        subtitle="ou use os botões abaixo — imagem, vídeo e áudio são identificados automaticamente"
        :formats="['JPG', 'PNG', 'WEBP', 'MP4', 'MKV', 'MP3', 'FLAC']"
        @pick-files="pickFiles"
        @pick-folder="pickFolder"
        @files-dropped="handleFilesDropped"
      />

      <MediaEditorShell
        v-else
        class="editor-shell"
        :items="editorItems"
        :active-id="activeId"
        add-label="Adicionar arquivo"
        @select="activeId = $event"
        @remove="removeById"
        @add="pickFiles"
      >
        <template #preview>
          <template v-if="activeJob && hasNativeApi">
            <img
              v-if="activeJob.mediaType === 'image'"
              class="preview-media"
              :src="api.toFileUrl(activeJob.file.path)"
              alt=""
            />
            <video
              v-else-if="activeJob.mediaType === 'video'"
              :key="activeJob.id"
              class="preview-media"
              :src="api.toFileUrl(activeJob.file.path)"
              controls
              preload="metadata"
            />
            <audio
              v-else
              :key="activeJob.id"
              class="preview-audio"
              :src="api.toFileUrl(activeJob.file.path)"
              controls
            />
          </template>
        </template>

        <template #panel>
          <template v-if="activeJob">
            <div v-if="activeJob.status === 'configuring'" class="panel-section">
              <CollapsiblePanel
                title="Formato"
                description="Mantém o original ou converte para outro container"
                :icon="Repeat"
              >
                <AppSelect
                  :model-value="activeJob.targetFormat"
                  :options="formatOptions(activeJob.mediaType)"
                  @update:model-value="(v) => (activeJob!.targetFormat = String(v))"
                />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Qualidade"
                description="Menor qualidade, menor arquivo — nada é reprocessado por IA"
                :icon="SlidersHorizontal"
              >
                <div class="slider-head">
                  <span class="field-label">Qualidade</span>
                  <span class="slider-value">{{ activeJob.quality }}</span>
                </div>
                <RangeSlider v-model="activeJob.quality" :default-value="75" />
              </CollapsiblePanel>

              <!-- Audio has no dimensions to resize. -->
              <CollapsiblePanel
                v-if="activeJob.mediaType !== 'audio'"
                title="Dimensões"
                description="Deixe em branco para manter o tamanho original"
                :icon="Expand"
              >
                <div class="size-row">
                  <input
                    class="size-input"
                    type="number"
                    min="1"
                    placeholder="Largura"
                    :value="activeJob.width ?? ''"
                    @input="onWidthInput(activeJob, ($event.target as HTMLInputElement).value)"
                  />
                  <span class="size-x">×</span>
                  <input
                    class="size-input"
                    type="number"
                    min="1"
                    placeholder="Altura"
                    :value="activeJob.height ?? ''"
                    @input="onHeightInput(activeJob, ($event.target as HTMLInputElement).value)"
                  />
                </div>
              </CollapsiblePanel>

              <AppButton variant="primary" size="lg" @click="runJob(activeJob)">
                Exportar
              </AppButton>
            </div>

            <div v-else class="panel-section">
              <div
                v-if="activeJob.status === 'queued' || activeJob.status === 'processing'"
                class="status-row"
              >
                <AppSpinner :size="16" />
                <span>{{ activeJob.progress }}%</span>
              </div>
              <div v-else-if="activeJob.status === 'done'" class="status-row done">
                <CheckCircle2 :size="16" />
                <span>Concluído — {{ fmtBytes(activeJob.outputSizeBytes) }}</span>
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
.optimize-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.optimize-content {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* The editor lays out its own preview/strip/panel — no outer padding fighting
   it once files are loaded. */
.optimize-content:has(.editor-shell) {
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
.preview-media {
  max-width: 100%;
  max-height: 100%;
}
.preview-audio {
  width: min(100%, 420px);
}
.panel-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.size-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.size-input {
  min-width: 0;
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-value);
}
.size-x {
  color: var(--text-tertiary);
}
.field-note {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
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
</style>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import FileQueueItem from '../components/FileQueueItem.vue'
import SummaryCards from '../components/SummaryCards.vue'
import { Trash2, ChevronDown, ListChecks } from '@lucide/vue'
import { api, hasNativeApi } from '../api'
import { addFiles, queueState, removeJob, setActiveJob, type UploadResult } from '../store/jobs'

const emit = defineEmits<{
  openImage: []
}>()

const uploadError = ref<string | null>(null)
const uploading = ref(false)
const DEFAULT_MODEL = 'realesrgan-x4'

const jobs = computed(() => queueState.jobs)
const fileCount = computed(() => jobs.value.length)
const totalSizeLabel = computed(() => {
  const totalBytes = jobs.value.reduce((sum, j) => sum + j.sourceMeta.sizeBytes, 0)
  return (totalBytes / (1024 * 1024)).toFixed(2) + ' MB'
})
const statusLabel = computed(() => {
  if (jobs.value.some((j) => j.status === 'processing')) return 'Processando'
  if (jobs.value.length && jobs.value.every((j) => j.status === 'done')) return 'Concluído'
  if (jobs.value.some((j) => j.status === 'error')) return 'Com erros'
  if (jobs.value.some((j) => j.status === 'queued')) return 'Na fila'
  if (jobs.value.length) return 'Configurando'
  return 'Vazio'
})

function clearQueue(): void {
  for (const j of [...jobs.value]) removeJob(j.id)
}

function reportResult(result: UploadResult): void {
  if (result.rejected.length) {
    uploadError.value = result.rejected.map((r) => `${r.name}: ${r.reason}`).join(' · ')
  } else if (!result.added.length && result.duplicates.length) {
    uploadError.value = `Este(s) arquivo(s) já está(ão) na fila: ${result.duplicates.join(', ')}.`
  } else {
    uploadError.value = null
  }
  // Anything successfully imported goes straight to the editor (spec 3.1: file
  // loaded → configuring, first file becomes the active job).
  if (result.added.length) {
    setActiveJob(result.added[0].id)
    emit('openImage')
  }
}

async function pickFiles(): Promise<void> {
  if (!hasNativeApi) {
    uploadError.value = 'Seleção de arquivos disponível apenas no aplicativo desktop.'
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFiles()
    if (result.canceled) return
    reportResult(await addFiles(result.files, DEFAULT_MODEL))
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : 'Falha ao selecionar arquivos.'
  } finally {
    uploading.value = false
  }
}

async function pickFolder(): Promise<void> {
  if (!hasNativeApi) {
    uploadError.value = 'Seleção de pasta disponível apenas no aplicativo desktop.'
    return
  }
  uploading.value = true
  try {
    const result = await api.selectFolder()
    if (result.canceled) return
    if (result.files.length === 0) {
      uploadError.value = 'Nenhuma imagem compatível foi encontrada nessa pasta.'
      return
    }
    reportResult(await addFiles(result.files, DEFAULT_MODEL))
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : 'Falha ao selecionar a pasta.'
  } finally {
    uploading.value = false
  }
}

async function handleFilesDropped(dropped: File[]): Promise<void> {
  if (!hasNativeApi) {
    uploadError.value = 'Arraste e solte disponível apenas no aplicativo desktop.'
    return
  }
  uploading.value = true
  try {
    const described = await Promise.all(
      dropped.map((file) => api.statPath(api.getPathForFile(file)))
    )
    reportResult(
      await addFiles(
        described.filter((d) => d !== null),
        DEFAULT_MODEL
      )
    )
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : 'Falha ao importar os arquivos.'
  } finally {
    uploading.value = false
  }
}

// Spec 3.1: "Colar imagem (Ctrl+V) → verifica clipboard → salva temp file → cria Job".
async function handlePaste(event: ClipboardEvent): Promise<void> {
  if (!hasNativeApi) return
  const item = Array.from(event.clipboardData?.items ?? []).find((i) => i.type.startsWith('image/'))
  if (!item) return
  const blob = item.getAsFile()
  if (!blob) return
  try {
    const buffer = await blob.arrayBuffer()
    const ext = item.type === 'image/jpeg' ? '.jpg' : item.type === 'image/webp' ? '.webp' : '.png'
    const path = await api.saveTempImage(buffer, ext)
    const described = await api.statPath(path)
    if (described) reportResult(await addFiles([described], DEFAULT_MODEL))
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : 'Falha ao colar a imagem.'
  }
}

onMounted(() => window.addEventListener('paste', handlePaste))
onUnmounted(() => window.removeEventListener('paste', handlePaste))

function openImage(id?: string): void {
  if (id) setActiveJob(id)
  emit('openImage')
}
</script>

<template>
  <div class="home-view">
    <TopBar title="Home" />

    <div class="home-content">
      <UploadZone
        :error="uploadError"
        :loading="uploading"
        @pick-files="pickFiles"
        @pick-folder="pickFolder"
        @files-dropped="handleFilesDropped"
      />

      <section class="queue-section">
        <div class="queue-header">
          <div class="queue-heading">
            <div class="queue-icon"><ListChecks :size="16" /></div>
            <div>
              <h2 class="queue-title">Fila ({{ fileCount }})</h2>
              <p class="queue-subtitle">
                {{ fileCount }} arquivo{{ fileCount === 1 ? '' : 's' }} · {{ statusLabel }}
              </p>
            </div>
          </div>
          <div class="queue-actions">
            <button class="btn-ghost" type="button" :disabled="!jobs.length" @click="clearQueue">
              <Trash2 :size="15" /> Limpar fila
            </button>
            <button class="btn-outline" type="button" :disabled="!jobs.length" @click="openImage()">
              Ir para Imagem <ChevronDown :size="14" />
            </button>
          </div>
        </div>

        <div v-if="jobs.length" class="queue-list">
          <FileQueueItem
            v-for="(j, index) in jobs"
            :key="j.id"
            :job="j"
            :style="{ animationDelay: Math.min(index, 10) * 25 + 'ms' }"
            @remove="removeJob"
            @click="openImage(j.id)"
          />
        </div>
        <p v-else class="queue-empty">
          Nenhum arquivo na fila. Arraste algo acima, cole com Ctrl+V, ou clique para importar.
        </p>
      </section>

      <SummaryCards
        :file-count="fileCount"
        :total-size-label="totalSizeLabel"
        :status-label="statusLabel"
        quality-label="Pronto para melhorar"
      />
    </div>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

.home-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.queue-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.queue-heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.queue-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.queue-title {
  font-size: 15px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.queue-subtitle {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.queue-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.btn-ghost {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--surface-border-soft);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  cursor: pointer;
}

.btn-ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--text-primary);
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.btn-outline:hover:not(:disabled) {
  background: var(--surface-3);
}

.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.queue-empty {
  font-size: var(--fs-label);
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
  border: 1px dashed var(--surface-border-soft);
  border-radius: var(--radius-md);
}
</style>

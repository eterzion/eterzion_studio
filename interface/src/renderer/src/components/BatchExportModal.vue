<script setup lang="ts">
import { ref, computed } from 'vue'
import { X, Loader2, CheckCircle2, AlertCircle, FolderOpen } from '@lucide/vue'
import type { Job, ExportOptions } from '../store/jobs'
import { exportOne } from '../store/jobs'
import { api, hasNativeApi } from '../api'
import AppSelect from './AppSelect.vue'

const formatOptions = [
  { value: 'png', label: '.png' },
  { value: 'jpg', label: '.jpg' },
  { value: 'webp', label: '.webp' }
]

const props = defineProps<{
  jobs: Job[]
}>()

const emit = defineEmits<{
  close: []
}>()

const selected = ref(new Set(props.jobs.map((j) => j.id)))
const format = ref<'png' | 'jpg' | 'webp'>('png')
const outputDir = ref<string | null>(null)
const running = ref(false)
const doneCount = ref(0)
const results = ref<{ job: Job; ok: boolean; error?: string }[]>([])

const selectedJobs = computed(() => props.jobs.filter((j) => selected.value.has(j.id)))
const finished = computed(
  () => results.value.length === selectedJobs.value.length && selectedJobs.value.length > 0
)
const successCount = computed(() => results.value.filter((r) => r.ok).length)
const failureCount = computed(() => results.value.filter((r) => !r.ok).length)

function toggle(id: string): void {
  if (selected.value.has(id)) selected.value.delete(id)
  else selected.value.add(id)
}

async function pickFolder(): Promise<void> {
  if (!hasNativeApi) return
  const folder = await api.selectOutputFolder(outputDir.value ?? undefined)
  if (folder) outputDir.value = folder
}

async function run(): Promise<void> {
  if (running.value || !selectedJobs.value.length) return
  running.value = true
  results.value = []
  doneCount.value = 0
  const options: ExportOptions = {
    format: format.value,
    quality: 90,
    outputDir: outputDir.value,
    filename: null,
    conflict: 'rename'
  }
  for (const job of selectedJobs.value) {
    const result = await exportOne(job, options)
    results.value.push({ job, ok: result.ok, error: result.error })
    doneCount.value++
  }
  running.value = false
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>Exportar tudo</h3>
        <button class="icon-btn" type="button" @click="emit('close')"><X :size="18" /></button>
      </div>

      <div v-if="!finished" class="modal-body">
        <p class="modal-hint">Selecione quais imagens concluídas exportar:</p>
        <div class="job-list">
          <label v-for="job in jobs" :key="job.id" class="job-row">
            <input type="checkbox" :checked="selected.has(job.id)" @change="toggle(job.id)" />
            <span class="job-name">{{ job.fileName }}</span>
          </label>
        </div>

        <div class="field-row">
          <label class="field-label">Formato</label>
          <AppSelect
            :model-value="format"
            :options="formatOptions"
            @update:model-value="(v) => (format = v as 'png' | 'jpg' | 'webp')"
          />
        </div>

        <div class="field-row">
          <label class="field-label">Destino</label>
          <div class="folder-row">
            <input
              class="select folder-input"
              type="text"
              :value="outputDir ?? 'Mesma pasta do original'"
              readonly
            />
            <button class="folder-btn" type="button" @click="pickFolder">
              <FolderOpen :size="15" />
            </button>
          </div>
        </div>

        <p v-if="running" class="progress-text">
          <Loader2 :size="14" class="spin" /> Exportando {{ doneCount }} de
          {{ selectedJobs.length }}
        </p>

        <button
          class="btn-primary"
          type="button"
          :disabled="running || !selectedJobs.length"
          @click="run"
        >
          Exportar {{ selectedJobs.length }} imagem{{ selectedJobs.length === 1 ? '' : 's' }}
        </button>
      </div>

      <div v-else class="modal-body">
        <p class="report-summary">
          {{ successCount }} exportado{{ successCount === 1 ? '' : 's' }} com sucesso
          <template v-if="failureCount">, {{ failureCount }} com erro</template>.
        </p>
        <div class="job-list">
          <div v-for="r in results" :key="r.job.id" class="report-row">
            <component
              :is="r.ok ? CheckCircle2 : AlertCircle"
              :size="14"
              :class="r.ok ? 'ok' : 'fail'"
            />
            <span class="job-name">{{ r.job.fileName }}</span>
            <span v-if="!r.ok" class="report-error">{{ r.error }}</span>
          </div>
        </div>
        <button class="btn-primary" type="button" @click="emit('close')">Fechar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal {
  width: 420px;
  max-width: 92vw;
  max-height: 80vh;
  overflow-y: auto;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--surface-border-soft);
}

.modal-header h3 {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.icon-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
}

.modal-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.modal-hint {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
}

.job-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--fs-label);
  color: var(--text-primary);
  cursor: pointer;
}

.job-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
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

.progress-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.report-summary {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.report-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
}

.ok {
  color: var(--color-success);
}

.fail {
  color: var(--color-danger);
}

.report-error {
  color: var(--color-danger);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

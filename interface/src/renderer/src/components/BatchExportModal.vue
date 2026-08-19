<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, CheckCircle2, AlertCircle, FolderOpen } from '@lucide/vue'
import type { Job, ExportOptions } from '../store/jobs'
import { exportOne } from '../store/jobs'
import { api, hasNativeApi } from '../services/native'
import AppSelect from './AppSelect.vue'
import AppButton from './atoms/AppButton.vue'
import AppSpinner from './atoms/AppSpinner.vue'

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

const { t } = useI18n()
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>{{ t('actions.exportAll') }}</h3>
        <AppButton variant="ghost" icon-only @click="emit('close')">
          <template #icon><X :size="18" /></template>
        </AppButton>
      </div>

      <div v-if="!finished" class="modal-body">
        <p class="modal-hint">{{ t('misc.selectCompleted') }}</p>
        <div class="job-list">
          <label v-for="job in jobs" :key="job.id" class="job-row">
            <input type="checkbox" :checked="selected.has(job.id)" @change="toggle(job.id)" />
            <span class="job-name">{{ job.fileName }}</span>
          </label>
        </div>

        <div class="field-row">
          <label class="field-label">{{ t('imageEditor.format') }}</label>
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
            <AppButton variant="secondary" icon-only @click="pickFolder">
              <template #icon><FolderOpen :size="15" /></template>
            </AppButton>
          </div>
        </div>

        <p v-if="running" class="progress-text">
          <AppSpinner :size="14" /> Exportando {{ doneCount }} de
          {{ selectedJobs.length }}
        </p>

        <AppButton
          variant="primary"
          size="lg"
          class="w-full"
          :disabled="running || !selectedJobs.length"
          @click="run"
        >
          Exportar {{ selectedJobs.length }} imagem{{ selectedJobs.length === 1 ? '' : 's' }}
        </AppButton>
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
        <AppButton variant="primary" size="lg" class="w-full" @click="emit('close')"
          >Fechar</AppButton
        >
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
  gap: var(--space-1-5);
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
  gap: var(--space-1-5);
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

.progress-text {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.report-summary {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.report-row {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
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
</style>

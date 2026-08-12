<script setup lang="ts">
import { computed } from 'vue'
import TopBar from '../components/TopBar.vue'
import FileQueueItem from '../components/FileQueueItem.vue'
import SummaryCards from '../components/SummaryCards.vue'
import {
  Image,
  Film,
  Headphones,
  Rocket,
  ArrowRight,
  Trash2,
  ChevronDown,
  FolderOpen,
  Info,
  ExternalLink
} from '@lucide/vue'
import { queueState, removeJob, setActiveJob } from '../store/jobs'
import type { NavKey } from '../types'

const emit = defineEmits<{
  navigate: [key: NavKey]
}>()

// Upload lives on each category tab now (Imagem/Vídeo/Áudio/Otimizar each
// own their intake directly) — Home keeps the launcher cards plus the
// original image queue/stats, just without the drop zone that used to sit
// above them. Each card owns a fixed accent (independent of the user's
// chosen theme accent) so the grid reads as a set of distinct destinations.
const CATEGORIES: {
  key: NavKey
  label: string
  description: string
  icon: unknown
  tint: string
}[] = [
  {
    key: 'imagem',
    label: 'Imagem',
    description: 'Aumente a resolução de fotos e ilustrações com IA.',
    icon: Image,
    tint: '#3b82f6'
  },
  {
    key: 'video',
    label: 'Vídeo',
    description: 'Aumente a resolução de vídeos preservando fps e áudio.',
    icon: Film,
    tint: '#a855f7'
  },
  {
    key: 'audio',
    label: 'Áudio',
    description: 'Reduza ruído, normalize volume e melhore a clareza da voz ou música.',
    icon: Headphones,
    tint: '#06b6d4'
  },
  {
    key: 'otimizar',
    label: 'Otimizar',
    description: 'Comprima ou converta imagens, vídeos e áudios sem IA.',
    icon: Rocket,
    tint: '#22c55e'
  }
]

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
const statusTone = computed(() => {
  if (jobs.value.some((j) => j.status === 'processing')) return 'warning'
  if (jobs.value.length && jobs.value.every((j) => j.status === 'done')) return 'success'
  if (jobs.value.some((j) => j.status === 'error')) return 'danger'
  return 'primary'
})

function clearQueue(): void {
  for (const j of [...jobs.value]) removeJob(j.id)
}

function openImage(id?: string): void {
  if (id) setActiveJob(id)
  emit('navigate', 'imagem')
}
</script>

<template>
  <div class="home-view">
    <TopBar title="Home" />

    <div class="home-content">
      <div class="intro-group">
        <p class="intro">O que você quer melhorar hoje?</p>
        <p class="intro-subtitle">Escolha uma opção abaixo para melhorar sua mídia com IA.</p>
      </div>

      <div class="category-grid">
        <button
          v-for="category in CATEGORIES"
          :key="category.key"
          class="category-card"
          type="button"
          :style="{ '--tint': category.tint }"
          @click="emit('navigate', category.key)"
        >
          <div class="category-icon">
            <component :is="category.icon" :size="22" />
          </div>
          <div class="category-text">
            <span class="category-label">{{ category.label }}</span>
            <span class="category-description">{{ category.description }}</span>
          </div>
          <span class="category-arrow"><ArrowRight :size="16" /></span>
        </button>
      </div>

      <section class="queue-section">
        <div class="queue-header">
          <div class="queue-heading">
            <div class="queue-icon"><FolderOpen :size="18" /></div>
            <div>
              <h2 class="queue-title">Fila de processamento ({{ fileCount }})</h2>
              <p class="queue-subtitle">
                {{ fileCount }} arquivo{{ fileCount === 1 ? '' : 's' }}
                <span class="queue-dot">·</span>
                <span class="queue-status" :class="`tone-${statusTone}`">{{ statusLabel }}</span>
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
          Nenhum arquivo na fila. Importe algo na aba Imagem para começar.
        </p>
      </section>

      <SummaryCards
        :file-count="fileCount"
        :total-size-label="totalSizeLabel"
        :status-label="statusLabel"
        quality-label="Pronto para melhorar"
      />

      <div class="tip-bar">
        <div class="tip-icon"><Info :size="16" /></div>
        <p class="tip-text">
          <strong>Dica:</strong> use configurações otimizadas para resultados ainda melhores e
          mais rápidos.
        </p>
        <button class="btn-outline tip-btn" type="button" @click="emit('navigate', 'configuracoes')">
          Ver configurações <ExternalLink :size="14" />
        </button>
      </div>
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

.intro-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.intro {
  font-size: 22px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.intro-subtitle {
  font-size: var(--fs-label);
  color: var(--text-tertiary);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.category-card {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--tint) 14%, var(--surface-1)) 0%,
    var(--surface-1) 75%
  );
  border: 1px solid color-mix(in srgb, var(--tint) 26%, var(--surface-border-soft));
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.category-card::after {
  content: '';
  position: absolute;
  inset: auto -30% -60% auto;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--tint) 22%, transparent), transparent 70%);
  pointer-events: none;
}

.category-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--tint) 45%, var(--surface-border-soft));
  box-shadow: var(--shadow-sm);
}

.category-card:focus-visible {
  outline: 2px solid var(--tint);
  outline-offset: -2px;
}

.category-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--tint);
  background: color-mix(in srgb, var(--tint) 20%, transparent);
  border: 1px solid color-mix(in srgb, var(--tint) 32%, transparent);
}

.category-text {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.category-label {
  font-size: 16px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.category-description {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  line-height: 1.4;
}

.category-arrow {
  position: relative;
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--tint);
  background: color-mix(in srgb, var(--tint) 16%, transparent);
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
  font-size: 16px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.queue-subtitle {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.queue-dot {
  margin: 0 4px;
  color: var(--text-tertiary);
}

.queue-status {
  font-weight: var(--fw-medium);
}

.queue-status.tone-primary {
  color: var(--color-primary);
}

.queue-status.tone-success {
  color: var(--color-success);
}

.queue-status.tone-warning {
  color: var(--color-warning);
}

.queue-status.tone-danger {
  color: var(--color-danger);
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

.tip-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: color-mix(in srgb, var(--color-primary) 8%, var(--surface-1));
  border: 1px solid color-mix(in srgb, var(--color-primary) 24%, var(--surface-border-soft));
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
}

.tip-icon {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.tip-text {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-label);
  color: var(--text-secondary);
}

.tip-text strong {
  color: var(--color-primary);
  font-weight: var(--fw-semibold);
}

.tip-btn {
  flex-shrink: 0;
}
</style>

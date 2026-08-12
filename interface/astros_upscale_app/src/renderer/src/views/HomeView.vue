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
  Layers,
  History,
  Settings,
  ArrowRight,
  Trash2,
  ChevronDown,
  ListChecks
} from '@lucide/vue'
import { queueState, removeJob, setActiveJob } from '../store/jobs'
import type { NavKey } from '../types'

const emit = defineEmits<{
  navigate: [key: NavKey]
}>()

// Upload lives on each category tab now (Imagem/Vídeo/Áudio/Otimizar each
// own their intake directly) — Home keeps the launcher cards plus the
// original image queue/stats, just without the drop zone that used to sit
// above them.
const CATEGORIES: { key: NavKey; label: string; description: string; icon: unknown }[] = [
  {
    key: 'imagem',
    label: 'Imagem',
    description: 'Aumente a resolução de fotos e ilustrações com IA.',
    icon: Image
  },
  {
    key: 'video',
    label: 'Vídeo',
    description: 'Aumente a resolução de vídeos preservando fps e áudio.',
    icon: Film
  },
  {
    key: 'audio',
    label: 'Áudio',
    description: 'Reduza ruído, normalize volume e melhore a clareza da voz ou música.',
    icon: Headphones
  },
  {
    key: 'otimizar',
    label: 'Otimizar',
    description: 'Comprima ou converta imagens, vídeos e áudios sem IA.',
    icon: Rocket
  },
  {
    key: 'modelos',
    label: 'Modelos',
    description: 'Instale, atualize ou remova os componentes de cada capacidade.',
    icon: Layers
  },
  {
    key: 'historico',
    label: 'Histórico',
    description: 'Veja os arquivos já processados anteriormente.',
    icon: History
  },
  {
    key: 'configuracoes',
    label: 'Configurações',
    description: 'Ajuste preferências gerais, tema e processamento.',
    icon: Settings
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
      <p class="intro">O que você quer melhorar hoje?</p>

      <div class="category-grid">
        <button
          v-for="category in CATEGORIES"
          :key="category.key"
          class="category-card"
          type="button"
          @click="emit('navigate', category.key)"
        >
          <div class="category-icon">
            <component :is="category.icon" :size="22" />
          </div>
          <div class="category-text">
            <span class="category-label">{{ category.label }}</span>
            <span class="category-description">{{ category.description }}</span>
          </div>
          <ArrowRight :size="18" class="category-arrow" />
        </button>
      </div>

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
          Nenhum arquivo na fila. Importe algo na aba Imagem para começar.
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

.intro {
  font-size: var(--fs-h3, 1.1rem);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.category-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.category-card:hover {
  background: var(--surface-2);
  border-color: var(--color-primary-soft);
}

.category-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.category-icon {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.category-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.category-description {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.category-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
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

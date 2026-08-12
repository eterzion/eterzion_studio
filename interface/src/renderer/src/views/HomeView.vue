<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, FolderOpen, Trash2 } from '@lucide/vue'
import CategoryIcon from '../components/CategoryIcon.vue'
import FileQueueItem from '../components/FileQueueItem.vue'
import SummaryCards from '../components/SummaryCards.vue'
import { queueState, removeJob, setActiveJob } from '../store/jobs'
import type { NavKey } from '../types'

const emit = defineEmits<{ navigate: [key: NavKey] }>()
type CategoryVariant = 'imagem' | 'video' | 'audio' | 'otimizar' | 'converter'
const CATEGORIES: { key: NavKey; label: string; variant: CategoryVariant; tint: string }[] = [
  { key: 'imagem', label: 'Image', variant: 'imagem', tint: '#1688ff' },
  { key: 'video', label: 'Video', variant: 'video', tint: '#bd24ff' },
  { key: 'audio', label: 'Audio', variant: 'audio', tint: '#20dced' },
  { key: 'otimizar', label: 'Otimizar', variant: 'otimizar', tint: '#59ef23' },
  { key: 'converter', label: 'Converter', variant: 'converter', tint: '#ff9d00' }
]
const jobs = computed(() => queueState.jobs)
const fileCount = computed(() => jobs.value.length)
const totalSizeLabel = computed(
  () =>
    `${(jobs.value.reduce((sum, job) => sum + job.sourceMeta.sizeBytes, 0) / (1024 * 1024)).toFixed(2)} MB`
)
const statusLabel = computed(() => {
  if (jobs.value.some((job) => job.status === 'processing')) return 'Processando'
  if (jobs.value.length && jobs.value.every((job) => job.status === 'done')) return 'Concluído'
  if (jobs.value.some((job) => job.status === 'error')) return 'Com erros'
  if (jobs.value.some((job) => job.status === 'queued')) return 'Na fila'
  if (jobs.value.length) return 'Configurando'
  return 'Vazio'
})
function clearQueue(): void {
  for (const job of [...jobs.value]) removeJob(job.id)
}
function openImage(id?: string): void {
  if (id) setActiveJob(id)
  emit('navigate', 'imagem')
}
</script>

<template>
  <main class="home-view">
    <div class="home-panel">
      <h1 class="home-title">What would you like to improve today?</h1>
      <div class="category-grid">
        <button
          v-for="category in CATEGORIES"
          :key="category.key"
          class="category-card"
          type="button"
          :style="{ '--tint': category.tint }"
          :aria-label="`Abrir ${category.label}`"
          @click="emit('navigate', category.key)"
        >
          <span class="category-label">{{ category.label }}</span>
          <span class="category-art" aria-hidden="true"
            ><CategoryIcon :variant="category.variant" :tint="category.tint"
          /></span>
          <span class="category-arrow" aria-hidden="true"
            ><ArrowRight :size="24" :stroke-width="2.8"
          /></span>
        </button>
      </div>
      <section class="queue-section" aria-labelledby="queue-title">
        <header class="queue-header">
          <div class="queue-heading">
            <div class="queue-icon"><FolderOpen :size="22" :stroke-width="1.8" /></div>
            <div>
              <h2 id="queue-title" class="queue-title">Fila de processamento</h2>
              <p class="queue-subtitle">
                <span class="queue-dot" />{{ fileCount }} arquivo{{ fileCount === 1 ? '' : 's' }}
              </p>
            </div>
          </div>
          <button class="clear-button" type="button" :disabled="!jobs.length" @click="clearQueue">
            <Trash2 :size="17" :stroke-width="1.8" /> Limpar fila
          </button>
        </header>
        <div v-if="jobs.length" class="queue-list">
          <FileQueueItem
            v-for="(job, index) in jobs"
            :key="job.id"
            :job="job"
            :style="{ animationDelay: Math.min(index, 10) * 25 + 'ms' }"
            @remove="removeJob"
            @click="openImage(job.id)"
          />
        </div>
      </section>
      <SummaryCards
        :file-count="fileCount"
        :total-size-label="totalSizeLabel"
        :status-label="statusLabel"
        quality-label="Pronto para melhorar"
      />
    </div>
  </main>
</template>

<style scoped>
/* FR-004 exception: this screen's category-card system (color-mix(), radial gradients,
   layered box-shadows, clamp()-based responsive type, all driven by a per-card --tint CSS
   custom property) is genuinely complex, bespoke, and — per research.md Audit (b) — uses
   one-off color literals deliberately excluded from tokenization (none repeat elsewhere).
   Converting it to Tailwind's arbitrary-value syntax would trade one form of literal values
   for another with no reduction in duplication and real risk of a gradient/shadow typo, so
   it stays hand-written. */
.home-view {
  flex: 1;
  min-width: 0;
  height: 100vh;
  padding: 6px;
  overflow: auto;
  color: #f7f8fc;
  background: #020910;
}
.home-panel {
  min-height: calc(100vh - 12px);
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: clamp(19px, 1.9vw, 24px);
  overflow: hidden;
  border: none;
  border-radius: 11px;
}
.home-title {
  margin: 0 0 clamp(15px, 1.6vw, 20px) 3px;
  color: #f8f9fb;
  font-size: clamp(24px, 2.15vw, 30px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.45px;
}
.category-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(8px, 0.9vw, 12px);
  margin-bottom: 16px;
}
.category-card {
  --card-bg: color-mix(in srgb, var(--tint) 8%, #030d18);
  position: relative;
  display: flex;
  min-width: 0;
  height: clamp(215px, 28vh, 270px);
  padding: 16px 17px;
  overflow: hidden;
  color: #fff;
  text-align: left;
  cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--tint) 82%, transparent);
  border-radius: 11px;
  background:
    radial-gradient(
      circle at 50% 45%,
      color-mix(in srgb, var(--tint) 13%, transparent),
      transparent 47%
    ),
    linear-gradient(155deg, var(--card-bg), #030b15 76%);
  box-shadow: inset 0 0 35px color-mix(in srgb, var(--tint) 3%, transparent);
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    border-color 180ms ease;
}
.category-card:hover {
  z-index: 1;
  transform: translateY(-2px);
  border-color: var(--tint);
  box-shadow: 0 7px 24px color-mix(in srgb, var(--tint) 15%, transparent);
}
.category-card:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 3px;
}
.category-label {
  position: relative;
  z-index: 2;
  font-size: clamp(17px, 1.5vw, 20px);
  font-weight: 650;
  line-height: 1.1;
  letter-spacing: -0.4px;
}
.category-art {
  position: absolute;
  inset: 44px 5px 53px;
  display: block;
}
.category-arrow {
  position: absolute;
  z-index: 2;
  left: 50%;
  bottom: 8px;
  display: flex;
  width: 40px;
  height: 44px;
  align-items: center;
  justify-content: center;
  color: #fff;
  border: 1.5px solid var(--tint);
  border-radius: 50%;
  background: color-mix(in srgb, var(--tint) 8%, #04101b);
  box-shadow:
    0 0 10px color-mix(in srgb, var(--tint) 55%, transparent),
    inset 0 0 9px color-mix(in srgb, var(--tint) 11%, transparent);
  transform: translateX(-50%);
  transition:
    transform 180ms ease,
    background 180ms ease;
}
.category-card:hover .category-arrow {
  background: color-mix(in srgb, var(--tint) 22%, #04101b);
  transform: translateX(-50%) scale(1.04);
}
.queue-section {
  margin-bottom: 16px;
  overflow: hidden;
  border: 1px solid #10263b;
  border-radius: 11px;
  background: rgba(3, 15, 27, 0.72);
}
.queue-header {
  display: flex;
  min-height: 88px;
  align-items: center;
  justify-content: space-between;
  gap: 11px;
  padding: 10px 12px;
}
.queue-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
}
.queue-icon {
  display: flex;
  width: 50px;
  height: 52px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: #1789ff;
  border-radius: 11px;
  background: linear-gradient(145deg, #0a2b57, #071a3b);
  box-shadow: inset 0 0 18px rgba(22, 136, 255, 0.08);
}
.queue-title {
  margin: 0;
  color: #f6f7fa;
  font-size: clamp(16px, 1.35vw, 19px);
  font-weight: 650;
  line-height: 1.15;
}
.queue-subtitle {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 5px 0 0;
  color: #d7dce5;
  font-size: 13px;
  line-height: 1;
}
.queue-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #087bff;
  box-shadow: 0 0 7px rgba(8, 123, 255, 0.45);
}
.clear-button {
  display: flex;
  min-width: 144px;
  height: 52px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #f3f3f5;
  font-size: 13px;
  font-weight: 450;
  cursor: pointer;
  border: 1px solid #10243a;
  border-radius: 11px;
  background: rgba(3, 13, 24, 0.35);
  transition:
    border-color 160ms ease,
    background 160ms ease;
}
.clear-button:hover:not(:disabled) {
  border-color: #28405c;
  background: #071524;
}
.clear-button:disabled {
  cursor: default;
  opacity: 0.82;
}
.queue-list {
  display: flex;
  max-height: 232px;
  flex-direction: column;
  gap: 6px;
  padding: 0 15px 15px;
  overflow-y: auto;
}
@media (max-width: 1000px) {
  .category-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .category-card {
    height: 245px;
  }
}
@media (max-width: 760px) {
  .home-view {
    padding: 6px;
  }
  .home-panel {
    min-height: calc(100vh - 12px);
    padding: 17px 12px;
    border-radius: 11px;
  }
  .home-title {
    margin-left: 0;
  }
  .category-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .category-card {
    height: 232px;
    padding: 14px;
  }
  .queue-header {
    align-items: stretch;
    flex-direction: column;
  }
  .clear-button {
    width: 100%;
    height: 44px;
  }
}
@media (max-width: 470px) {
  .category-grid {
    grid-template-columns: 1fr;
  }
  .category-card {
    height: 245px;
  }
  .queue-heading {
    gap: 12px;
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight, FolderOpen, Trash2 } from '@lucide/vue'
import CategoryIcon from '../components/CategoryIcon.vue'
import FileQueueItem from '../components/FileQueueItem.vue'
import SummaryCards from '../components/SummaryCards.vue'
import { queueState, removeJob, setActiveJob } from '../store/jobs'
import type { NavKey } from '../types'

const { t } = useI18n()
const emit = defineEmits<{ navigate: [key: NavKey] }>()
type CategoryVariant = 'imagem' | 'video' | 'audio'
const CATEGORIES = computed<
  { key: NavKey; label: string; variant: CategoryVariant; tint: string }[]
>(() => [
  // The same four accents the modules themselves use (theme.css --accent-*),
  // so a card and the screen it opens are literally the same colour.
  { key: 'imagem', label: t('nav.image'), variant: 'imagem', tint: 'var(--accent-image)' },
  { key: 'video', label: t('nav.video'), variant: 'video', tint: 'var(--accent-video)' },
  { key: 'audio', label: t('nav.audio'), variant: 'audio', tint: 'var(--accent-audio)' }
])
const jobs = computed(() => queueState.jobs)
const fileCount = computed(() => jobs.value.length)
const totalSizeLabel = computed(
  () =>
    `${(jobs.value.reduce((sum, job) => sum + job.sourceMeta.sizeBytes, 0) / (1024 * 1024)).toFixed(2)} MB`
)
const statusLabel = computed(() => {
  if (jobs.value.some((job) => job.status === 'processing')) return t('home.status.processing')
  if (jobs.value.length && jobs.value.every((job) => job.status === 'done'))
    return t('home.status.done')
  if (jobs.value.some((job) => job.status === 'error')) return t('home.status.errors')
  if (jobs.value.some((job) => job.status === 'queued')) return t('home.status.queued')
  if (jobs.value.length) return t('home.status.configuring')
  return t('home.status.empty')
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
      <h1 class="home-title">{{ t('home.title') }}</h1>
      <div class="category-grid">
        <button
          v-for="category in CATEGORIES"
          :key="category.key"
          class="category-card"
          type="button"
          :style="{ '--tint': category.tint }"
          :aria-label="t('home.openAria', { label: category.label })"
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
            <div class="queue-icon icon-chip"><FolderOpen :size="22" :stroke-width="1.8" /></div>
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
  color: var(--text-primary);
  background: var(--surface-0);
}
.home-panel {
  /* A flex column so the queue can absorb the leftover height — otherwise the
     content stacks at the top and the bottom third of the screen sits empty. */
  display: flex;
  flex-direction: column;
  height: calc(100vh - 12px);
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: clamp(19px, 1.9vw, 24px);
  overflow: hidden;
  border: none;
  border-radius: 11px;
}
.home-title {
  margin: 0 0 clamp(15px, 1.6vw, 20px) 3px;
  color: var(--text-primary);
  font-size: clamp(24px, 2.15vw, 30px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.45px;
}
.category-grid {
  display: grid;
  /* One column per card, so the row always ends where the panel does. The count
     is tied to the number of categories — it was still 4 after Exportar was
     removed, which is what left a card-sized hole on the right. */
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(8px, 0.9vw, 12px);
  margin-bottom: 16px;
}
.category-card {
  --card-bg: color-mix(in srgb, var(--tint) 8%, var(--surface-1));
  position: relative;
  display: flex;
  min-width: 0;
  height: clamp(215px, 28vh, 270px);
  padding: 16px 17px;
  overflow: hidden;
  color: var(--text-primary);
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
    linear-gradient(155deg, var(--card-bg), var(--surface-0) 76%);
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
  color: var(--text-primary);
  border: 1.5px solid var(--tint);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--tint) 8%, var(--surface-2));
  box-shadow:
    0 0 10px color-mix(in srgb, var(--tint) 55%, transparent),
    inset 0 0 9px color-mix(in srgb, var(--tint) 11%, transparent);
  transform: translateX(-50%);
  transition:
    transform 180ms ease,
    background 180ms ease;
}
.category-card:hover .category-arrow {
  background: color-mix(in srgb, var(--tint) 22%, var(--surface-2));
  transform: translateX(-50%) scale(1.04);
}
.queue-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
  overflow: hidden;
  border: 1px solid var(--surface-border);
  border-radius: 11px;
  background: var(--surface-1);
}
.queue-header {
  display: flex;
  /* Trimmed along with the icon below: the cards now span the full row and are
     correspondingly taller, so the queue's own chrome gives back the height. */
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 11px;
  padding: 8px 12px;
}
.queue-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
}
.queue-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
}
.queue-title {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(16px, 1.35vw, 19px);
  font-weight: 650;
  line-height: 1.15;
}
.queue-subtitle {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1;
}
.queue-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  box-shadow: none;
}
.clear-button {
  display: flex;
  min-width: 144px;
  height: 52px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 450;
  cursor: pointer;
  border: 1px solid var(--surface-border);
  border-radius: 11px;
  background: var(--surface-2);
  transition:
    border-color 160ms ease,
    background 160ms ease;
}
.clear-button:hover:not(:disabled) {
  border-color: var(--surface-border);
  background: var(--surface-3);
}
.clear-button:disabled {
  cursor: default;
  opacity: 0.82;
}
.queue-list {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 6px;
  padding: 0 12px 12px;
  overflow-y: auto;
}
@media (max-width: 1000px) {
  /* Still three across — only the height gives way, so the row stays full. */
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

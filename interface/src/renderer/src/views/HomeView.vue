<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowRight, FolderOpen, Trash2 } from '@lucide/vue'
import CategoryIcon from '../components/CategoryIcon.vue'
import FileQueueItem from '../components/FileQueueItem.vue'
import { setActiveJob } from '../store/jobs'
import {
  allEntries,
  clearAll,
  queueGroups,
  removeEntry,
  reorderEntry,
  canReorder,
  kindLabel,
  type MediaKind,
  type QueueEntry
} from '../store/mediaQueue'
import { videoQueue } from '../store/videoQueue'
import { audioQueue } from '../store/audioQueue'
import type { NavKey } from '../types'

const { t } = useI18n()
const emit = defineEmits<{ navigate: [key: NavKey] }>()
type CategoryVariant = 'imagem' | 'video' | 'audio' | 'compressao'
const CATEGORIES = computed<
  { key: NavKey; label: string; variant: CategoryVariant; tint: string }[]
>(() => [
  // The same four accents the modules themselves use (theme.css --accent-*),
  // so a card and the screen it opens are literally the same colour.
  { key: 'imagem', label: t('nav.image'), variant: 'imagem', tint: 'var(--accent-image)' },
  { key: 'video', label: t('nav.video'), variant: 'video', tint: 'var(--accent-video)' },
  { key: 'audio', label: t('nav.audio'), variant: 'audio', tint: 'var(--accent-audio)' },
  {
    key: 'compressao',
    label: t('nav.compression'),
    variant: 'compressao',
    tint: 'var(--accent-compression)'
  }
])
// All three queues, not just images: videos and audio were simply absent from
// this list before, because it read store/jobs.ts and that store only ever held
// images.
const jobs = allEntries
const fileCount = computed(() => jobs.value.length)
function clearQueue(): void {
  clearAll()
}

const NAV_FOR_KIND: Record<MediaKind, NavKey> = {
  image: 'imagem',
  video: 'video',
  audio: 'audio'
}

/** Open the item on the screen that owns it, and select it there — clicking a
 *  video used to land on the Imagem screen, which held none of these files. */
function openEntry(entry: QueueEntry): void {
  if (entry.kind === 'image') setActiveJob(entry.id)
  else if (entry.kind === 'video') videoQueue.activeId = entry.id
  else audioQueue.activeId = entry.id
  emit('navigate', NAV_FOR_KIND[entry.kind])
}

// ------------------------------- drag to reorder ------------------------------- //
//
// Plain HTML drag-and-drop rather than a library: the list is short, the drop
// target is a sibling row, and the whole interaction is three events.
//
// A drag is confined to one kind. Processing is serial within each screen, so
// moving a video above an image changes nothing that runs — offering the drop
// would promise an effect the app cannot deliver.

const dragging = ref<{ kind: MediaKind; index: number } | null>(null)
const dropTarget = ref<{ kind: MediaKind; index: number; after: boolean } | null>(null)

function onDragStart(event: DragEvent, kind: MediaKind, index: number): void {
  dragging.value = { kind, index }
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    // Firefox refuses to start a drag without data set.
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function onDragOver(event: DragEvent, kind: MediaKind, index: number, entry: QueueEntry): void {
  if (!dragging.value || dragging.value.kind !== kind || !canReorder(entry)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  // Which half of the row the cursor is on decides whether the item lands
  // before or after it — without this the last position is unreachable.
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  dropTarget.value = { kind, index, after: event.clientY > box.top + box.height / 2 }
}

function onDrop(kind: MediaKind): void {
  const from = dragging.value
  const to = dropTarget.value
  if (from && to && from.kind === kind && to.kind === kind) {
    let target = to.after ? to.index + 1 : to.index
    // Removing the dragged row first shifts everything after it up by one.
    if (from.index < target) target -= 1
    if (target !== from.index) reorderEntry(kind, from.index, target)
  }
  endDrag()
}

function endDrag(): void {
  dragging.value = null
  dropTarget.value = null
}

function rowClass(kind: MediaKind, index: number): Record<string, boolean> {
  const target = dropTarget.value
  return {
    dragging: dragging.value?.kind === kind && dragging.value.index === index,
    'drop-before': !!target && target.kind === kind && target.index === index && !target.after,
    'drop-after': !!target && target.kind === kind && target.index === index && target.after
  }
}
</script>

<template>
  <main class="home-view">
    <div class="home-panel">
      <h1 class="home-title">{{ t('home.title') }}</h1>
      <div class="category-grid" :style="{ '--categorias': CATEGORIES.length }">
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
              <h2 id="queue-title" class="queue-title">{{ t('queue.title') }}</h2>
              <p class="queue-subtitle">
                <!-- t(key, n) picks the plural form from the locale. The previous
                     `fileCount === 1 ? '' : 's'` only worked for languages whose
                     plural is "add an s" — Russian needs three forms, and
                     Japanese, Korean and Chinese need none. -->
                <span class="queue-dot" />{{ t('queue.fileCountLabel', fileCount) }}
              </p>
            </div>
          </div>
          <button class="clear-button" type="button" :disabled="!jobs.length" @click="clearQueue">
            <Trash2 :size="17" :stroke-width="1.8" /> {{ t('queue.clear') }}
          </button>
        </header>
        <div v-if="jobs.length" class="queue-list">
          <!-- Grouped by kind, and labelled once there is more than one group:
               a drag only travels within its own group, and an unexplained
               refusal to drop reads as a bug. -->
          <template v-for="group in queueGroups" :key="group.kind">
            <p v-if="queueGroups.length > 1" class="queue-group-label">
              {{ kindLabel(group.kind) }}
            </p>
            <FileQueueItem
              v-for="(entry, index) in group.entries"
              :key="entry.id"
              :entry="entry"
              :class="rowClass(group.kind, index)"
              :style="{ animationDelay: Math.min(index, 10) * 25 + 'ms' }"
              :allow-reorder="canReorder(entry)"
              @dragstart="onDragStart($event, group.kind, index)"
              @dragover="onDragOver($event, group.kind, index, entry)"
              @drop="onDrop(group.kind)"
              @dragend="endDrag"
              @remove="removeEntry"
              @click="openEntry(entry)"
            />
          </template>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
/* Cartoes de categoria sem brilho: fundo chapado na mesma superficie dos cartoes de
   Configuracoes (`--surface-1`), sem gradiente radial, sem sombra tingida e sem o
   levantamento no hover. O tom de cada cartao (`--tint`, vindo de CATEGORIES) aparece
   so' na borda, no icone e na seta; o hover apenas acende a borda ate' o tom cheio.
   Continua CSS escrito a mao por causa do clamp() da tipografia e do color-mix() por
   cartao, mas o espacamento usa os tokens `--space-*` para acompanhar a densidade. */
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
  /* Uma coluna por cartão, para a linha terminar onde o painel termina. A
     contagem vem de `CATEGORIES.length` via variável CSS, e não de um número
     escrito aqui: já ficou em 4 depois de "Exportar" sair, deixando um buraco do
     tamanho de um cartão, e voltaria a divergir agora que a Central entrou. */
  grid-template-columns: repeat(var(--categorias, 3), minmax(0, 1fr));
  gap: clamp(8px, 0.9vw, 12px);
  margin-bottom: var(--space-3);
}
.category-card {
  position: relative;
  display: flex;
  min-width: 0;
  height: clamp(215px, 28vh, 270px);
  padding: var(--space-3);
  overflow: hidden;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  /* Em repouso o tom vem misturado com a borda neutra; no hover vai ao tom cheio.
     Sem sombra nem levantamento, essa distancia e' o que faz o hover ser notado. */
  border: 1px solid color-mix(in srgb, var(--tint) 45%, var(--surface-border));
  border-radius: 11px;
  background: var(--surface-1);
  transition: border-color 180ms ease;
}
.category-card:hover {
  border-color: var(--tint);
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
  bottom: var(--space-2);
  display: flex;
  width: 40px;
  height: 44px;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
  border: 1.5px solid var(--tint);
  border-radius: var(--radius-sm);
  /* Fundo tingido e chapado, como o `.icon-chip`: sem halo nem brilho interno. */
  background: color-mix(in srgb, var(--tint) 8%, var(--surface-2));
  transform: translateX(-50%);
}
.queue-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
.queue-group-label {
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding-top: var(--space-1);
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

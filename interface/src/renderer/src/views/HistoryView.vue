<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Search,
  History as HistoryIcon,
  CircleCheck,
  LoaderCircle,
  CircleX,
  Clock,
  EllipsisVertical,
  Eye,
  Download,
  RotateCcw,
  Info,
  Trash2,
  Image as ImageIcon
} from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import AppSelect from '../components/AppSelect.vue'
import AppButton from '../components/atoms/AppButton.vue'
import AppBadge from '../components/atoms/AppBadge.vue'
import {
  historyState,
  removeHistoryEntry,
  restoreHistoryEntry,
  setHistoryLimit,
  type HistoryEntry,
  type HistoryStatus
} from '../store/history'
import { addFiles, setActiveJob, queueState } from '../store/jobs'
import { settingsState } from '../store/settings'
import { api, hasNativeApi } from '../services/native'

const emit = defineEmits<{
  openImage: []
}>()

const search = ref('')
const statusFilter = ref<'all' | HistoryStatus>('all')
const contentTypeFilter = ref<'all' | string>('all')
const dateFilter = ref<'all' | 'today' | '7d' | '30d'>('all')
type SortKey = 'newest' | 'oldest' | 'res-desc' | 'res-asc' | 'size-desc' | 'size-asc'
const sortKey = ref<SortKey>('newest')
const openMenuId = ref<string | null>(null)
const expandedId = ref<string | null>(null)
const reuseError = ref<string | null>(null)

// Never exposes a model/checkpoint name — only the content-type label
// (FR-009/FR-063). Entries recorded before this field existed (pre-Unified
// Media Processing) only have the legacy `model` string; shown as
// "Arquivado" since it no longer maps to anything meaningful.
const CONTENT_TYPE_LABEL: Record<string, string> = {
  photo: 'Foto',
  anime_image: 'Anime/Ilustração',
  real_video: 'Vídeo real',
  anime_video: 'Vídeo anime',
  speech: 'Voz',
  music: 'Música'
}

function contentTypeLabel(entry: HistoryEntry): string {
  if (entry.contentType) return CONTENT_TYPE_LABEL[entry.contentType] ?? entry.contentType
  return 'Arquivado'
}

const undoEntry = ref<HistoryEntry | null>(null)
let undoTimer: ReturnType<typeof setTimeout> | undefined

const statusOptions = [
  { value: 'all', label: 'Todos os status' },
  { value: 'done', label: 'Concluído' },
  { value: 'processing', label: 'Processando' },
  { value: 'queued', label: 'Aguardando' },
  { value: 'error', label: 'Falhou' },
  { value: 'cancelled', label: 'Cancelado' }
]

const contentTypeOptions = computed(() => {
  const present = new Set<string>()
  for (const e of historyState.entries) if (e.contentType) present.add(e.contentType)
  return [
    { value: 'all', label: 'Todos os tipos' },
    ...Array.from(present).map((c) => ({ value: c, label: CONTENT_TYPE_LABEL[c] ?? c }))
  ]
})

const dateOptions = [
  { value: 'all', label: 'Qualquer data' },
  { value: 'today', label: 'Hoje' },
  { value: '7d', label: 'Últimos 7 dias' },
  { value: '30d', label: 'Últimos 30 dias' }
]

const sortOptions: { value: SortKey; label: string }[] = [
  { value: 'newest', label: 'Mais recentes' },
  { value: 'oldest', label: 'Mais antigos' },
  { value: 'res-desc', label: 'Maior resolução' },
  { value: 'res-asc', label: 'Menor resolução' },
  { value: 'size-desc', label: 'Maior tamanho' },
  { value: 'size-asc', label: 'Menor tamanho' }
]

function withinDateFilter(entry: HistoryEntry): boolean {
  if (dateFilter.value === 'all') return true
  const days = dateFilter.value === 'today' ? 1 : dateFilter.value === '7d' ? 7 : 30
  return Date.now() - entry.createdAt <= days * 24 * 60 * 60 * 1000
}

function resPixels(entry: HistoryEntry): number {
  return (entry.newWidth ?? 0) * (entry.newHeight ?? 0)
}

const filteredEntries = computed(() => {
  const q = search.value.trim().toLowerCase()
  let list = historyState.entries.filter((e) => {
    if (statusFilter.value !== 'all' && e.status !== statusFilter.value) return false
    if (contentTypeFilter.value !== 'all' && e.contentType !== contentTypeFilter.value) return false
    if (!withinDateFilter(e)) return false
    if (q && !e.fileName.toLowerCase().includes(q)) return false
    return true
  })
  list = [...list].sort((a, b) => {
    switch (sortKey.value) {
      case 'oldest':
        return a.createdAt - b.createdAt
      case 'res-desc':
        return resPixels(b) - resPixels(a)
      case 'res-asc':
        return resPixels(a) - resPixels(b)
      case 'size-desc':
        return (b.outputSizeBytes ?? 0) - (a.outputSizeBytes ?? 0)
      case 'size-asc':
        return (a.outputSizeBytes ?? 0) - (b.outputSizeBytes ?? 0)
      default:
        return b.createdAt - a.createdAt
    }
  })
  return list
})

const statusMeta: Record<
  HistoryStatus,
  { label: string; icon: unknown; tone: 'success' | 'info' | 'neutral' | 'danger' }
> = {
  done: { label: 'Concluído', icon: CircleCheck, tone: 'success' },
  processing: { label: 'Processando', icon: LoaderCircle, tone: 'info' },
  queued: { label: 'Aguardando', icon: Clock, tone: 'neutral' },
  error: { label: 'Falhou', icon: CircleX, tone: 'danger' },
  cancelled: { label: 'Cancelado', icon: CircleX, tone: 'neutral' }
}

function fmtDateTime(ts: number): string {
  return new Date(ts).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function fmtBytes(bytes: number | undefined): string {
  return bytes == null ? '—' : (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function toggleMenu(id: string): void {
  openMenuId.value = openMenuId.value === id ? null : id
}

function onDocClick(e: MouseEvent): void {
  if (!openMenuId.value) return
  const target = e.target as HTMLElement
  if (!target.closest('.menu-wrap')) openMenuId.value = null
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

function toggleDetails(id: string): void {
  expandedId.value = expandedId.value === id ? null : id
}

async function view(entry: HistoryEntry): Promise<void> {
  openMenuId.value = null
  if (!hasNativeApi || !entry.outputPath) return
  await api.openPath(entry.outputPath)
}

async function downloadAgain(entry: HistoryEntry): Promise<void> {
  openMenuId.value = null
  if (!hasNativeApi || !entry.outputPath) return
  await api.showItemInFolder(entry.outputPath)
}

async function reuseConfig(entry: HistoryEntry): Promise<void> {
  openMenuId.value = null
  reuseError.value = null
  if (!hasNativeApi) return
  if (entry.mediaType && entry.mediaType !== 'image') {
    reuseError.value = 'Reaproveitar configuração só está disponível para entradas de imagem.'
    return
  }
  if (!entry.scaleConfig?.contentType) {
    reuseError.value =
      'Esta configuração é de antes da atualização e não pode mais ser reaproveitada — configure novamente.'
    return
  }
  const described = await api.statPath(entry.sourcePath)
  if (!described || described.kind !== 'Imagem') {
    reuseError.value = `Arquivo original não encontrado: ${entry.sourcePath}`
    return
  }
  const result = await addFiles([described])
  const newJob = result.added[0]
  if (!newJob) {
    reuseError.value = 'Este arquivo já está na fila atual.'
    return
  }
  newJob.scaleConfig = { ...entry.scaleConfig }
  setActiveJob(newJob.id)
  emit('openImage')
}

function remove(entry: HistoryEntry): void {
  openMenuId.value = null
  removeHistoryEntry(entry.id)
  undoEntry.value = entry
  clearTimeout(undoTimer)
  undoTimer = setTimeout(() => (undoEntry.value = null), 6000)
}

function undoRemove(): void {
  if (!undoEntry.value) return
  restoreHistoryEntry(undoEntry.value)
  undoEntry.value = null
  clearTimeout(undoTimer)
}

function goProcess(): void {
  emit('openImage')
}

const limitInput = ref(settingsState.historyLimit)
function applyLimit(): void {
  setHistoryLimit(limitInput.value)
}
</script>

<template>
  <div class="history-view">
    <TopBar title="Histórico" />

    <div class="history-content">
      <div v-if="!queueState.jobs.length && !historyState.entries.length" class="empty-state">
        <HistoryIcon :size="40" />
        <h2>Nenhum processamento realizado</h2>
        <p>As imagens processadas aparecerão aqui.</p>
        <AppButton variant="primary" size="lg" @click="goProcess">Processar imagem</AppButton>
      </div>

      <template v-else>
        <div class="toolbar">
          <div class="search-bar">
            <Search :size="16" />
            <input v-model="search" type="text" placeholder="Buscar por nome ou modelo…" />
          </div>

          <div class="filters-row">
            <div class="filter-select-wrap">
              <AppSelect
                :model-value="statusFilter"
                :options="statusOptions"
                @update:model-value="(v) => (statusFilter = v as 'all' | HistoryStatus)"
              />
            </div>
            <div class="filter-select-wrap">
              <AppSelect
                :model-value="contentTypeFilter"
                :options="contentTypeOptions"
                @update:model-value="(v) => (contentTypeFilter = v as string)"
              />
            </div>
            <div class="filter-select-wrap">
              <AppSelect
                :model-value="dateFilter"
                :options="dateOptions"
                @update:model-value="(v) => (dateFilter = v as 'all' | 'today' | '7d' | '30d')"
              />
            </div>
            <div class="filter-select-wrap">
              <AppSelect
                :model-value="sortKey"
                :options="sortOptions"
                @update:model-value="(v) => (sortKey = v as SortKey)"
              />
            </div>
          </div>

          <div class="limit-control">
            <label for="history-limit">Limite de registros</label>
            <input
              id="history-limit"
              v-model.number="limitInput"
              type="number"
              min="1"
              max="2000"
              class="limit-input"
              @change="applyLimit"
            />
          </div>
        </div>

        <p v-if="reuseError" class="banner-error">{{ reuseError }}</p>

        <div v-if="!filteredEntries.length" class="empty-filtered">
          Nenhum item corresponde aos filtros atuais.
        </div>

        <div v-else class="history-list">
          <div
            v-for="(entry, index) in filteredEntries"
            :key="entry.id"
            class="history-card"
            :style="{ animationDelay: Math.min(index, 12) * 25 + 'ms' }"
          >
            <div class="card-main">
              <div class="thumb">
                <img v-if="entry.thumbnail" :src="entry.thumbnail" alt="" />
                <ImageIcon v-else :size="18" />
              </div>

              <div class="card-info">
                <div class="card-info-top">
                  <span class="file-name">{{ entry.fileName }}</span>
                  <AppBadge :tone="statusMeta[entry.status].tone">
                    <component
                      :is="statusMeta[entry.status].icon"
                      :size="12"
                      :class="{ 'animate-spin': entry.status === 'processing' }"
                    />
                    {{ statusMeta[entry.status].label }}
                  </AppBadge>
                </div>
                <div class="card-meta">
                  <span>{{ fmtDateTime(entry.createdAt) }}</span>
                  <span>·</span>
                  <span>{{ contentTypeLabel(entry) }}</span>
                  <span v-if="entry.scale">· {{ entry.scale }}x</span>
                </div>
                <div class="card-meta">
                  <span>{{ entry.originalWidth ?? '—' }}×{{ entry.originalHeight ?? '—' }}px</span>
                  <span>→</span>
                  <span>{{ entry.newWidth ?? '—' }}×{{ entry.newHeight ?? '—' }}px</span>
                  <span v-if="entry.outputSizeBytes">· {{ fmtBytes(entry.outputSizeBytes) }}</span>
                </div>
              </div>

              <div class="card-actions">
                <button
                  class="icon-action"
                  type="button"
                  title="Visualizar"
                  :disabled="!entry.outputPath"
                  @click="view(entry)"
                >
                  <Eye :size="15" />
                </button>
                <button
                  class="icon-action"
                  type="button"
                  title="Baixar novamente"
                  :disabled="!entry.outputPath"
                  @click="downloadAgain(entry)"
                >
                  <Download :size="15" />
                </button>
                <div class="menu-wrap">
                  <button
                    class="icon-action"
                    type="button"
                    title="Mais ações"
                    @click="toggleMenu(entry.id)"
                  >
                    <EllipsisVertical :size="15" />
                  </button>
                  <div v-if="openMenuId === entry.id" class="dropdown-menu">
                    <button type="button" @click="reuseConfig(entry)">
                      <RotateCcw :size="13" /> Reutilizar configurações
                    </button>
                    <button type="button" @click="toggleDetails(entry.id)">
                      <Info :size="13" /> Ver detalhes
                    </button>
                    <button type="button" class="danger" @click="remove(entry)">
                      <Trash2 :size="13" /> Excluir
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="expandedId === entry.id" class="card-details">
              <div class="detail-item">
                <dt>Origem</dt>
                <dd>{{ entry.sourcePath }}</dd>
              </div>
              <div class="detail-item">
                <dt>Saída</dt>
                <dd>{{ entry.outputPath ?? 'Ainda não exportado' }}</dd>
              </div>
              <div class="detail-item">
                <dt>Concluído em</dt>
                <dd>{{ entry.completedAt ? fmtDateTime(entry.completedAt) : '—' }}</dd>
              </div>
              <div v-if="entry.errorMessage" class="detail-item">
                <dt>Erro</dt>
                <dd>{{ entry.errorMessage }}</dd>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div v-if="undoEntry" class="undo-toast">
      <span>"{{ undoEntry.fileName }}" removido do histórico.</span>
      <button type="button" @click="undoRemove">Desfazer</button>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

.history-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  text-align: center;
  padding: var(--space-4);
}

.empty-state h2 {
  font-size: var(--fs-page-title);
  color: var(--text-primary);
  margin-top: var(--space-2);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  color: var(--text-tertiary);
  width: 260px;
  flex-shrink: 0;
}

.search-bar input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.search-bar input:focus {
  outline: none;
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* A wrapper div — not a bare "> *" selector — because Vue's scoped CSS doesn't
   attach the parent's scope attribute to a universal selector, so "> *" ties in
   specificity with (and can lose to, by source order) AppSelect's own
   ".app-select { width: 100% }" rule. The wrapper sidesteps that entirely: it
   sets the real width, and AppSelect's width:100% just fills it as intended. */
.filter-select-wrap {
  width: 170px;
  flex-shrink: 0;
}

.limit-control {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.limit-input {
  width: 70px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 6px 8px;
  font-size: var(--fs-caption);
}

.banner-error {
  font-size: var(--fs-caption);
  color: var(--color-danger);
}

.empty-filtered {
  /* Fills the space left under the toolbar instead of being a short strip, so
     the screen doesn't end in a band of dead space. */
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--fs-label);
  border: 1px dashed var(--surface-border-soft);
  border-radius: var(--radius-md);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.history-card {
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast),
    background var(--transition-fast);
  animation: card-in 260ms ease backwards;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.history-card:hover {
  border-color: var(--surface-border);
  background: var(--surface-3);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.card-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: calc(var(--thumb-size) * 0.8125);
}

.thumb {
  width: calc(var(--thumb-size) * 0.8125);
  height: calc(var(--thumb-size) * 0.8125);
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  background: var(--surface-3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  overflow: hidden;
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.card-info-top {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.file-name {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.card-meta {
  display: flex;
  gap: var(--space-1-5);
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  flex-wrap: wrap;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.icon-action {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.icon-action:hover:not(:disabled) {
  background: var(--surface-3);
  color: var(--text-primary);
}

.icon-action:focus-visible {
  outline: 2px solid var(--color-primary);
}

.icon-action:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.menu-wrap {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 20;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 200px;
}

.dropdown-menu button {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  color: var(--text-primary);
  font-size: var(--fs-caption);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
}

.dropdown-menu button:hover {
  background: var(--surface-3);
}

.dropdown-menu button.danger {
  color: var(--color-danger);
}

.card-details {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--surface-border-soft);
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.detail-item dt {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.detail-item dd {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  overflow-wrap: break-word;
  word-break: break-word;
}

.undo-toast {
  position: fixed;
  bottom: var(--space-4);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  padding: 10px 16px;
  box-shadow: var(--shadow-md);
  font-size: var(--fs-caption);
  color: var(--text-primary);
  z-index: 60;
}

.undo-toast button {
  background: none;
  border: none;
  color: var(--color-primary);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

@media (max-width: 900px) {
  .card-main {
    flex-wrap: wrap;
  }

  .filter-select-wrap {
    width: 100%;
  }

  .search-bar {
    width: 100%;
  }
}
</style>

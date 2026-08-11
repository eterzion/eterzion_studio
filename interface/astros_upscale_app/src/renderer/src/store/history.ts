import { reactive } from 'vue'
import type { ContentType, MediaType } from '../backend'
import type { Job, JobStatus, ScaleConfig } from './jobs'
import { settingsState } from './settings'

const STORAGE_KEY = 'astros-upscale:history'

export type HistoryStatus = 'queued' | 'processing' | 'done' | 'error' | 'cancelled'

export interface HistoryEntry {
  id: string // shared with the originating Job.id, so updates land in place
  sourcePath: string
  fileName: string
  thumbnail?: string
  status: HistoryStatus
  createdAt: number
  completedAt?: number
  originalWidth: number | null
  originalHeight: number | null
  newWidth?: number
  newHeight?: number
  /** Present on entries recorded before this field existed — kept only so
   *  History can still show something for old rows (see HistoryView.vue's
   *  "Arquivado" fallback). New entries never set it, they set contentType. */
  model?: string
  contentType?: ContentType | null
  /** T066 — absent on entries recorded before video/audio history existed;
   *  HistoryView.vue treats a missing value as 'image' (the only kind that
   *  existed then). */
  mediaType?: MediaType
  scale: number
  outputSizeBytes?: number
  outputPath?: string
  errorMessage?: string
  /** Only ever set for image-enhance entries (ImageEditorView's "reuse
   *  config" feature) — video/audio/compress-convert entries never carry
   *  this, since ScaleConfig is an image-specific shape (T066). */
  scaleConfig?: ScaleConfig
}

export const historyState = reactive<{ entries: HistoryEntry[] }>({
  entries: load()
})

function load(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function persist(): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(historyState.entries))
}

/** historyLimit lives in settings (single source of truth — Configurações > Histórico
 *  and the inline control on the Histórico tab both read/write the same value). */
export function setHistoryLimit(limit: number): void {
  settingsState.historyLimit = Math.max(1, Math.round(limit))
  pruneToLimit()
}

function pruneToLimit(): void {
  if (historyState.entries.length <= settingsState.historyLimit) return
  historyState.entries.sort((a, b) => a.createdAt - b.createdAt)
  historyState.entries.splice(0, historyState.entries.length - settingsState.historyLimit)
  persist()
}

/** "Limpeza automática" (Configurações > Histórico): drops entries older than the
 *  configured number of days. Runs on load and after every recordJob() call. */
function pruneOlderThanConfigured(): void {
  const days = settingsState.historyAutoCleanupDays
  if (!days) return
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000
  const before = historyState.entries.length
  historyState.entries = historyState.entries.filter((e) => e.createdAt >= cutoff)
  if (historyState.entries.length !== before) persist()
}

pruneOlderThanConfigured()
pruneToLimit()

/** Called whenever a Job's status changes — creates the history row the first time
 *  (on queued/processing) and updates it in place afterwards, so History reflects
 *  work in progress too, not just finished jobs. */
export function recordJob(job: Job, status: JobStatus): void {
  if (status === 'configuring') return // not yet a real processing attempt
  let entry = historyState.entries.find((e) => e.id === job.id)
  if (!entry) {
    entry = {
      id: job.id,
      sourcePath: job.sourcePath,
      fileName: job.fileName,
      thumbnail: job.thumbnail,
      status: status as HistoryStatus,
      createdAt: job.createdAt,
      originalWidth: job.sourceMeta.width,
      originalHeight: job.sourceMeta.height,
      contentType: job.scaleConfig.contentType,
      mediaType: 'image',
      scale: job.scaleConfig.mode === 'preset' ? job.scaleConfig.presetFactor : 0,
      scaleConfig: { ...job.scaleConfig }
    }
    historyState.entries.push(entry)
  }
  entry.status = status as HistoryStatus
  entry.contentType = job.scaleConfig.contentType
  entry.scaleConfig = { ...job.scaleConfig }
  if (job.outputMeta) {
    entry.newWidth = job.outputMeta.width
    entry.newHeight = job.outputMeta.height
    entry.outputSizeBytes = job.outputMeta.sizeBytes ?? undefined
  }
  if (job.lastExportPath) entry.outputPath = job.lastExportPath
  if (status === 'done' || status === 'error' || status === 'cancelled') {
    entry.completedAt = Date.now()
  }
  if (status === 'error') entry.errorMessage = job.errorMessage

  persist()
  pruneToLimit()
}

/** T066 — the video/audio/compress-convert screens each keep their own
 *  self-contained job list (see VideoView.vue/AudioView.vue/
 *  CompressConvertView.vue's own comments on why: ScaleConfig is an
 *  image-only shape) instead of store/jobs.ts's queueState. This is the
 *  media-agnostic equivalent of recordJob() for those — same "create on
 *  first call, update in place after" behavior, without requiring a full
 *  image Job/ScaleConfig object those screens never have. */
export interface SimpleJobRecord {
  id: string
  sourcePath: string
  fileName: string
  status: HistoryStatus
  mediaType: MediaType
  contentType?: ContentType | null
  createdAt: number
  outputPath?: string
  outputSizeBytes?: number
  errorMessage?: string
}

export function recordSimpleJob(record: SimpleJobRecord): void {
  let entry = historyState.entries.find((e) => e.id === record.id)
  if (!entry) {
    entry = {
      id: record.id,
      sourcePath: record.sourcePath,
      fileName: record.fileName,
      status: record.status,
      createdAt: record.createdAt,
      originalWidth: null,
      originalHeight: null,
      contentType: record.contentType,
      mediaType: record.mediaType,
      scale: 0
    }
    historyState.entries.push(entry)
  }
  entry.status = record.status
  entry.contentType = record.contentType
  entry.mediaType = record.mediaType
  if (record.outputPath) entry.outputPath = record.outputPath
  if (record.outputSizeBytes != null) entry.outputSizeBytes = record.outputSizeBytes
  if (record.status === 'done' || record.status === 'error' || record.status === 'cancelled') {
    entry.completedAt = Date.now()
  }
  if (record.status === 'error') entry.errorMessage = record.errorMessage

  persist()
  pruneToLimit()
}

export function removeHistoryEntry(id: string): HistoryEntry | undefined {
  const index = historyState.entries.findIndex((e) => e.id === id)
  if (index === -1) return undefined
  const [removed] = historyState.entries.splice(index, 1)
  persist()
  return removed
}

export function restoreHistoryEntry(entry: HistoryEntry): void {
  historyState.entries.push(entry)
  persist()
}

export function clearHistory(): void {
  historyState.entries = []
  persist()
}

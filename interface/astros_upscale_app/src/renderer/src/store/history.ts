import { reactive } from 'vue'
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
  model: string
  scale: number
  outputSizeBytes?: number
  outputPath?: string
  errorMessage?: string
  scaleConfig: ScaleConfig // snapshot, for "reuse config"
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
      model: job.scaleConfig.model,
      scale: job.scaleConfig.mode === 'preset' ? job.scaleConfig.presetFactor : 0,
      scaleConfig: { ...job.scaleConfig }
    }
    historyState.entries.push(entry)
  }
  entry.status = status as HistoryStatus
  entry.model = job.scaleConfig.model
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

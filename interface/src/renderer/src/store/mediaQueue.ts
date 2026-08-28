import { computed, type ComputedRef } from 'vue'
import { i18n } from '../i18n'
import { queueState, removeJob, reorderJob, type JobStatus } from './jobs'
import { audioQueue, removeAudioJob, reorderAudioJob } from './audioQueue'
import { removeVideo, reorderVideo, videoQueue } from './videoQueue'

// One view over three queues.
//
// The Início screen used to read store/jobs.ts directly, which holds only
// images — so videos and audio were absent from "Fila de processamento"
// entirely. Rather than merge the three into one job type (they diverge a lot:
// an image job carries scale and export config an audio job has no use for),
// this derives the handful of fields the queue actually shows, and routes each
// action back to the store that owns the item.
//
// Ordering is per kind on purpose. Processing is serial *within* each screen,
// so the position of a video relative to an image decides nothing — allowing
// that drag would promise an effect the app cannot deliver.

export type MediaKind = 'image' | 'video' | 'audio'

export interface QueueEntry {
  id: string
  kind: MediaKind
  fileName: string
  sizeBytes: number
  status: JobStatus
  progress: number
  queuePosition: number | null
  /** Dimensions, duration — whatever the kind can say about itself. */
  detail: string | null
  thumbnail?: string
  errorMessage?: string
}

/** Video and audio use their own status vocabularies; the queue shows one. */
function asJobStatus(status: string): JobStatus {
  switch (status) {
    case 'detecting':
    case 'configuring':
    case 'idle':
      return 'configuring'
    case 'queued':
      return 'queued'
    case 'processing':
    case 'exporting':
      return 'processing'
    case 'done':
      return 'done'
    case 'error':
      return 'error'
    case 'cancelled':
      return 'cancelled'
    default:
      return 'configuring'
  }
}

function formatDuration(seconds: number): string {
  const total = Math.round(seconds)
  const minutes = Math.floor(total / 60)
  return `${minutes}:${String(total % 60).padStart(2, '0')}`
}

export const imageEntries: ComputedRef<QueueEntry[]> = computed(() =>
  queueState.jobs.map((job) => ({
    id: job.id,
    kind: 'image' as const,
    fileName: job.fileName,
    sizeBytes: job.sourceMeta.sizeBytes,
    status: job.status,
    progress: job.progress,
    queuePosition: job.queuePosition,
    detail: job.sourceMeta.width ? `${job.sourceMeta.width} × ${job.sourceMeta.height}` : null,
    thumbnail: job.thumbnail,
    errorMessage: job.errorMessage
  }))
)

export const videoEntries: ComputedRef<QueueEntry[]> = computed(() =>
  videoQueue.videos.map((video) => ({
    id: video.handle.handle_id,
    kind: 'video' as const,
    fileName: video.handle.display_name,
    sizeBytes: video.handle.size_bytes,
    // The editor owns the per-video processing state; the queue shows the
    // resting state, and the screen itself is where a running job is watched.
    status: 'configuring' as JobStatus,
    progress: 0,
    queuePosition: null,
    // Esta fila é do editor de vídeo, e todo vídeo tem duração — o `?? 0` está
    // aqui porque a rota de registro passou a servir também imagens (specs/008)
    // e o campo virou opcional no tipo, não porque um vídeo possa chegar sem ela.
    detail: video.handle.width
      ? `${video.handle.width} × ${video.handle.height} · ${formatDuration(video.handle.duration_seconds ?? 0)}`
      : formatDuration(video.handle.duration_seconds ?? 0)
  }))
)

export const audioEntries: ComputedRef<QueueEntry[]> = computed(() =>
  audioQueue.jobs.map((job) => ({
    id: job.id,
    kind: 'audio' as const,
    fileName: job.file.name,
    sizeBytes: job.file.size,
    status: asJobStatus(job.status),
    progress: job.progress,
    queuePosition: null,
    detail: job.stage,
    errorMessage: job.error
  }))
)

/** Grouped, not interleaved: reordering only means something inside a kind. */
export const queueGroups = computed(() =>
  [
    { kind: 'image' as const, entries: imageEntries.value },
    { kind: 'video' as const, entries: videoEntries.value },
    { kind: 'audio' as const, entries: audioEntries.value }
  ].filter((group) => group.entries.length > 0)
)

export const allEntries = computed(() => queueGroups.value.flatMap((group) => group.entries))

export function removeEntry(entry: QueueEntry): void {
  if (entry.kind === 'image') removeJob(entry.id)
  else if (entry.kind === 'video') removeVideo(entry.id)
  else removeAudioJob(entry.id)
}

export function clearAll(): void {
  for (const entry of [...allEntries.value]) removeEntry(entry)
}

/** Reorder within one kind — the index is into that kind's own array. */
export function reorderEntry(kind: MediaKind, fromIndex: number, toIndex: number): void {
  if (kind === 'image') reorderJob(fromIndex, toIndex)
  else if (kind === 'video') reorderVideo(fromIndex, toIndex)
  else reorderAudioJob(fromIndex, toIndex)
}

/** Only an item that has not been handed to the backend yet. Each screen
 *  submits in array order, so moving a not-yet-submitted job really does change
 *  what runs first — but once a job is queued server-side, its position comes
 *  from the API, and a drag would change the list without changing the outcome.
 *  Offering the drag anyway would promise an effect the app cannot deliver. */
export function canReorder(entry: QueueEntry): boolean {
  return entry.status === 'configuring'
}

export function kindLabel(kind: MediaKind): string {
  return i18n.global.t(`queue.kind.${kind}`)
}

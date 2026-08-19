import { reactive } from 'vue'
import type { ContentType, Profile } from '../services/api'
import type { DescribedFile } from '../services/native'

// The audio list lived inside AudioView as a `ref` — see store/videoQueue.ts
// for why that had to move.

export type AudioStatus = 'detecting' | 'configuring' | 'queued' | 'processing' | 'done' | 'error'

export interface AudioJob {
  id: string
  backendJobId: string | null
  file: DescribedFile
  contentType: ContentType
  profile: Profile
  device: string
  status: AudioStatus
  progress: number
  stage: string | null
  error?: string
  outputPath?: string
  createdAt: number
  /** Drops the progress socket — held so cancelling can stop it. */
  unsubscribe?: () => void
}

export const audioQueue = reactive<{ jobs: AudioJob[]; activeId: string | null }>({
  jobs: [],
  activeId: null
})

export function addAudioJob(job: AudioJob): AudioJob {
  audioQueue.jobs.push(job)
  audioQueue.activeId = job.id
  // Read it back out: reactive() proxies on the way in, and callers that keep
  // the object they passed would be mutating a copy nothing is watching.
  return audioQueue.jobs[audioQueue.jobs.length - 1]
}

export function removeAudioJob(id: string): void {
  audioQueue.jobs = audioQueue.jobs.filter((j) => j.id !== id)
  if (audioQueue.activeId === id) audioQueue.activeId = audioQueue.jobs[0]?.id ?? null
}

/** Move one job to a new index — the Início queue's drag-to-reorder. Audio is
 *  processed serially, so this array's order is the order they run in. */
export function reorderAudioJob(fromIndex: number, toIndex: number): void {
  const list = audioQueue.jobs
  if (fromIndex < 0 || fromIndex >= list.length) return
  if (toIndex < 0 || toIndex >= list.length) return
  const [moved] = list.splice(fromIndex, 1)
  list.splice(toIndex, 0, moved)
}

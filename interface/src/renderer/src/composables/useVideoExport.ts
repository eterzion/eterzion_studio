import { onBeforeUnmount, ref, type Ref } from 'vue'
import { cancelJob, type JobStatus } from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { createVideoEditJob, type VideoExportRequest } from '../services/api'

// T063 (specs/007-video-editor-player) — FR-021, FR-023a.
//
// Progress and cancellation come from the existing job system; nothing here
// reimplements them. What this owns is the part that is specific to the editor:
// which export belongs to which video, and the rule that closing the editing
// area does not stop one.

export interface ExportState {
  jobId: string | null
  status: JobStatus['status'] | 'creating'
  progress: number
  stage: string | null
  outputPath: string | null
  error: string | null
  /** Set when the refusal was a ceiling or a missing encoder, so the interface
      can say which limit rather than showing a generic failure (FR-025). */
  refusal: { reason: string; limitingFactor?: string } | null
}

export interface VideoExport {
  /** One export per video, keyed by handle. Switching videos must not appear to
      cancel or reassign an export already running (FR-023a). */
  exports: Ref<Map<string, ExportState>>
  stateFor: (handleId: string) => ExportState | null
  start: (handleId: string, request: VideoExportRequest) => Promise<void>
  cancel: (handleId: string) => Promise<void>
}

export function useVideoExport(): VideoExport {
  const exports = ref(new Map<string, ExportState>())
  const unsubscribers = new Map<string, () => void>()

  function set(handleId: string, patch: Partial<ExportState>): void {
    const previous = exports.value.get(handleId)
    const next: ExportState = {
      jobId: null,
      status: 'creating',
      progress: 0,
      stage: null,
      outputPath: null,
      error: null,
      refusal: null,
      ...previous,
      ...patch
    }
    // Replacing the Map rather than mutating it: a Map's contents are not deeply
    // reactive in Vue, so mutating in place updates nothing on screen.
    exports.value = new Map(exports.value).set(handleId, next)
  }

  function stateFor(handleId: string): ExportState | null {
    return exports.value.get(handleId) ?? null
  }

  async function start(handleId: string, request: VideoExportRequest): Promise<void> {
    set(handleId, { status: 'creating', progress: 0, error: null, refusal: null })
    try {
      const { job_id: jobId } = await createVideoEditJob(request)
      set(handleId, { jobId, status: 'queued' })

      unsubscribers.get(handleId)?.()
      unsubscribers.set(
        handleId,
        subscribeJobProgress(jobId, (status) => {
          set(handleId, {
            status: status.status,
            progress: status.progress ?? 0,
            stage: status.stage ?? null,
            outputPath: status.output_path ?? null,
            error: status.error ?? null
          })
        })
      )
    } catch (cause) {
      // A refusal carries a reason key the interface translates; a plain failure
      // carries a message. Distinguishing them is what lets FR-025's "name the
      // limiting factor" reach the screen.
      const detail = cause instanceof Error ? safeParse(cause.message) : null
      set(handleId, {
        status: 'error',
        error: cause instanceof Error ? cause.message : 'unknown',
        refusal: detail ? { reason: detail.reason, limitingFactor: detail.limiting_factor } : null
      })
    }
  }

  async function cancel(handleId: string): Promise<void> {
    const state = exports.value.get(handleId)
    if (!state?.jobId) return
    await cancelJob(state.jobId)
    set(handleId, { status: 'cancelled' })
  }

  // Unsubscribing from the socket is NOT cancelling the job. FR-023a: closing
  // the editing area leaves an export running, and the person finds it in the
  // history. Only the application shutting down cancels one.
  onBeforeUnmount(() => {
    for (const stop of unsubscribers.values()) stop()
    unsubscribers.clear()
  })

  return { exports, stateFor, start, cancel }
}

function safeParse(message: string): { reason: string; limiting_factor?: string } | null {
  try {
    const parsed = JSON.parse(message)
    return typeof parsed?.reason === 'string' ? parsed : null
  } catch {
    return null
  }
}

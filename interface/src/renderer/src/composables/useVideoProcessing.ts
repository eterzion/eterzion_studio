import { onBeforeUnmount, ref, type Ref } from 'vue'
import {
  cancelJob,
  confirmSecondaryElements,
  createLocalJob,
  createVideoEditJob,
  defaultAdjustments,
  getJob,
  processJob as apiProcessJob,
  type JobStatus,
  type Profile,
  type SecondaryElements,
  type VideoContainer,
  type VideoExportRequest
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordSimpleJob } from '../store/history'
import type { EnhanceSettings } from '../components/video/VideoEnhancePanel.vue'
import type { VideoEditSet } from './useVideoEdits'

// Owns everything that happens to a video after the person presses the button,
// for the unified Vídeo screen (specs/007-video-editor-player, FR-032 as
// amended: one screen, not two).
//
// Was useVideoExport, which only knew the edit-only route. Renamed rather than
// paired with a second composable: one video, one job, one place that knows
// which route it takes — two owners would eventually disagree about whose job
// is running.
//
// Two routes, and the difference is not cosmetic:
//
//   upscale requested → POST /jobs (enhance). Runs the model, then applies the
//                       edit set to the upscaled frames as a second pass. Can
//                       stop at pending_confirmation when the file carries
//                       extra audio tracks, subtitles or chapters (FR-081 to
//                       FR-086).
//   no upscale        → POST /video/edit-jobs. FFmpeg only, no model, no
//                       confirmation step — nothing is dropped that the filter
//                       graph does not drop.

export type ProcessingStatus =
  | 'idle'
  | 'creating'
  | 'awaiting_confirmation'
  | 'queued'
  | 'processing'
  | 'done'
  | 'error'
  | 'cancelled'

export interface ProcessingState {
  jobId: string | null
  status: ProcessingStatus
  progress: number
  stage: string | null
  outputPath: string | null
  error: string | null
  /** What enhance would silently drop. Non-null only while awaiting
      confirmation — the person decides before anything is processed. */
  secondaryElements: SecondaryElements | null
  refusal: { reason: string; limitingFactor?: string } | null
}

export interface VideoRequest {
  handleId: string
  displayName: string
  sourcePath: string
  edits: VideoEditSet
  enhance: EnhanceSettings
  container: VideoContainer
  directory: string | null
}

const HISTORY_STATUS: Partial<
  Record<ProcessingStatus, 'queued' | 'processing' | 'done' | 'error'>
> = {
  queued: 'queued',
  processing: 'processing',
  done: 'done',
  error: 'error',
  cancelled: 'error'
}

function neutralState(): ProcessingState {
  return {
    jobId: null,
    status: 'idle',
    progress: 0,
    stage: null,
    outputPath: null,
    error: null,
    secondaryElements: null,
    refusal: null
  }
}

export interface VideoProcessing {
  states: Ref<Map<string, ProcessingState>>
  stateFor: (handleId: string) => ProcessingState
  start: (request: VideoRequest) => Promise<void>
  /** FR-082/FR-084: the person has seen what would be lost and proceeds. */
  confirm: (handleId: string) => Promise<void>
  cancel: (handleId: string) => Promise<void>
  isBusy: (handleId: string) => boolean
}

export function useVideoProcessing(): VideoProcessing {
  const states = ref(new Map<string, ProcessingState>())
  const unsubscribers = new Map<string, () => void>()

  function set(handleId: string, patch: Partial<ProcessingState>): void {
    const next = { ...(states.value.get(handleId) ?? neutralState()), ...patch }
    // Replacing the Map rather than mutating it: a Map's contents are not deeply
    // reactive in Vue, so mutating in place updates nothing on screen.
    states.value = new Map(states.value).set(handleId, next)
  }

  function stateFor(handleId: string): ProcessingState {
    return states.value.get(handleId) ?? neutralState()
  }

  function isBusy(handleId: string): boolean {
    const status = stateFor(handleId).status
    return status === 'creating' || status === 'queued' || status === 'processing'
  }

  function syncHistory(request: VideoRequest): void {
    const state = states.value.get(request.handleId)
    if (!state?.jobId) return
    const status = HISTORY_STATUS[state.status]
    if (!status) return
    recordSimpleJob({
      id: state.jobId,
      sourcePath: request.sourcePath,
      fileName: request.displayName,
      status,
      mediaType: 'video',
      contentType: request.enhance.contentType,
      createdAt: Date.now(),
      outputPath: state.outputPath ?? undefined,
      errorMessage: state.error ?? undefined
    })
  }

  function applyStatus(request: VideoRequest, status: JobStatus): void {
    const handleId = request.handleId
    if (status.status === 'pending_confirmation') {
      set(handleId, {
        status: 'awaiting_confirmation',
        secondaryElements: status.secondary_elements ?? null
      })
    } else if (status.status === 'done') {
      set(handleId, { status: 'done', progress: 100, outputPath: status.output_path ?? null })
    } else if (status.status === 'error') {
      set(handleId, { status: 'error', error: status.error ?? 'unknown' })
    } else if (status.status === 'cancelled') {
      set(handleId, { status: 'cancelled' })
    } else {
      set(handleId, {
        status: status.status === 'processing' ? 'processing' : 'queued',
        progress: status.progress ?? 0,
        stage: status.stage ?? null
      })
    }
    syncHistory(request)
  }

  function watch(request: VideoRequest, jobId: string): void {
    unsubscribers.get(request.handleId)?.()
    unsubscribers.set(
      request.handleId,
      subscribeJobProgress(
        jobId,
        (status) => applyStatus(request, status),
        // A dropped socket is not a failed job. Falling back to a poll is what
        // keeps a long export from appearing stuck because the connection
        // blinked — the same fallback VideoView used.
        () => {
          getJob(jobId)
            .then((status) => applyStatus(request, status))
            .catch(() =>
              set(request.handleId, { status: 'error', error: 'Falha ao acompanhar o job.' })
            )
        }
      )
    )
  }

  async function startEnhance(request: VideoRequest): Promise<void> {
    const { enhance } = request
    const jobId = await createLocalJob(
      {
        media_type: 'video',
        operation: 'enhance',
        input_path: request.sourcePath,
        content_type_override: enhance.contentType,
        profile: enhance.profile,
        device: enhance.device,
        // 'custom' still travels a preset: it decides how hard the model works,
        // while custom_size names the exact frame size to land on.
        scale: enhance.scale === 'custom' ? '2x' : (enhance.scale as '2x' | '4x'),
        custom_size:
          enhance.scale === 'custom' && enhance.customWidth && enhance.customHeight
            ? { width: enhance.customWidth, height: enhance.customHeight }
            : null,
        edits: request.edits
      },
      defaultAdjustments()
    )
    set(request.handleId, { jobId, status: 'queued' })

    // FR-085: a job with nothing to lose lands straight in `pending`. Only start
    // processing once we know it is not waiting on the person.
    const created = await getJob(jobId)
    if (created.status === 'pending_confirmation') {
      set(request.handleId, {
        status: 'awaiting_confirmation',
        secondaryElements: created.secondary_elements ?? null
      })
      watch(request, jobId)
      return
    }

    syncHistory(request)
    await apiProcessJob(jobId)
    watch(request, jobId)
  }

  async function startEditOnly(request: VideoRequest): Promise<void> {
    const payload: VideoExportRequest = {
      handle_id: request.handleId,
      edits: request.edits as unknown as VideoExportRequest['edits'],
      container: request.container,
      profile: request.enhance.profile as Profile,
      output_directory: request.directory,
      conflict: 'rename'
    }
    const { job_id: jobId } = await createVideoEditJob(payload)
    set(request.handleId, { jobId, status: 'queued' })
    syncHistory(request)
    watch(request, jobId)
  }

  const pending = new Map<string, VideoRequest>()

  async function start(request: VideoRequest): Promise<void> {
    pending.set(request.handleId, request)
    set(request.handleId, {
      ...neutralState(),
      status: 'creating'
    })
    try {
      if (request.enhance.scale === 'none') await startEditOnly(request)
      else await startEnhance(request)
    } catch (cause) {
      const detail = cause instanceof Error ? safeParse(cause.message) : null
      set(request.handleId, {
        status: 'error',
        error: cause instanceof Error ? cause.message : 'unknown',
        refusal: detail ? { reason: detail.reason, limitingFactor: detail.limiting_factor } : null
      })
      syncHistory(request)
    }
  }

  async function confirm(handleId: string): Promise<void> {
    const state = states.value.get(handleId)
    const request = pending.get(handleId)
    if (!state?.jobId || !request) return
    await confirmSecondaryElements(state.jobId)
    set(handleId, { status: 'queued', secondaryElements: null })
    syncHistory(request)
    await apiProcessJob(state.jobId)
    watch(request, state.jobId)
  }

  async function cancel(handleId: string): Promise<void> {
    const state = states.value.get(handleId)
    if (!state?.jobId) return
    await cancelJob(state.jobId)
    set(handleId, { status: 'cancelled' })
  }

  // Unsubscribing is NOT cancelling. FR-023a: leaving the screen leaves the job
  // running and the person finds it in the history; only the application
  // shutting down cancels one.
  onBeforeUnmount(() => {
    for (const stop of unsubscribers.values()) stop()
    unsubscribers.clear()
  })

  return { states, stateFor, start, confirm, cancel, isBusy }
}

function safeParse(message: string): { reason: string; limiting_factor?: string } | null {
  try {
    const parsed = JSON.parse(message)
    return typeof parsed?.reason === 'string' ? parsed : null
  } catch {
    return null
  }
}

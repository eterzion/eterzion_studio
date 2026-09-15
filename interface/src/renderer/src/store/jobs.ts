import { reactive } from 'vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  detectContentType,
  processJob as apiProcessJob,
  cancelJob as apiCancelJob,
  getJob,
  ComponentActionError,
  type JobStatus as ApiJobStatus,
  type MediaRequest,
  type ErrorCategory,
  type ConflictMode,
  type ContentType,
  type Profile
} from '../services/api'
import type { RespostaDeConflito } from '../composables/usePerguntaDeConflito'
import { neutralEdits, type VideoEditSet } from '../composables/useVideoEdits'
import { copiarEdicoes } from '../utils/videoApplyAll'
import { subscribeJobProgress } from '../services/websocket'
import { recordJob } from './history'
import { settingsState } from './settings'
import { pushReactive } from './reactiveInsert'
import { i18n } from '../i18n'

// A store has no component instance, so useI18n() does not apply here.
// Calling through the global instance per message is also what makes a
// language change take effect immediately rather than at the next reload.
const t = i18n.global.t

// ------------------------------------------------------------------------- //
// Data model — mirrors the Spec Kit's Job/ScaleConfig/QueueState, adapted to
// the real eterzion_upscale_api contract. 'configuring' is entirely client-side
// (the backend job is only created once the user clicks "Processar", which
// creates it and enqueues it in one step — see startProcessing()). From
// 'queued' onward, status mirrors the backend job 1:1.
// ------------------------------------------------------------------------- //

export type JobStatus = 'configuring' | 'queued' | 'processing' | 'done' | 'error' | 'cancelled'

/** A exportacao da Imagem, escolhida antes de processar (app/exportacao_de_imagem.py). */
export interface ImageExport {
  /** 'keep' = o formato do original. */
  format: 'keep' | 'png' | 'jpg' | 'webp'
  /** A qualidade do JPEG/WebP, como a do Video e a do Audio. */
  profile: Profile
  directory: string | null
  conflict: ConflictMode
}

export interface ProcessingOptions {
  exportacao?: ImageExport
  /** Sem extensao; `null` = o nome do original. */
  filename?: string | null
  /** Abre a pergunta de conflito da tela. Sem ela, a recusa aparece como erro. */
  perguntarConflito?: (caminho: string) => Promise<RespostaDeConflito>
}

// As recusas que o backend faz antes do job, com a frase na lingua do app.
const RECUSAS = new Set(['format_unavailable', 'encoder_unavailable', 'insufficient_disk'])

// 1, not 16. The 16px floor rejected legitimate work — game and UI sprite
// sheets are routinely 8x8 or 12x10, and upscaling exactly that kind of art is
// a reason someone reaches for this app. It was a client-side rule with nothing
// behind it: the API accepts and enqueues an 8x8 job the same as any other
// (verified against the running server). What remains is the only floor that
// means anything — a side of zero is not a picture.
export const MIN_DIMENSION = 1
export const MAX_OUTPUT_DIMENSION = 32000
export const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

export interface ScaleConfig {
  /** 'original' keeps the source resolution and never runs the model — the job
      becomes a plain re-encode, which is what the Exportar screen already does
      for files that only need a different format or a smaller size. */
  mode: 'preset' | 'custom'
  presetFactor: 2 | 4
  customWidth: number | null
  customHeight: number | null
  lockAspectRatio: boolean
  // Detected automatically (T008/FR-096) when the file is added; editable —
  // never a model/checkpoint identifier (FR-009/FR-011). null while
  // detection is still in flight or failed.
  contentType: ContentType | null
  profile: Profile
  device: string
  denoise: number
  /** Off keeps the source's own sharpness — `sharpen` is only sent when on. */
  sharpenEnabled: boolean
  sharpen: number
  faceRecovery: boolean
  faceRecoveryStrength: number
  denoiseFilterEnabled: boolean
  denoiseFilterStrength: number
}

export interface SourceMeta {
  width: number | null
  height: number | null
  format: string
  sizeBytes: number
}

export interface OutputMeta {
  width: number
  height: number
  sizeBytes: number | null
}

export interface Job {
  id: string
  backendJobId: string | null
  sourcePath: string
  fileName: string
  sourceMeta: SourceMeta
  scaleConfig: ScaleConfig
  status: JobStatus
  progress: number
  stage?: string
  queuePosition: number | null
  errorMessage?: string
  errorCategory?: ErrorCategory
  /** Motivo fino da falha (hoje: o de um download), para a frase certa. */
  errorReason?: string
  /** Saída técnica (URL, código HTTP, ffmpeg) para a área recolhida. */
  errorDetail?: string
  outputMeta?: OutputMeta
  createdAt: number
  processingStartedAt?: number
  processingEndedAt?: number
  /** Onde o resultado foi gravado -- o destino escolhido, numa etapa so'. */
  outputPath?: string
  /** Ajustes de cor, efeitos e transformacao -- os mesmos do Video, aplicados
   *  ao resultado depois do modelo (app/exportacao_de_imagem.py). Trecho e
   *  audio existem no tipo e ficam neutros: numa imagem nao ha' o que cortar. */
  edits: VideoEditSet
  thumbnail?: string
}

export const queueState = reactive<{ jobs: Job[]; activeJobId: string | null; concurrency: 1 }>({
  jobs: [],
  activeJobId: null,
  concurrency: 1
})

function defaultScaleConfig(): ScaleConfig {
  return {
    mode: 'preset',
    presetFactor: settingsState.defaultScalePreset,
    customWidth: null,
    customHeight: null,
    lockAspectRatio: settingsState.defaultLockAspectRatio,
    contentType: null,
    profile: 'fast', // FR-008: Rápido is the default when nothing is chosen
    device: 'auto',
    denoise: 50,
    sharpenEnabled: false,
    sharpen: 50,
    faceRecovery: false,
    faceRecoveryStrength: 50,
    denoiseFilterEnabled: false,
    denoiseFilterStrength: 45
  }
}

function loadImageDimensions(url: string): Promise<{ width: number; height: number } | null> {
  return new Promise((resolvePromise) => {
    const img = new Image()
    img.onload = () => resolvePromise({ width: img.naturalWidth, height: img.naturalHeight })
    img.onerror = () => resolvePromise(null)
    img.src = url
  })
}

export interface UploadRejection {
  name: string
  reason: string
}

export interface UploadResult {
  added: Job[]
  rejected: UploadRejection[]
  duplicates: string[]
}

/** Validates and turns DescribedFile entries into configuring Jobs — section 3.2
 *  of the spec: format, file size, and min/max resolution checks happen here,
 *  before a Job is ever created. */
export async function addFiles(described: DescribedFile[]): Promise<UploadResult> {
  const rejected: UploadRejection[] = []
  const duplicates: string[] = []
  const added: Job[] = []

  // Two passes on purpose.
  //
  // The checks that depend on accumulated state — is this a duplicate of one
  // already in the queue, or of an earlier file in this same batch — have to
  // run in order, one after another. They are pure comparisons, so that costs
  // nothing.
  //
  // Reading each image's dimensions does not. It decodes the file to ask how
  // big it is, and doing that inside the sequential loop meant file N waited
  // for all N-1 before it. Worse, content-type detection is fired right after,
  // so the last file's detection could not even start until every earlier
  // image had finished decoding — which is what made "Detectando…" sit there
  // on a batch. The API answers detection in about 10ms; the waiting was all
  // on this side.
  const candidates: DescribedFile[] = []
  for (const f of described) {
    if (f.kind !== 'Imagem') {
      rejected.push({ name: f.name, reason: t('errors.job.unsupportedFormat') })
      continue
    }
    if (
      queueState.jobs.some((j) => j.sourcePath === f.path) ||
      candidates.some((c) => c.path === f.path)
    ) {
      duplicates.push(f.name)
      continue
    }
    if (f.size > MAX_FILE_SIZE_BYTES) {
      rejected.push({
        name: f.name,
        reason: t('validation.tooLargeFile', { mb: MAX_FILE_SIZE_BYTES / (1024 * 1024) })
      })
      continue
    }
    candidates.push(f)
  }

  // All the decoding at once. Order is preserved because Promise.all resolves
  // positionally, so the queue still lists files as the person picked them.
  const measured = await Promise.all(
    candidates.map(async (f) => {
      const thumbnail = hasNativeApi ? api.toFileUrl(f.path) : undefined
      return { f, thumbnail, dims: thumbnail ? await loadImageDimensions(thumbnail) : null }
    })
  )

  for (const { f, thumbnail, dims } of measured) {
    if (dims && (dims.width < MIN_DIMENSION || dims.height < MIN_DIMENSION)) {
      rejected.push({ name: f.name, reason: t('validation.tooSmall', { min: MIN_DIMENSION }) })
      continue
    }
    if (dims && (dims.width > 10000 || dims.height > 10000)) {
      rejected.push({ name: f.name, reason: t('errors.job.resolutionTooHigh') })
      continue
    }

    const job: Job = {
      id: crypto.randomUUID(),
      backendJobId: null,
      sourcePath: f.path,
      fileName: f.name,
      sourceMeta: {
        width: dims?.width ?? null,
        height: dims?.height ?? null,
        format: f.ext.replace('.', '').toUpperCase(),
        sizeBytes: f.size
      },
      scaleConfig: defaultScaleConfig(),
      status: 'configuring',
      progress: 0,
      queuePosition: null,
      edits: neutralEdits(),
      createdAt: Date.now(),
      thumbnail
    }
    // pushReactive, not push: the array holds Vue's proxy and `job` is the raw
    // object underneath, so the detection callback below has to write through
    // the proxy or nothing re-renders. See store/reactiveInsert.ts.
    const stored = pushReactive(queueState.jobs, job)
    added.push(stored)

    // FR-096: detect automatically, but leave it fully editable — a failed
    // detection just leaves contentType null, and the UI/validateScaleConfig
    // requires the person to pick one manually before processing.
    detectContentType(f.path, 'image')
      .then((detected) => {
        stored.scaleConfig.contentType = detected
      })
      .catch(() => {
        // left null on purpose — see comment above
      })
  }

  if (added.length && !queueState.activeJobId) {
    queueState.activeJobId = added[0].id
  }

  return { added, rejected, duplicates }
}

export function getJobById(id: string): Job | undefined {
  return queueState.jobs.find((j) => j.id === id)
}

export function getActiveJob(): Job | undefined {
  return queueState.jobs.find((j) => j.id === queueState.activeJobId)
}

export function setActiveJob(id: string): void {
  queueState.activeJobId = id
}

/** Move one job to a new index. processAll() submits in array order, so this
 *  array decides which image the backend is handed first — but only for jobs
 *  not yet submitted. Once a job is queued server-side its position comes from
 *  the API (job.queuePosition), and moving it here would change nothing. */
export function reorderJob(fromIndex: number, toIndex: number): void {
  const list = queueState.jobs
  if (fromIndex < 0 || fromIndex >= list.length) return
  if (toIndex < 0 || toIndex >= list.length) return
  const [moved] = list.splice(fromIndex, 1)
  list.splice(toIndex, 0, moved)
}

export function removeJob(id: string): void {
  const job = getJobById(id)
  if (job?.status === 'processing' || job?.status === 'queued') {
    void cancelProcessing(job)
  }
  queueState.jobs = queueState.jobs.filter((j) => j.id !== id)
  if (queueState.activeJobId === id) {
    queueState.activeJobId = queueState.jobs[0]?.id ?? null
  }
}

/** The multiplier a custom size represents relative to the source — max of the two
 *  axis ratios, the same rule the backend uses to pick the model pass before the
 *  final resize (see eterzion_upscale_api Upscaler.process). */
export function effectiveCustomScale(job: Job): number | null {
  const { width: srcW, height: srcH } = job.sourceMeta
  const w = job.scaleConfig.customWidth
  const h = job.scaleConfig.customHeight
  if (!srcW || !srcH || !w || !h) return null
  return Math.max(w / srcW, h / srcH)
}

function dimsForFactor(job: Job, rawFactor: number): { width: number; height: number } | null {
  const { width: srcW, height: srcH } = job.sourceMeta
  if (!srcW || !srcH) return null
  const factor = Math.max(
    1,
    Math.min(rawFactor, MAX_OUTPUT_DIMENSION / srcW, MAX_OUTPUT_DIMENSION / srcH)
  )
  return { width: Math.round(srcW * factor), height: Math.round(srcH * factor) }
}

/** Prefills custom width/height (from the current preset factor, clamped to the
 *  output limit) the first time the user switches to custom mode — empty inputs
 *  are a hostile starting point. */
export function ensureCustomSizeDefaults(job: Job): void {
  if (job.scaleConfig.customWidth != null && job.scaleConfig.customHeight != null) return
  const dims = dimsForFactor(job, job.scaleConfig.presetFactor)
  if (!dims) return
  job.scaleConfig.customWidth = dims.width
  job.scaleConfig.customHeight = dims.height
}

/** Which model pass a job should ask for.
 *
 *  'original' and 'pixel' never run a model at all — '1x' tells the backend to
 *  skip it (Upscaler.process_without_model).
 *
 *  'preset' is whatever the person picked, 2x or 4x.
 *
 *  'custom' derives it from the target actually typed, which is the point: the
 *  mode used to send whichever preset factor happened to be selected, so asking
 *  for a 2x-sized output while the preset sat on 4x ran the 4x model and threw
 *  most of it away in a downscale. Now a target up to 2x uses the 2x pass and
 *  anything beyond it uses 4x, so the model always works at or above the size
 *  being asked for — never below, which would mean interpolating up afterwards.
 */
/** Content types that run no model at all — the client-side mirror of the
 *  backend's licensing.MODEL_FREE_CONTENT_TYPES. */
const MODEL_FREE_CONTENT_TYPES = ['pixel_art', 'no_model']

export function scaleForJob(job: Job): '1x' | '2x' | '4x' {
  const { mode, presetFactor, contentType } = job.scaleConfig
  // '1x' is what tells the backend to skip the model. It used to be decided by
  // the scale mode, which put "should a model run" among the sizes; it is the
  // content type's answer to give.
  if (contentType && MODEL_FREE_CONTENT_TYPES.includes(contentType)) return '1x'
  if (mode !== 'custom') return `${presetFactor}x` as '2x' | '4x'

  const { width: srcW, height: srcH } = job.sourceMeta
  const { customWidth, customHeight } = job.scaleConfig
  if (!srcW || !srcH || !customWidth || !customHeight) return `${presetFactor}x` as '2x' | '4x'

  const factor = Math.max(customWidth / srcW, customHeight / srcH)
  return factor <= 2 ? '2x' : '4x'
}

/** Proposes an exact doubling for art drawn on a grid.
 *
 *  Whole multiples are what this mode is for: at 2x every source pixel becomes
 *  a clean 2x2 block. A fractional factor makes some pixels wider than others,
 *  which on pixel art is visible as an uneven, wobbling grid — the one artefact
 *  this path exists to avoid. Nothing forbids typing another number; this is
 *  just the starting point that is right far more often than not. */
export function proposePixelSize(job: Job): void {
  const { width: srcW, height: srcH } = job.sourceMeta
  if (!srcW || !srcH) return
  job.scaleConfig.customWidth = Math.min(srcW * 2, MAX_OUTPUT_DIMENSION)
  job.scaleConfig.customHeight = Math.min(srcH * 2, MAX_OUTPUT_DIMENSION)
}

/** Entering 'original' starts from the source's own size — the mode's whole
 *  point is not enlarging, so a preset-derived 2x default would be invalid the
 *  moment it appeared. Any target already smaller than the source is kept. */
export function clampSizeToSource(job: Job): void {
  const { width: srcW, height: srcH } = job.sourceMeta
  if (!srcW || !srcH) return
  const { customWidth, customHeight } = job.scaleConfig
  job.scaleConfig.customWidth = customWidth && customWidth <= srcW ? customWidth : srcW
  job.scaleConfig.customHeight = customHeight && customHeight <= srcH ? customHeight : srcH
}

/** Keeps the custom target in sync with whichever preset factor the user just
 *  picked — otherwise switching 4x -> 2x on the Predefinido tab and then back
 *  to Custom kept showing the old 4x-derived dimensions/multiplier,
 *  since ensureCustomSizeDefaults() no-ops once they're already set. Called
 *  whenever the preset buttons are clicked, not just on first custom-mode entry. */
export function syncCustomSizeToPreset(job: Job): void {
  const dims = dimsForFactor(job, job.scaleConfig.presetFactor)
  if (!dims) return
  job.scaleConfig.customWidth = dims.width
  job.scaleConfig.customHeight = dims.height
}

export function applyConfigToAll(sourceJob: Job): void {
  // Custom sizes are absolute pixels, which only make sense for the source image's
  // aspect ratio — so what carries over to the other jobs is the *scale factor*,
  // recomputed against each image's own dimensions.
  const customFactor =
    sourceJob.scaleConfig.mode === 'custom' ? effectiveCustomScale(sourceJob) : null
  for (const job of queueState.jobs) {
    if (job.id === sourceJob.id || job.status !== 'configuring') continue
    job.scaleConfig = { ...sourceJob.scaleConfig }
    copiarEdicoes(sourceJob.edits, job.edits)
    if (customFactor && job.sourceMeta.width && job.sourceMeta.height) {
      job.scaleConfig.customWidth = Math.min(
        MAX_OUTPUT_DIMENSION,
        Math.round(job.sourceMeta.width * customFactor)
      )
      job.scaleConfig.customHeight = Math.min(
        MAX_OUTPUT_DIMENSION,
        Math.round(job.sourceMeta.height * customFactor)
      )
    }
  }
}

/** Section 4.4 — outscale/model validity, plus the "never downscale, never exceed
 *  32000px per side" guards from 4.2. Returns a single human-readable reason so
 *  the UI can show it inline instead of just disabling the button silently. */
export function validateScaleConfig(job: Job): { valid: boolean; reason?: string } {
  // Original mode resolves no model (it travels as scale '1x'), so the content
  // type — which exists only to pick one — cannot block it. Requiring it here is
  // what left Processar disabled on the one mode that never needed it.
  if (!job.scaleConfig.contentType)
    return { valid: false, reason: t('errors.job.contentTypeMissing') }

  const { width: srcW, height: srcH } = job.sourceMeta
  if (job.scaleConfig.mode === 'preset') {
    if (![2, 4].includes(job.scaleConfig.presetFactor))
      return { valid: false, reason: t('errors.job.scaleMissing') }
    if (srcW && srcH) {
      const outW = srcW * job.scaleConfig.presetFactor
      const outH = srcH * job.scaleConfig.presetFactor
      if (outW > MAX_OUTPUT_DIMENSION || outH > MAX_OUTPUT_DIMENSION) {
        return {
          valid: false,
          reason: t('validation.outputTooLarge', { max: MAX_OUTPUT_DIMENSION })
        }
      }
    }
    return { valid: true }
  }

  const w = job.scaleConfig.customWidth
  const h = job.scaleConfig.customHeight
  if (!w || !h || w <= 0 || h <= 0) return { valid: false, reason: t('errors.job.sizeMissing') }

  if (w > MAX_OUTPUT_DIMENSION || h > MAX_OUTPUT_DIMENSION) {
    return { valid: false, reason: t('validation.maxSide', { max: MAX_OUTPUT_DIMENSION }) }
  }
  if (srcW && srcH && (w < srcW || h < srcH)) {
    return {
      valid: false,
      reason: t('errors.job.customTooSmall')
    }
  }
  return { valid: true }
}

export function estimatedOutputSize(job: Job): { width: number; height: number } | null {
  const { width: srcW, height: srcH } = job.sourceMeta
  if (!srcW || !srcH) return null
  if (job.scaleConfig.mode === 'custom') {
    const { customWidth, customHeight } = job.scaleConfig
    return customWidth && customHeight
      ? { width: customWidth, height: customHeight }
      : { width: srcW, height: srcH }
  }
  if (job.scaleConfig.mode === 'preset') {
    return {
      width: srcW * job.scaleConfig.presetFactor,
      height: srcH * job.scaleConfig.presetFactor
    }
  }
  if (job.scaleConfig.customWidth && job.scaleConfig.customHeight) {
    return { width: job.scaleConfig.customWidth, height: job.scaleConfig.customHeight }
  }
  return null
}

/** Very rough heuristic (source bytes scaled by output/source pixel ratio) — good
 *  enough for the "estimated size" hint the spec asks for, not a real prediction. */
export function estimatedOutputBytes(job: Job): number | null {
  const out = estimatedOutputSize(job)
  const { width: srcW, height: srcH, sizeBytes } = job.sourceMeta
  if (!out || !srcW || !srcH) return null
  const ratio = (out.width * out.height) / (srcW * srcH)
  return Math.round(sizeBytes * ratio)
}

const jobUnsubscribers = new Map<string, () => void>()

function stopWatching(backendJobId: string): void {
  jobUnsubscribers.get(backendJobId)?.()
  jobUnsubscribers.delete(backendJobId)
}

/** Spec 5.5: native OS notification when a job finishes and the window isn't focused. */
function notifyDone(job: Job): void {
  if (typeof document === 'undefined' || document.hasFocus()) return
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  new Notification('Eterzion Studio', {
    body: t('errors.job.notificationDone', { file: job.fileName })
  })
}

function applyApiStatus(job: Job, status: ApiJobStatus): void {
  job.progress = status.progress
  job.stage = status.stage ?? undefined
  job.queuePosition = status.queue_position
  if (status.processing_started_at)
    job.processingStartedAt = Date.parse(status.processing_started_at)
  if (status.processing_ended_at) job.processingEndedAt = Date.parse(status.processing_ended_at)
  if (status.source_meta) {
    job.sourceMeta.width = status.source_meta.width
    job.sourceMeta.height = status.source_meta.height
  }
  if (status.output_meta) {
    job.outputMeta = {
      width: status.output_meta.width,
      height: status.output_meta.height,
      sizeBytes: status.output_meta.size_bytes
    }
  }

  if (status.status === 'queued' || status.status === 'processing') {
    job.status = status.status
    recordJob(job, job.status)
    return
  }

  if (job.backendJobId) stopWatching(job.backendJobId)

  if (status.status === 'done') {
    job.status = 'done'
    job.progress = 100
    // Antes do recordJob: e' o que leva o caminho ao Historico, que antes
    // quase sempre mostrava "nao exportado".
    job.outputPath = status.output_path ?? undefined
    notifyDone(job)
  } else if (status.status === 'error') {
    job.status = 'error'
    job.errorMessage = status.error ?? t('errors.job.processingFailed')
    job.errorCategory = status.error_category ?? undefined
    job.errorReason = status.error_reason ?? undefined
    job.errorDetail = status.error_detail ?? undefined
  } else if (status.status === 'cancelled') {
    job.status = 'cancelled'
  }
  recordJob(job, job.status)
}

/** configuring -> queued: creates the backend job (with the final scaleConfig
 *  and the destination) and enqueues it in one go, then subscribes to live
 *  progress. */
export async function startProcessing(job: Job, options: ProcessingOptions = {}): Promise<void> {
  if (!hasNativeApi) return
  const validity = validateScaleConfig(job)
  if (!validity.valid) {
    job.status = 'error'
    job.errorMessage = validity.reason
    return
  }

  job.status = 'queued'
  job.progress = 0
  job.errorMessage = undefined
  job.errorCategory = undefined
  job.errorReason = undefined
  job.errorDetail = undefined
  job.outputPath = undefined
  recordJob(job, job.status)

  const exportacao = options.exportacao
  try {
    // Both 'custom' and 'original' express an exact target size; they differ
    // only in which direction it is allowed to go (see validateScaleConfig).
    const customSize =
      job.scaleConfig.mode !== 'preset' &&
      job.scaleConfig.customWidth &&
      job.scaleConfig.customHeight
        ? { width: job.scaleConfig.customWidth, height: job.scaleConfig.customHeight }
        : null

    const backendJobId = await createLocalJob(
      {
        media_type: 'image',
        operation: 'enhance',
        // '1x' tells the backend to skip the model entirely and just run the
        // filters (and any reduction) — see Upscaler.process_without_model.
        scale: scaleForJob(job),
        profile: job.scaleConfig.profile,
        content_type_override: job.scaleConfig.contentType,
        input_path: job.sourcePath,
        device: job.scaleConfig.device,
        custom_size: customSize,
        // So' o que vale para um quadro; trecho e audio nao existem numa imagem.
        edits: {
          adjustments: job.edits.adjustments,
          effects: job.edits.effects,
          transform: job.edits.transform
        } as unknown as MediaRequest['edits'],
        output_target: exportacao
          ? {
              format: exportacao.format,
              profile: exportacao.profile,
              directory: exportacao.directory,
              filename: options.filename ?? null,
              conflict: exportacao.conflict
            }
          : null
      },
      {
        denoise: job.scaleConfig.denoise,
        // Same rule the denoise filter and face recovery follow: the strength
        // only travels when its toggle is on, so a slider left at some value
        // from an earlier job cannot leak into one where it was switched off.
        deblur: job.scaleConfig.sharpenEnabled ? job.scaleConfig.sharpen : 0,
        detail_recovery: job.scaleConfig.sharpenEnabled ? job.scaleConfig.sharpen : 0,
        face_correction: job.scaleConfig.faceRecovery,
        face_recovery_strength: job.scaleConfig.faceRecoveryStrength,
        denoise_filter_enabled: job.scaleConfig.denoiseFilterEnabled,
        denoise_filter_strength: job.scaleConfig.denoiseFilterStrength
      }
    )
    job.backendJobId = backendJobId
    await apiProcessJob(backendJobId)

    const unsubscribe = subscribeJobProgress(
      backendJobId,
      (status) => applyApiStatus(job, status),
      () => {
        getJob(backendJobId)
          .then((status) => applyApiStatus(job, status))
          .catch(() => {
            job.status = 'error'
            job.errorMessage = t('errors.job.connectionLost')
            recordJob(job, job.status)
          })
      }
    )
    jobUnsubscribers.set(backendJobId, unsubscribe)
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    if (message.startsWith('CONFLICT:') && exportacao && options.perguntarConflito) {
      // Nada foi processado: o backend recusou antes de criar o job.
      const resposta = await options.perguntarConflito(message.slice('CONFLICT:'.length))
      if (resposta) {
        return startProcessing(job, {
          ...options,
          exportacao: { ...exportacao, conflict: resposta }
        })
      }
      job.status = 'configuring'
      recordJob(job, 'cancelled')
      return
    }
    job.status = 'error'
    job.errorMessage =
      error instanceof ComponentActionError && error.reason && RECUSAS.has(error.reason)
        ? t(`destination.refusal.${error.reason}`)
        : message || t('errors.job.createFailed')
    recordJob(job, job.status)
  }
}

/** processing/queued -> configuring. Cancellation of an in-flight job is
 *  best-effort on the backend (see job_manager.cancel_job) — the model call
 *  already running can't be killed safely, so its result is just discarded. */
export async function cancelProcessing(job: Job): Promise<void> {
  if (job.backendJobId) {
    stopWatching(job.backendJobId)
    try {
      await apiCancelJob(job.backendJobId)
    } catch {
      // best-effort — fall through and reset the local state regardless
    }
    recordJob(job, 'cancelled')
  }
  job.status = 'configuring'
  job.progress = 0
  job.queuePosition = null
  job.backendJobId = null
}

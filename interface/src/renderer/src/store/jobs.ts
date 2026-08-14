import { reactive } from 'vue'
import { api, hasNativeApi, type DescribedFile } from '../services/native'
import {
  createLocalJob,
  detectContentType,
  processJob as apiProcessJob,
  cancelJob as apiCancelJob,
  exportJob as apiExportJob,
  getJob,
  type JobStatus as ApiJobStatus,
  type ErrorCategory,
  type ExportRequest,
  type ContentType,
  type Profile
} from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import { recordJob } from './history'
import { settingsState } from './settings'

// ------------------------------------------------------------------------- //
// Data model — mirrors the Spec Kit's Job/ScaleConfig/QueueState, adapted to
// the real astros_upscale_api contract. 'configuring' is entirely client-side
// (the backend job is only created once the user clicks "Processar", which
// creates it and enqueues it in one step — see startProcessing()). From
// 'queued' onward, status mirrors the backend job 1:1.
// ------------------------------------------------------------------------- //

export type JobStatus = 'configuring' | 'queued' | 'processing' | 'done' | 'error' | 'cancelled'
export type ExportState = 'idle' | 'exporting' | 'exported' | 'error'

export const MIN_DIMENSION = 16
export const MAX_OUTPUT_DIMENSION = 32000
export const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

export interface ScaleConfig {
  /** 'original' keeps the source resolution and never runs the model — the job
      becomes a plain re-encode, which is what the Exportar screen already does
      for files that only need a different format or a smaller size. */
  mode: 'preset' | 'custom' | 'original'
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
  outputMeta?: OutputMeta
  createdAt: number
  processingStartedAt?: number
  processingEndedAt?: number
  exportState: ExportState
  exportError?: string
  lastExportPath?: string
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
    sharpen: 0,
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

  for (const f of described) {
    if (f.kind !== 'Imagem') {
      rejected.push({
        name: f.name,
        reason: 'Formato não suportado (apenas imagens: PNG, JPG, TIFF, WEBP, BMP).'
      })
      continue
    }
    if (queueState.jobs.some((j) => j.sourcePath === f.path)) {
      duplicates.push(f.name)
      continue
    }
    if (f.size > MAX_FILE_SIZE_BYTES) {
      rejected.push({
        name: f.name,
        reason: `Arquivo maior que o limite de ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB.`
      })
      continue
    }

    const thumbnail = hasNativeApi ? api.toFileUrl(f.path) : undefined
    const dims = thumbnail ? await loadImageDimensions(thumbnail) : null
    if (dims && (dims.width < MIN_DIMENSION || dims.height < MIN_DIMENSION)) {
      rejected.push({
        name: f.name,
        reason: `Resolução muito baixa (mínimo ${MIN_DIMENSION}×${MIN_DIMENSION}px).`
      })
      continue
    }
    if (dims && (dims.width > 10000 || dims.height > 10000)) {
      rejected.push({
        name: f.name,
        reason: 'Resolução de entrada muito alta (acima de 10000px); o upscale pode não ser viável.'
      })
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
      exportState: 'idle',
      createdAt: Date.now(),
      thumbnail
    }
    queueState.jobs.push(job)
    added.push(job)

    // FR-096: detect automatically, but leave it fully editable — a failed
    // detection just leaves contentType null, and the UI/validateScaleConfig
    // requires the person to pick one manually before processing.
    detectContentType(f.path, 'image')
      .then((detected) => {
        job.scaleConfig.contentType = detected
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
 *  final resize (see astros_upscale_api Upscaler.process). */
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
 *  to Customizado kept showing the old 4x-derived dimensions/multiplier,
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
  if (!job.scaleConfig.contentType)
    return { valid: false, reason: 'Tipo de conteúdo ainda não detectado — selecione manualmente.' }

  const { width: srcW, height: srcH } = job.sourceMeta
  if (job.scaleConfig.mode === 'preset') {
    if (![2, 4].includes(job.scaleConfig.presetFactor))
      return { valid: false, reason: 'Escolha um fator de escala.' }
    if (srcW && srcH) {
      const outW = srcW * job.scaleConfig.presetFactor
      const outH = srcH * job.scaleConfig.presetFactor
      if (outW > MAX_OUTPUT_DIMENSION || outH > MAX_OUTPUT_DIMENSION) {
        return {
          valid: false,
          reason: `Saída excederia o limite de ${MAX_OUTPUT_DIMENSION}px por lado.`
        }
      }
    }
    return { valid: true }
  }

  const w = job.scaleConfig.customWidth
  const h = job.scaleConfig.customHeight
  if (!w || !h || w <= 0 || h <= 0) return { valid: false, reason: 'Informe largura e altura.' }

  // 'original' is the mirror of 'custom': it exists precisely to NOT enlarge, so
  // its target may only shrink. Everything else about the job — filters, face
  // recovery, denoise — runs exactly the same way in both modes.
  if (job.scaleConfig.mode === 'original') {
    if (w < MIN_DIMENSION || h < MIN_DIMENSION) {
      return { valid: false, reason: `Mínimo de ${MIN_DIMENSION}px por lado.` }
    }
    if (srcW && srcH && (w > srcW || h > srcH)) {
      return {
        valid: false,
        reason:
          'No modo Original o tamanho não pode passar do original — para ampliar, use Predefinido ou Customizado.'
      }
    }
    return { valid: true }
  }

  if (w > MAX_OUTPUT_DIMENSION || h > MAX_OUTPUT_DIMENSION) {
    return { valid: false, reason: `Máximo de ${MAX_OUTPUT_DIMENSION}px por lado.` }
  }
  if (srcW && srcH && (w < srcW || h < srcH)) {
    return {
      valid: false,
      reason: 'O tamanho customizado não pode ser menor que o original (isto é um upscaler).'
    }
  }
  return { valid: true }
}

export function estimatedOutputSize(job: Job): { width: number; height: number } | null {
  const { width: srcW, height: srcH } = job.sourceMeta
  if (!srcW || !srcH) return null
  if (job.scaleConfig.mode === 'original') {
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
  new Notification('Astros Upscale', { body: `${job.fileName} foi processada com sucesso.` })
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
    notifyDone(job)
  } else if (status.status === 'error') {
    job.status = 'error'
    job.errorMessage = status.error ?? 'Falha no processamento.'
    job.errorCategory = status.error_category ?? undefined
  } else if (status.status === 'cancelled') {
    job.status = 'cancelled'
  }
  recordJob(job, job.status)
}

/** configuring -> queued: creates the backend job (with the final scaleConfig)
 *  and enqueues it in one go, then subscribes to live progress. */
export async function startProcessing(job: Job): Promise<void> {
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
  recordJob(job, job.status)

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
        scale: `${job.scaleConfig.presetFactor}x`,
        profile: job.scaleConfig.profile,
        content_type_override: job.scaleConfig.contentType,
        input_path: job.sourcePath,
        device: job.scaleConfig.device,
        custom_size: customSize
      },
      {
        denoise: job.scaleConfig.denoise,
        deblur: job.scaleConfig.sharpen,
        detail_recovery: job.scaleConfig.sharpen,
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
            job.errorMessage = 'Falha na comunicação com o servidor durante o processamento.'
            recordJob(job, job.status)
          })
      }
    )
    jobUnsubscribers.set(backendJobId, unsubscribe)
  } catch (error) {
    job.status = 'error'
    job.errorMessage = error instanceof Error ? error.message : 'Falha ao criar o job.'
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

export interface ExportOptions {
  format: 'png' | 'jpg' | 'webp' | 'tiff'
  quality: number
  outputDir: string | null
  filename: string | null
  conflict: 'overwrite' | 'rename' | 'ask'
}

/** done -> exporting -> exported. Never re-runs the model — see services/api.ts's exportJob. */
export async function exportOne(
  job: Job,
  options: ExportOptions
): Promise<{ ok: boolean; path?: string; error?: string }> {
  if (!job.backendJobId) return { ok: false, error: 'Job sem processamento associado.' }
  job.exportState = 'exporting'
  job.exportError = undefined
  const request: ExportRequest = {
    format: options.format,
    quality: options.quality,
    output_dir: options.outputDir,
    filename: options.filename,
    conflict: options.conflict
  }
  try {
    const path = await apiExportJob(job.backendJobId, request)
    job.exportState = 'exported'
    job.lastExportPath = path
    return { ok: true, path }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Falha ao exportar.'
    job.exportState = 'error'
    job.exportError = message.startsWith('CONFLICT:')
      ? 'Já existe um arquivo com esse nome no destino.'
      : message
    return { ok: false, error: job.exportError }
  }
}

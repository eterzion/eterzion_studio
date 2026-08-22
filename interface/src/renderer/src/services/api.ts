// Client for the astros_upscale_api FastAPI server (api/astros_upscale_api).
// Mirrors app/models/schemas.py — keep the two in sync when either changes.

// Inlined at build time by electron.vite.config.ts's `define`. The renderer has
// no process.env, and making every call site await the port from the main
// process would turn a constant into an async dependency for no gain.
declare const __ASTROS_API_PORT__: string
import { i18n } from '../i18n'

export const BASE_URL = `http://127.0.0.1:${__ASTROS_API_PORT__}`

// T069/T070 — GET /components (FR-063/FR-064): capability-first, never a raw
// technical model identifier at the list level (FR-009). Replaces the old
// GET /models, which returned `name` directly and violated that.
export type InstallState = 'not_installed' | 'installing' | 'installed' | 'update_available'

export interface ComponentSummary {
  id: string
  capability_label: string
  size_mb: number
  install_state: InstallState
  update_available: boolean
}

export interface ComponentDetails extends ComponentSummary {
  technical_name: string
  version: string
  provenance: string
  license: string
}

export interface CustomSize {
  width: number
  height: number
}

export interface Adjustments {
  denoise: number
  deblur: number
  detail_recovery: number
  face_correction: boolean
  face_recovery_strength: number
  denoise_filter_enabled: boolean
  denoise_filter_strength: number
}

// Mirrors app/models/schemas.py's MediaRequest. `model`/`engine`/`checkpoint_id`
// are never valid fields here — the API rejects them outright (extra='forbid',
// FR-009/FR-011). The backend resolves which implementation to use internally
// from media_type/operation/scale/profile/content_type_override.
export type MediaType = 'image' | 'video' | 'audio'
export type Operation = 'enhance' | 'compress' | 'convert'
export type Profile = 'fast' | 'balanced' | 'quality'
export type ContentType =
  | 'photo'
  | 'pixel_art'
  | 'no_model'
  | 'anime_image'
  | 'real_video'
  | 'anime_video'
  | 'speech'
  | 'music'

export interface OutputTarget {
  format: string
  directory?: string | null
  filename?: string | null
  conflict?: ConflictMode
}

export interface MediaRequest {
  media_type: MediaType
  operation: Operation
  /** '1x' is the Imagem screen's Original mode: no model, filters only. */
  scale?: '1x' | '2x' | '4x' | null
  profile?: Profile | null
  content_type_override?: ContentType | null
  input_path: string
  output_target?: OutputTarget | null
  secondary_elements_ack?: boolean
  device?: string
  custom_size?: CustomSize | null
  quality?: number | null // compress/convert only (FR-027)
  /** specs/007-video-editor-player — the editor's settings, applied to the
      upscaled result as a second pass. Omitted means "no edits", and the job
      behaves exactly as it did before the unified screen existed. */
  edits?: unknown
}

/** Espelha `JobStatusValue` de `api/astros_upscale_api/app/schemas.py`. As duas
    listas são verificadas uma contra a outra por `test_status_enum_is_single_source.py`
    — um status novo no backend que não chegasse aqui viraria um estado que a
    interface não sabe desenhar. */
export type JobStatusValue =
  | 'pending'
  | 'pending_confirmation'
  /** specs/008 — entre importar e poder estimar: sondagem de metadados. */
  | 'analyzing'
  | 'queued'
  | 'processing'
  | 'done'
  | 'error'
  | 'cancelled'
export type ErrorCategory =
  | 'out_of_memory'
  | 'corrupted_input'
  | 'model_failure'
  | 'disk_full'
  | 'hardware_insufficient'
  | 'license_invalid'
export type ConflictMode = 'overwrite' | 'rename' | 'ask'

export interface SizeMeta {
  width: number
  height: number
  size_bytes: number | null
}

export interface CapacityCheck {
  fits: boolean
  estimated_duration: number | null
  limiting_resource: string | null
}

// FR-081 to FR-086: what the probe found before a video-enhance job started —
// only ever set for media_type='video'/operation='enhance', null everywhere else.
export interface SecondaryElements {
  video_stream_count: number
  audio_stream_count: number
  subtitle_stream_count: number
  has_chapters: boolean
  duration_seconds: number
  has_losses: boolean
  losses: string[]
}

export interface JobStatus {
  id: string
  status: JobStatusValue
  media_type: MediaType
  operation: Operation
  content_type_detected: ContentType | null
  secondary_elements?: SecondaryElements | null
  progress: number
  stage: string | null
  eta_seconds: number | null
  queue_position: number | null
  input_file: string
  output_path: string | null
  error: string | null
  error_category: ErrorCategory | null
  capacity_check: CapacityCheck | null
  created_at: string
  processing_started_at: string | null
  processing_ended_at: string | null
  source_meta: SizeMeta | null
  output_meta: SizeMeta | null
  params: Record<string, unknown>
}

export interface ExportRequest {
  format: 'png' | 'jpg' | 'jpeg' | 'tiff' | 'webp'
  quality: number
  output_dir?: string | null
  filename?: string | null
  conflict: ConflictMode
}

async function extractError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') return data.detail
    if (data.detail?.reason === 'conflict') return `CONFLICT:${data.detail.path}`
    return `Erro ${res.status}`
  } catch {
    return `Erro ${res.status}`
  }
}

export async function listComponents(): Promise<ComponentSummary[]> {
  const res = await fetch(`${BASE_URL}/components`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export async function getComponentDetails(componentId: string): Promise<ComponentDetails> {
  const res = await fetch(`${BASE_URL}/components/${componentId}/details`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export async function installComponent(componentId: string): Promise<ComponentSummary> {
  const res = await fetch(`${BASE_URL}/components/${componentId}/install`, { method: 'POST' })
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export async function updateComponent(componentId: string): Promise<ComponentSummary> {
  const res = await fetch(`${BASE_URL}/components/${componentId}/update`, { method: 'POST' })
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export type LicenseState =
  | 'active'
  | 'offline_tolerance'
  | 'offline_expiring'
  | 'blocked'
  | 'not_activated'
  | 'not_configured'

export interface LicenseStatusResponse {
  state: LicenseState
  installations_used: number
  installations_limit: number
  offline_days_remaining: number | null
}

/** T036/T038 — always goes through the local API's facade (never the remote
 *  licensing service directly): that's the only place the real offline-
 *  tolerance fallback (license_cache.py) and the T016 gate mechanism live. */
export async function getLicenseStatus(): Promise<LicenseStatusResponse> {
  const res = await fetch(`${BASE_URL}/license/status`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export async function activateLicenseKey(licenseId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/license/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ license_id: licenseId })
  })
  if (!res.ok) throw new Error(await extractError(res))
}

export async function releaseLicense(): Promise<void> {
  const res = await fetch(`${BASE_URL}/license/release`, { method: 'POST' })
  if (!res.ok) throw new Error(await extractError(res))
}

export async function createLocalJob(
  mediaRequest: MediaRequest,
  adjustments: Adjustments
): Promise<string> {
  const res = await fetch(`${BASE_URL}/jobs/local`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_request: mediaRequest, adjustments })
  })
  if (!res.ok) throw new Error(await extractError(res))
  const data = await res.json()
  return data.id as string
}

/** Populates the editable content-type indicator (FR-096) with a real
 *  detected default before a Job exists — the person can still override it
 *  in the request sent to createLocalJob(). */
export async function detectContentType(
  inputPath: string,
  mediaType: MediaType
): Promise<ContentType> {
  const res = await fetch(`${BASE_URL}/jobs/detect-content-type`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_path: inputPath, media_type: mediaType })
  })
  if (!res.ok) throw new Error(await extractError(res))
  const data = await res.json()
  return data.content_type as ContentType
}

/** FR-082/FR-084 — moves a video-enhance job out of pending_confirmation once
 *  the person has seen and accepted what the probe found would be lost. */
export async function confirmSecondaryElements(jobId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/jobs/${jobId}/confirm-secondary-elements`, {
    method: 'POST'
  })
  if (!res.ok) throw new Error(await extractError(res))
}

export async function processJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/jobs/${jobId}/process`, { method: 'POST' })
  if (!res.ok) throw new Error(await extractError(res))
}

export async function cancelJob(jobId: string): Promise<void> {
  await fetch(`${BASE_URL}/jobs/${jobId}`, { method: 'DELETE' })
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE_URL}/jobs/${jobId}`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

/** Re-encodes an already-processed job to the requested format/destination —
 *  never re-runs the model, so this is always fast (see routes_jobs.py). */
export async function exportJob(jobId: string, request: ExportRequest): Promise<string> {
  const res = await fetch(`${BASE_URL}/jobs/${jobId}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })
  if (!res.ok) throw new Error(await extractError(res))
  const data = await res.json()
  return data.output_path as string
}

export interface DenoisePreview {
  before: string // base64 PNG, no data: prefix
  after: string
  width: number
  height: number
}

/** Runs the real denoise filter (same cv2.fastNlMeansDenoisingColored used by the
 *  job pipeline) on a downscaled copy of the source image, for fast interactive
 *  before/after feedback — the actual job always re-runs it on the full result. */
export async function previewDenoise(inputPath: string, strength: number): Promise<DenoisePreview> {
  const res = await fetch(`${BASE_URL}/preview/denoise`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_path: inputPath, strength })
  })
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export function defaultAdjustments(): Adjustments {
  return {
    denoise: 50,
    deblur: 0,
    detail_recovery: 0,
    face_correction: false,
    face_recovery_strength: 80,
    denoise_filter_enabled: false,
    denoise_filter_strength: 45
  }
}

/** Copy for a failed job, in the current language.
 *
 *  A function, not a const object: a const is evaluated once at module load, so
 *  it would freeze whichever locale happened to be active at startup and never
 *  follow a language change — which is the bug this sweep exists to fix.
 *
 *  Keys live under errors.category.* so the message and its suggested action
 *  stay together; splitting them invites a message that no longer matches the
 *  advice beneath it. */
export function errorCategoryCopy(category: ErrorCategory): { message: string; action: string } {
  const key = ERROR_CATEGORY_KEYS[category]
  const t = i18n.global.t
  return {
    message: t(`errors.category.${key}.message`),
    action: t(`errors.category.${key}.action`)
  }
}

// The API's snake_case categories mapped to the locale files' camelCase keys.
// Explicit rather than derived, so renaming one side breaks the build here
// instead of silently rendering a raw identifier on screen.
const ERROR_CATEGORY_KEYS: Record<ErrorCategory, string> = {
  out_of_memory: 'outOfMemory',
  corrupted_input: 'corruptedInput',
  model_failure: 'modelFailure',
  disk_full: 'diskFull',
  hardware_insufficient: 'hardwareInsufficient',
  license_invalid: 'licenseInvalid'
}

// --- Video editing (specs/007-video-editor-player) ---
//
// Media is referenced by handle_id, never by path — Constitution Princípio
// XIII. `registerMediaHandle` is the single exception, and exists so that no
// other call needs a path: it is the bounded exception added to the principle
// in constitution v3.0.0, and its path must come from the OS file dialog.

export type VideoContainer = 'mp4' | 'mov' | 'mkv' | 'webm'

export interface MediaHandle {
  handle_id: string
  display_name: string
  duration_seconds: number
  width: number | null
  height: number | null
  frame_rate: number | null
  /** When true, FR-012 forbids presenting a frame number as exact. */
  frame_rate_is_variable: boolean
  has_audio: boolean
  size_bytes: number
  /** Changes when the file's content changes — compare against a cached value
      to know that derived thumbnails are stale (FR-017). */
  content_key: string
}

export interface ContainerAvailability {
  value: VideoContainer
  available: boolean
  /** A key, not a sentence — the interface translates it. Never an encoder
      name (Princípio V). */
  unavailable_reason: 'no_encoder_available' | null
}

export interface VideoExportOptions {
  containers: ContainerAvailability[]
  profiles: Profile[]
  ceilings: {
    max_duration_seconds: number
    max_width: number
    max_height: number
    max_frame_rate: number
    max_frame_count: number
    max_size_bytes: number
  }
}

/** Register a file chosen through the native dialog and receive the identifier
 *  every other video-editing call uses. The path passed here MUST have come
 *  from the OS file dialog — that is the first condition of the constitutional
 *  exception this call relies on, and the only one the renderer can honour. */
export async function registerMediaHandle(path: string): Promise<MediaHandle> {
  const res = await fetch(`${BASE_URL}/media/handles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  })
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

/** Re-read a handle's metadata. Used to detect that the source file changed
 *  underneath us, which invalidates thumbnails and previews (FR-017). */
export async function getMediaHandle(handleId: string): Promise<MediaHandle> {
  const res = await fetch(`${BASE_URL}/media/handles/${handleId}`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

/** What this machine can actually produce. Drives FR-027: a container with no
 *  working encoder is disabled before the person picks it, not after an export
 *  fails. */
export async function getVideoExportOptions(): Promise<VideoExportOptions> {
  const res = await fetch(`${BASE_URL}/video/export-options`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

/** The image counterpart. Same purpose as the video one: a format this
 *  machine's OpenCV build cannot write is disabled before it is chosen, not
 *  after the export fails. */
export interface ImageFormatAvailability {
  value: 'png' | 'jpg' | 'jpeg' | 'tiff' | 'webp'
  available: boolean
  unavailable_reason: 'unsupported_build' | null
}

export interface ImageExportOptions {
  formats: ImageFormatAvailability[]
}

export async function getImageExportOptions(): Promise<ImageExportOptions> {
  const res = await fetch(`${BASE_URL}/image/export-options`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export interface VideoEditSetPayload {
  adjustments: Record<string, number>
  effects: Record<string, number | boolean>
  transform: Record<string, unknown>
  trim: { start_seconds: number; end_seconds: number } | null
  audio: { mode: string; volume: number }
}

export interface VideoExportRequest {
  handle_id: string
  edits: VideoEditSetPayload
  container: VideoContainer
  profile: Profile
  output_directory?: string | null
  output_filename?: string | null
  conflict?: 'rename' | 'overwrite'
}

/** Create an export. A 422 body carries a `reason` key (ceiling_exceeded,
 *  encoder_unavailable, hardware_insufficient, source_changed) and, for a
 *  ceiling, the `limiting_factor` — so the interface can name what to change
 *  rather than reporting a generic failure (FR-025). */
export async function createVideoEditJob(
  request: VideoExportRequest
): Promise<{ job_id: string; status: string; estimated_duration_seconds: number | null }> {
  const res = await fetch(`${BASE_URL}/video/edit-jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })
  if (!res.ok) {
    // The detail object is preserved verbatim so useVideoExport can read the
    // reason key; extractError would flatten it to a sentence.
    const body = await res.json().catch(() => null)
    throw new Error(JSON.stringify(body?.detail ?? { reason: 'unknown' }))
  }
  return res.json()
}

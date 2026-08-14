// Client for the astros_upscale_api FastAPI server (api/astros_upscale_api).
// Mirrors app/models/schemas.py — keep the two in sync when either changes.

export const BASE_URL = 'http://127.0.0.1:8765'

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
  'photo' | 'anime_image' | 'real_video' | 'anime_video' | 'speech' | 'music'

export interface OutputTarget {
  format: string
  directory?: string | null
  filename?: string | null
  conflict?: ConflictMode
}

export interface MediaRequest {
  media_type: MediaType
  operation: Operation
  scale?: '2x' | '4x' | null
  profile?: Profile | null
  content_type_override?: ContentType | null
  input_path: string
  output_target?: OutputTarget | null
  secondary_elements_ack?: boolean
  device?: string
  custom_size?: CustomSize | null
  quality?: number | null // compress/convert only (FR-027)
}

export type JobStatusValue =
  'pending' | 'pending_confirmation' | 'queued' | 'processing' | 'done' | 'error' | 'cancelled'
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

export const ERROR_CATEGORY_COPY: Record<ErrorCategory, { message: string; action: string }> = {
  out_of_memory: {
    message: 'Memória insuficiente para este tamanho de saída.',
    action: 'Tente reduzir o fator de escala ou o tamanho customizado.'
  },
  corrupted_input: {
    message: 'Não foi possível ler o arquivo de origem.',
    action: 'Remova este item da fila e tente importar o arquivo novamente.'
  },
  model_failure: {
    message: 'Erro no processamento.',
    action: 'Tente novamente — se persistir, tente outro modelo ou dispositivo.'
  },
  disk_full: {
    message: 'Espaço em disco insuficiente.',
    action: 'Escolha outra pasta de destino com mais espaço livre.'
  },
  hardware_insufficient: {
    message: 'Este equipamento não tem capacidade para este processamento.',
    action: 'Tente um tamanho de saída menor ou o perfil Rápido.'
  },
  license_invalid: {
    message: 'Sua licença não está ativa.',
    action: 'Verifique o status da sua licença nas Configurações.'
  }
}

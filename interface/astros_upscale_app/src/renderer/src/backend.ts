// Client for the astros_upscale_api FastAPI server (interface/astros_upscale_api).
// Mirrors app/models/schemas.py — keep the two in sync when either changes.

const BASE_URL = 'http://127.0.0.1:8765'

export interface ModelInfo {
  name: string
  category: string
  scale: number
  description: string
}

export interface ModelsResponse {
  models: ModelInfo[]
  devices: string[]
  default_image_model: string
  default_video_model: string
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
}

export interface JobParams {
  model: string
  device: string
  scale: number
  custom_size?: CustomSize | null
  adjustments: Adjustments
}

export type JobStatusValue = 'pending' | 'queued' | 'processing' | 'done' | 'error' | 'cancelled'
export type ErrorCategory = 'out_of_memory' | 'corrupted_input' | 'model_failure' | 'disk_full'
export type ConflictMode = 'overwrite' | 'rename' | 'ask'

export interface SizeMeta {
  width: number
  height: number
  size_bytes: number | null
}

export interface JobStatus {
  id: string
  status: JobStatusValue
  progress: number
  stage: string | null
  eta_seconds: number | null
  queue_position: number | null
  input_file: string
  output_path: string | null
  error: string | null
  error_category: ErrorCategory | null
  created_at: string
  processing_started_at: string | null
  processing_ended_at: string | null
  source_meta: SizeMeta | null
  output_meta: SizeMeta | null
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

export async function getModels(): Promise<ModelsResponse> {
  const res = await fetch(`${BASE_URL}/models`)
  if (!res.ok) throw new Error(await extractError(res))
  return res.json()
}

export async function createLocalJob(inputPath: string, params: JobParams): Promise<string> {
  const res = await fetch(`${BASE_URL}/jobs/local`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_path: inputPath, params })
  })
  if (!res.ok) throw new Error(await extractError(res))
  const data = await res.json()
  return data.id as string
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

export async function listJobs(): Promise<JobStatus[]> {
  const res = await fetch(`${BASE_URL}/jobs`)
  if (!res.ok) throw new Error(await extractError(res))
  const data = await res.json()
  return data.jobs as JobStatus[]
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

/** Subscribes to live progress for a job over the API's WebSocket. Returns an
 *  unsubscribe function. Falls back silently if the socket errors — callers should
 *  still poll getJob() once as a fallback if they need a guaranteed final state. */
export function subscribeJobProgress(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  onError?: (error: Event) => void
): () => void {
  const wsUrl = `${BASE_URL.replace('http', 'ws')}/ws/jobs/${jobId}`
  const ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      onUpdate(JSON.parse(event.data))
    } catch {
      // ignore malformed frame
    }
  }
  if (onError) ws.onerror = onError
  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) ws.close()
  }
}

export function defaultAdjustments(): Adjustments {
  return { denoise: 50, deblur: 0, detail_recovery: 0, face_correction: false }
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
  }
}

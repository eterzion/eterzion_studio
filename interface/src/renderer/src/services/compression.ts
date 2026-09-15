// specs/008-compression-centre — cliente da Central de Compressão.
//
// Espelha `contracts/api.md` e `app/schemas.py`. Fica separado de `api.ts` por
// tamanho, não por natureza: a Central acrescenta ~10 rotas e enfiá-las num
// arquivo que já passa de mil linhas tornaria as duas coisas piores.
//
// **Nenhum nome de encoder atravessa este arquivo.** O que vem do backend são
// codecs (`h264`, `av1`) e razões em chave (`requires_hardware_encoder`), e é
// isso que a interface traduz — o Princípio V mantém `nvenc` e `libx264` fora do
// fio, e um tipo que os aceitasse aqui seria o primeiro passo para vazarem.
import { BASE_URL } from './api'
import type { MediaKind } from '../constants/compression'

/** Chave, nunca frase: quem exibe traduz (Princípio XIV). */
export type UnavailableReason =
  | 'no_encoder_available'
  | 'requires_hardware_encoder'
  // O que o backend de fato manda (schemas.py). Esta lista tinha
  // 'not_supported_by_build' e 'format_not_writable', que ele nunca envia, e
  // nao tinha este -- a pessoa via o motivo sem traducao.
  | 'unsupported_build'

export interface CapabilityEntry {
  value: string
  available: boolean
  unavailable_reason: UnavailableReason | null
  requires_hardware: boolean
}

export interface ContainerCompatibility {
  video: string[]
  audio: string[]
}

export interface CompressionCapabilities {
  image: { formats: CapabilityEntry[] }
  video: {
    containers: CapabilityEntry[]
    video_codecs: CapabilityEntry[]
    audio_codecs: CapabilityEntry[]
    compatibility: Record<string, ContainerCompatibility>
    hardware: { available: boolean; reason: string | null }
  }
  audio: { formats: CapabilityEntry[]; codecs: CapabilityEntry[] }
  animation: { formats: CapabilityEntry[] }
}

/** `unknown` e não `any`: as configurações variam por tipo de mídia e por modo,
 *  e um `any` aqui apagaria a checagem em todo lugar que as tocasse. Quem lê um
 *  campo específico estreita no ponto de uso. */
export type CompressionSettings = Record<string, unknown>

export type SizeUnit = 'KB' | 'MB' | 'GB'
export interface SizeTarget {
  value: number
  unit: SizeUnit
}

export type EstimateConfidence = 'measured' | 'derived' | 'rough'
export type Feasibility = 'ok' | 'below_floor' | 'already_smaller'

export interface CompressionEstimate {
  original_bytes: number
  estimated_bytes: number
  estimated_saving_bytes: number
  reduction_ratio: number | null
  confidence: EstimateConfidence
  /** O que a estimativa **não** sabe. Uma estimativa sem premissas declaradas é
   *  um palpite com cara de medição. */
  assumptions: string[]
  resolved_settings: CompressionSettings | null
  feasibility: Feasibility
}

export type PresetOrigin = 'builtin' | 'platform' | 'user'

export interface CompressionPreset {
  id: string
  /** Interno: chave traduzível. */
  name_key?: string | null
  /** Do usuário: a palavra que a pessoa escolheu, que não se traduz. */
  name?: string | null
  media_kind: MediaKind
  origin: PresetOrigin
  settings: CompressionSettings
}

export type ConflictPolicy = 'overwrite' | 'rename' | 'ask'

export interface CompressionExport {
  directory?: string | null
  naming_pattern?: string
  conflict_policy?: ConflictPolicy
}

export interface CompressionJobRequest {
  handle_id: string
  media_kind: MediaKind
  settings: CompressionSettings
  target?: SizeTarget | null
  preset_id?: string | null
  /** "Repetir" do historico. Resolvido no backend, como o preset: no modo
   *  Basico os campos tecnicos da configuracao repetida nao podem viajar. */
  history_id?: string | null
  advanced?: boolean
  export?: CompressionExport | null
}

export interface CompressionJobResponse {
  job_id: string
  status: string
  estimate: CompressionEstimate | null
}

/** A recusa vem com `reason` em chave; a frase é da interface. Manter o corpo
 *  inteiro permite a quem trata mostrar o detalhe (qual codec, quanto falta de
 *  disco) sem uma segunda chamada. */
export class CompressionError extends Error {
  constructor(
    readonly status: number,
    readonly reason: string,
    readonly detail: Record<string, unknown>
  ) {
    super(reason)
    this.name = 'CompressionError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init
  })
  if (!response.ok) throw await toError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function toError(response: Response): Promise<CompressionError> {
  let detail: Record<string, unknown> = {}
  try {
    const body = (await response.json()) as { detail?: unknown }
    // FastAPI aninha em `detail`; a validação do Pydantic devolve uma lista.
    // Nos dois casos o que interessa é chegar a um objeto com `reason`.
    if (
      body &&
      typeof body.detail === 'object' &&
      body.detail !== null &&
      !Array.isArray(body.detail)
    ) {
      detail = body.detail as Record<string, unknown>
    } else if (body) {
      detail = { pydantic: body.detail }
    }
  } catch {
    // Corpo não-JSON: o status ainda diz o suficiente para a tela reagir.
  }
  const reason = typeof detail.reason === 'string' ? detail.reason : 'unknown'
  return new CompressionError(response.status, reason, detail)
}

/** O que a sondagem obteve sobre um arquivo importado.
 *
 *  **Quase tudo é opcional, e isso é o ponto** (FR-010): um campo que a sondagem
 *  não conseguiu ler chega ausente, nunca zerado. A interface omite o que não
 *  recebeu em vez de exibir um traço que parece medido. */
export interface CompressionMedia {
  handle_id: string
  display_name: string
  media_kind: MediaKind
  content_key: string
  size_bytes: number
  width?: number | null
  height?: number | null
  duration_seconds?: number | null
  frame_rate?: number | null
  frame_rate_is_variable?: boolean | null
  has_audio?: boolean | null
  has_alpha?: boolean | null
  has_metadata?: boolean | null
  sample_rate?: number | null
  channels?: number | null
  /** Codec do contêiner (`h264`, `opus`), nunca encoder. */
  video_codec?: string | null
  audio_codec?: string | null
  video_bitrate_bps?: number | null
  audio_bitrate_bps?: number | null
  container_bitrate_bps?: number | null
}

/** Importa em dois passos, e a divisão é constitucional, não estilística.
 *
 *  `POST /media/handles` é a **única** rota autorizada a receber um caminho de
 *  disco (terceira condição da exceção do Princípio XIII). Abrir uma segunda
 *  para a Central seria exatamente a erosão que a condição existe para impedir —
 *  sempre parece razoável deixar "só mais uma" receber um caminho.
 *
 *  O segundo passo não carrega caminho nenhum: pergunta pelo identificador. */
export async function registerMedia(path: string): Promise<CompressionMedia> {
  const registrado = await request<{ handle_id: string }>('/media/handles', {
    method: 'POST',
    body: JSON.stringify({ path })
  })
  return request<CompressionMedia>(`/compression/media/${encodeURIComponent(registrado.handle_id)}`)
}

export function getCapabilities(): Promise<CompressionCapabilities> {
  return request<CompressionCapabilities>('/compression/capabilities')
}

export function estimate(body: {
  handle_id: string
  media_kind: MediaKind
  settings: CompressionSettings
  target?: SizeTarget | null
  // Os mesmos da compressao: sem eles a estimativa partiria de outras
  // configuracoes e mostraria um numero que a compressao nao produz.
  preset_id?: string | null
  history_id?: string | null
  advanced?: boolean
}): Promise<CompressionEstimate> {
  return request<CompressionEstimate>('/compression/estimate', {
    method: 'POST',
    body: JSON.stringify(body)
  })
}

export function listPresets(mediaKind?: MediaKind): Promise<{ presets: CompressionPreset[] }> {
  const query = mediaKind ? `?media_kind=${mediaKind}` : ''
  return request<{ presets: CompressionPreset[] }>(`/compression/presets${query}`)
}

export function createPreset(body: {
  name: string
  media_kind: MediaKind
  settings: CompressionSettings
}): Promise<CompressionPreset> {
  return request<CompressionPreset>('/compression/presets', {
    method: 'POST',
    body: JSON.stringify(body)
  })
}

export function updatePreset(
  id: string,
  body: { name?: string; settings?: CompressionSettings }
): Promise<CompressionPreset> {
  return request<CompressionPreset>(`/compression/presets/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(body)
  })
}

export function deletePreset(id: string): Promise<void> {
  return request<void>(`/compression/presets/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function duplicatePreset(id: string, name: string): Promise<CompressionPreset> {
  return request<CompressionPreset>(`/compression/presets/${encodeURIComponent(id)}/duplicate`, {
    method: 'POST',
    body: JSON.stringify({ name })
  })
}

/** Uma compressão concluída, como o histórico a guarda.
 *
 *  `settings_snapshot` é o que **foi usado**; `preset_id` só diz de onde veio.
 *  Repetir parte do snapshot — um preset editado depois faria a repetição
 *  produzir algo diferente do que a entrada exibe (FR-063). */
export interface CompressionHistoryEntry {
  id: string
  display_name: string
  media_kind: MediaKind
  settings_snapshot: CompressionSettings
  preset_id: string | null
  result: Record<string, unknown>
  output_path: string | null
  finished_at: string | null
}

export function listHistory(
  mediaKind?: MediaKind
): Promise<{ entries: CompressionHistoryEntry[] }> {
  const query = mediaKind ? `?media_kind=${mediaKind}` : ''
  return request<{ entries: CompressionHistoryEntry[] }>(`/compression/history${query}`)
}

export function deleteHistoryEntry(id: string): Promise<void> {
  return request<void>(`/compression/history/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function clearHistory(): Promise<void> {
  return request<void>('/compression/history', { method: 'DELETE' })
}

export function createJob(body: CompressionJobRequest): Promise<CompressionJobResponse> {
  return request<CompressionJobResponse>('/compression/jobs', {
    method: 'POST',
    body: JSON.stringify(body)
  })
}

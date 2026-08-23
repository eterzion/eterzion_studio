// specs/008-compression-centre — T044/T046: rodar a compressão e medir o que saiu.
//
// **O resultado vem do job, nunca da estimativa** (FR-022). A previsão está aqui
// ao lado, já calculada e com o formato certo — reaproveitá-la como resultado
// seria invisível até o arquivo no disco não bater com o que a tela afirma.
//
// O WebSocket é a fonte de progresso, e `getJob` é a rede: um socket que cai no
// meio deixaria a barra parada em 60% para sempre, e a compressão teria
// terminado. Uma consulta ao final é barata e transforma um travamento aparente
// num resultado.
import { ref } from 'vue'
import { getJob, type JobStatus } from '../services/api'
import { subscribeJobProgress } from '../services/websocket'
import {
  CompressionError,
  createJob,
  type CompressionExport,
  type CompressionJobRequest,
  type CompressionSettings,
  type SizeTarget
} from '../services/compression'
import type { CompressionResultData } from '../components/compression/CompressionResult.vue'
import type { CompressionMode, MediaKind } from '../constants/compression'

export interface RunRequest {
  handleId: string
  mediaKind: MediaKind
  settings: CompressionSettings
  target: SizeTarget | null
  mode: CompressionMode
  presetId: string | null
  export: CompressionExport
}

export function useCompressionJob() {
  const running = ref(false)
  const progress = ref(0)
  /** Chave de razão, nunca frase — quem exibe traduz (Princípio XIV). */
  const error = ref<string | null>(null)
  const errorDetail = ref<Record<string, unknown>>({})
  const result = ref<CompressionResultData | null>(null)
  const jobId = ref<string | null>(null)

  let unsubscribe: (() => void) | null = null

  async function run(pedido: RunRequest): Promise<void> {
    stop()
    running.value = true
    progress.value = 0
    error.value = null
    errorDetail.value = {}
    result.value = null

    const corpo: CompressionJobRequest = {
      handle_id: pedido.handleId,
      media_kind: pedido.mediaKind,
      settings: pedido.settings,
      target: pedido.target,
      preset_id: pedido.presetId,
      advanced: pedido.mode === 'advanced',
      export: pedido.export
    }

    let criado
    try {
      criado = await createJob(corpo)
    } catch (e) {
      // As recusas do FR-064 chegam aqui, todas antes de qualquer processamento:
      // nada foi escrito, nada precisa ser desfeito.
      running.value = false
      error.value = e instanceof CompressionError ? e.reason : 'unknown'
      errorDetail.value = e instanceof CompressionError ? e.detail : {}
      return
    }

    jobId.value = criado.job_id
    await new Promise<void>((resolve) => {
      unsubscribe = subscribeJobProgress(
        criado.job_id,
        (status) => {
          apply(status)
          if (isFinal(status.status)) resolve()
        },
        () => resolve()
      )
    })

    // A consulta final acontece **sempre**, e não só quando o socket falha: o
    // último quadro pode chegar antes de o job gravar o resultado, e a tela
    // ficaria sem os números de um job que terminou bem.
    try {
      apply(await getJob(criado.job_id))
    } catch {
      if (!error.value && !result.value) error.value = 'unknown'
    }
    stop()
    running.value = false
  }

  function apply(status: JobStatus): void {
    if (typeof status.progress === 'number') progress.value = status.progress
    if (status.status === 'error') {
      error.value = status.error_category ?? 'unknown'
      return
    }
    if (status.status !== 'done') return

    const medido = (status as unknown as { compression?: Record<string, number | boolean> })
      .compression
    if (!medido || !status.output_path) return
    result.value = {
      outputPath: status.output_path,
      originalBytes: Number(medido.original_bytes),
      outputSizeBytes: Number(medido.output_size_bytes),
      savingBytes: Number(medido.saving_bytes),
      reductionRatio:
        medido.reduction_ratio == null ? null : Number(medido.reduction_ratio),
      grew: Boolean(medido.grew),
      elapsedSeconds: Number(medido.elapsed_seconds)
    }
  }

  function isFinal(status: string): boolean {
    return status === 'done' || status === 'error' || status === 'cancelled'
  }

  function stop(): void {
    unsubscribe?.()
    unsubscribe = null
  }

  return { running, progress, error, errorDetail, result, jobId, run, stop }
}

// specs/008-compression-centre — T077/T079/T081: a fila de trabalho.
//
// **N pedidos, não uma rota em lote**, e a decisão está registrada em
// `contracts/api.md`. Uma rota que recebesse a lista inteira devolveria um
// resultado agregado, e quando um arquivo falhasse a resposta teria que carregar
// qual — reconstruindo, pior, o que N pedidos já dão de graça. Com um job por
// arquivo, cancelar um é cancelar um, tentar de novo é repetir um, e o erro
// aponta para o arquivo que o causou.
//
// **Um erro não para a fila.** O contrário é fácil de escrever e destrói o valor
// do lote: quem deixou trinta arquivos processando à noite volta e encontra
// vinte e nove não feitos por causa de um PNG corrompido.
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { cancelJob, getJob, type JobStatus } from '../services/api'
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
import type { RespostaDeConflito } from './usePerguntaDeConflito'

export type BatchItemStatus = 'pending' | 'running' | 'done' | 'error' | 'cancelled'

export interface BatchItem {
  /** O id do item na fila de entrada — o que liga o trabalho ao arquivo. */
  queueId: string
  fileName: string
  handleId: string
  mediaKind: MediaKind
  status: BatchItemStatus
  progress: number
  jobId: string | null
  /** Chave de razão, nunca frase (Princípio XIV). */
  error: string | null
  result: CompressionResultData | null
}

export interface BatchRequest {
  queueId: string
  fileName: string
  handleId: string
  mediaKind: MediaKind
  settings: CompressionSettings
  target: SizeTarget | null
  mode: CompressionMode
  presetId: string | null
  historyId: string | null
  export: CompressionExport
}

export interface CompressionBatchApi {
  items: Ref<BatchItem[]>
  running: Ref<boolean>
  done: ComputedRef<BatchItem[]>
  failed: ComputedRef<BatchItem[]>
  finished: ComputedRef<number>
  overallProgress: ComputedRef<number>
  savedBytes: ComputedRef<number>
  originalBytes: ComputedRef<number>
  run: (pedidos: BatchRequest[]) => Promise<void>
  cancelItem: (queueId: string) => Promise<void>
  cancelAll: () => Promise<void>
  retryFailed: (pedidos: BatchRequest[]) => Promise<void>
  clear: () => void
  stop: () => void
}

export interface CompressionBatchOptions {
  /** A mesma pergunta do job unico (useCompressionJob). */
  perguntarConflito?: (caminho: string) => Promise<RespostaDeConflito>
}

export function useCompressionBatch(options: CompressionBatchOptions = {}): CompressionBatchApi {
  const items = ref<BatchItem[]>([])
  const running = ref(false)

  const unsubscribers = new Map<string, () => void>()
  let cancelled = false

  const done = computed(() => items.value.filter((i) => i.status === 'done'))
  const failed = computed(() => items.value.filter((i) => i.status === 'error'))
  const finished = computed(
    () => items.value.filter((i) => i.status !== 'pending' && i.status !== 'running').length
  )

  /** Progresso geral pela média dos itens, e não pela contagem de concluídos.
   *
   *  Contar concluídos faria a barra ficar parada durante o arquivo mais longo e
   *  depois saltar — exatamente quando a pessoa mais quer saber se algo está
   *  acontecendo. */
  const overallProgress = computed(() => {
    if (!items.value.length) return 0
    const soma = items.value.reduce((total, item) => {
      if (item.status === 'done') return total + 100
      if (item.status === 'error' || item.status === 'cancelled') return total + 100
      return total + item.progress
    }, 0)
    return Math.round(soma / items.value.length)
  })

  /** A economia **medida**, somada — nunca a estimativa (FR-022). */
  const savedBytes = computed(() =>
    done.value.reduce((total, item) => total + (item.result?.savingBytes ?? 0), 0)
  )

  const originalBytes = computed(() =>
    done.value.reduce((total, item) => total + (item.result?.originalBytes ?? 0), 0)
  )

  async function run(pedidos: BatchRequest[]): Promise<void> {
    if (!pedidos.length || running.value) return
    cancelled = false
    running.value = true
    items.value = pedidos.map((p) => ({
      queueId: p.queueId,
      fileName: p.fileName,
      handleId: p.handleId,
      mediaKind: p.mediaKind,
      status: 'pending',
      progress: 0,
      jobId: null,
      error: null,
      result: null
    }))

    // Sequencial de propósito. Comprimir é limitado por CPU, e disparar cinco de
    // uma vez não termina antes — termina junto, cinco vezes mais devagar cada
    // um, com o computador travado no meio. A fila do backend já existe; o que
    // esta ordem preserva é o progresso individual fazer sentido.
    for (const pedido of pedidos) {
      if (cancelled) break
      await _runOne(pedido)
    }

    running.value = false
  }

  async function _runOne(pedido: BatchRequest): Promise<void> {
    const item = items.value.find((i) => i.queueId === pedido.queueId)
    if (!item) return
    item.status = 'running'

    const corpo: CompressionJobRequest = {
      handle_id: pedido.handleId,
      media_kind: pedido.mediaKind,
      settings: pedido.settings,
      target: pedido.target,
      preset_id: pedido.presetId,
      history_id: pedido.historyId,
      advanced: pedido.mode === 'advanced',
      export: pedido.export
    }

    let criado
    try {
      criado = await createJob(corpo)
    } catch (e) {
      if (e instanceof CompressionError && e.reason === 'conflict' && options.perguntarConflito) {
        // A fila espera a resposta deste arquivo antes de seguir para o proximo.
        const resposta = await options.perguntarConflito(String(e.detail.path ?? ''))
        if (resposta) {
          return _runOne({ ...pedido, export: { ...pedido.export, conflict_policy: resposta } })
        }
        item.status = 'cancelled'
        return
      }
      // Uma recusa é deste arquivo, e a fila segue. Parar aqui faria um arquivo
      // com configuração impossível levar os outros junto.
      item.status = 'error'
      item.error = e instanceof CompressionError ? e.reason : 'unknown'
      return
    }

    item.jobId = criado.job_id

    await new Promise<void>((resolve) => {
      const parar = subscribeJobProgress(
        criado.job_id,
        (status) => {
          _apply(item, status)
          if (_isFinal(status.status)) resolve()
        },
        () => resolve()
      )
      unsubscribers.set(criado.job_id, parar)
    })

    // Consulta final sempre: o último quadro do socket pode chegar antes de o
    // job gravar o resultado, e o item ficaria sem os números de um trabalho que
    // terminou bem.
    try {
      _apply(item, await getJob(criado.job_id))
    } catch {
      if (item.status === 'running') {
        item.status = 'error'
        item.error = 'unknown'
      }
    }
    unsubscribers.get(criado.job_id)?.()
    unsubscribers.delete(criado.job_id)

    if (item.status === 'running') item.status = 'done'
  }

  function _apply(item: BatchItem, status: JobStatus): void {
    if (typeof status.progress === 'number') item.progress = status.progress
    if (status.status === 'error') {
      item.status = 'error'
      // O motivo antes da categoria, como no job unico (useCompressionJob).
      item.error = status.error_reason ?? status.error_category ?? 'unknown'
      return
    }
    if (status.status === 'cancelled') {
      item.status = 'cancelled'
      return
    }
    if (status.status !== 'done') return

    const medido = (status as unknown as { compression?: Record<string, unknown> }).compression
    if (medido && status.output_path) {
      item.result = {
        outputPath: status.output_path,
        originalBytes: Number(medido.original_bytes),
        outputSizeBytes: Number(medido.output_size_bytes),
        savingBytes: Number(medido.saving_bytes),
        reductionRatio: medido.reduction_ratio == null ? null : Number(medido.reduction_ratio),
        grew: Boolean(medido.grew),
        elapsedSeconds: Number(medido.elapsed_seconds),
        applied: (medido.applied as Record<string, unknown> | undefined) ?? null
      }
    }
    item.status = 'done'
    item.progress = 100
  }

  function _isFinal(status: string): boolean {
    return status === 'done' || status === 'error' || status === 'cancelled'
  }

  /** Cancela **um** item. Os outros seguem — é a propriedade que justifica um
   *  job por arquivo em vez de uma rota em lote. */
  async function cancelItem(queueId: string): Promise<void> {
    const item = items.value.find((i) => i.queueId === queueId)
    if (!item) return
    if (item.jobId) {
      try {
        await cancelJob(item.jobId)
      } catch {
        // Um job que já terminou responde 404 ao cancelamento. Não é erro: o
        // efeito pedido — que ele não continue — já vale.
      }
    }
    item.status = 'cancelled'
  }

  /** Cancela a fila inteira: o que está rodando e o que ainda não começou. */
  async function cancelAll(): Promise<void> {
    cancelled = true
    const pendentes = items.value.filter((i) => i.status === 'pending' || i.status === 'running')
    await Promise.all(pendentes.map((i) => cancelItem(i.queueId)))
  }

  /** Tenta de novo só o que falhou.
   *
   *  Refazer a fila inteira desperdiçaria o que já deu certo, e — pior — pode
   *  colidir com os arquivos já exportados, obrigando a pessoa a responder à
   *  pergunta de conflito para trabalho que ela não pediu de novo. */
  async function retryFailed(pedidos: BatchRequest[]): Promise<void> {
    const paraRefazer = pedidos.filter((p) =>
      items.value.some((i) => i.queueId === p.queueId && i.status === 'error')
    )
    if (!paraRefazer.length || running.value) return

    cancelled = false
    running.value = true
    for (const pedido of paraRefazer) {
      if (cancelled) break
      const item = items.value.find((i) => i.queueId === pedido.queueId)
      if (item) {
        item.error = null
        item.progress = 0
        item.result = null
      }
      await _runOne(pedido)
    }
    running.value = false
  }

  function clear(): void {
    stop()
    items.value = []
  }

  function stop(): void {
    cancelled = true
    for (const parar of unsubscribers.values()) parar()
    unsubscribers.clear()
  }

  return {
    items,
    running,
    done,
    failed,
    finished,
    overallProgress,
    savedBytes,
    originalBytes,
    run,
    cancelItem,
    cancelAll,
    retryFailed,
    clear,
    stop
  }
}

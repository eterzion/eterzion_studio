// specs/008-compression-centre — T030: a estimativa, sem uma chamada por tecla.
//
// A estimativa é chamada a cada mudança de controle (FR-018), e "cada mudança"
// inclui arrastar um slider — o que sem supressão de rajada vira uma chamada por
// pixel do arraste. O atraso não é cosmético: cada chamada de imagem recorta e
// codifica cinco amostras, e uma rajada delas deixa a interface pior do que
// nenhuma estimativa deixaria.
//
// A outra metade do problema é a **ordem de chegada**. Requisições em voo podem
// responder fora de ordem, e uma resposta antiga que chega depois da nova
// escreveria por cima do número certo com o errado. O contador de geração abaixo
// é o que impede isso; um `AbortController` sozinho não impediria, porque
// abortar não é instantâneo.
import { readonly, ref, watch, type Ref } from 'vue'
import {
  CompressionError,
  estimate as requestEstimate,
  type CompressionEstimate,
  type CompressionSettings,
  type SizeTarget
} from '../services/compression'
import type { MediaKind } from '../constants/compression'

const DEBOUNCE_MS = 250

export interface EstimateSource {
  handleId: Ref<string | null>
  mediaKind: Ref<MediaKind>
  settings: Ref<CompressionSettings>
  target: Ref<SizeTarget | null>
}

export function useCompressionEstimate(source: EstimateSource) {
  const estimate = ref<CompressionEstimate | null>(null)
  const loading = ref(false)
  /** Chave de razão, nunca frase: quem exibe traduz (Princípio XIV). */
  const error = ref<string | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null
  let generation = 0

  async function run(): Promise<void> {
    const handle = source.handleId.value
    if (!handle) {
      estimate.value = null
      return
    }
    const mine = ++generation
    loading.value = true
    error.value = null
    try {
      const resultado = await requestEstimate({
        handle_id: handle,
        media_kind: source.mediaKind.value,
        settings: source.settings.value,
        target: source.target.value
      })
      // Chegou tarde: outra estimativa já foi pedida depois desta, e escrever
      // aqui mostraria o número da configuração anterior.
      if (mine !== generation) return
      estimate.value = resultado
    } catch (e) {
      if (mine !== generation) return
      // Uma estimativa que falhou não pode deixar a anterior no lugar: o número
      // continuaria ali, agora descrevendo configurações que não são mais as da
      // tela — mais enganoso que espaço vazio.
      estimate.value = null
      error.value = e instanceof CompressionError ? e.reason : 'estimate_failed'
    } finally {
      if (mine === generation) loading.value = false
    }
  }

  function schedule(): void {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      void run()
    }, DEBOUNCE_MS)
  }

  watch(
    () => [
      source.handleId.value,
      source.mediaKind.value,
      JSON.stringify(source.settings.value),
      JSON.stringify(source.target.value)
    ],
    schedule,
    { immediate: true }
  )

  /** Descarta o que estiver em voo e o que estiver agendado. Chamada ao sair da
   *  tela — sem isto, uma resposta que chega depois escreveria num estado que
   *  ninguém está olhando. */
  function stop(): void {
    generation++
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    loading.value = false
  }

  return {
    estimate: readonly(estimate),
    loading: readonly(loading),
    error: readonly(error),
    refresh: run,
    stop
  }
}

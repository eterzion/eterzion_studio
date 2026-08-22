// specs/008-compression-centre — T025e/T025g: a fila de entrada da Central.
//
// **Acrescentar, nunca substituir** (FR-006). Soltar um segundo lote sobre o
// primeiro é o gesto de quem quer os dois; uma fila que se substitui apagaria
// silenciosamente o trabalho de importação anterior, e a pessoa só descobriria
// ao procurar um arquivo que sumiu.
//
// O tipo de cada arquivo vem do **backend**, que o lê do conteúdo (FR-007). A
// interface não adivinha por extensão: um `.png` com bytes JPEG e um `.gif` de
// um quadro só chegariam classificados errado, e os controles oferecidos seriam
// os do formato que o arquivo não é.
import { computed, ref } from 'vue'
import { api, hasNativeApi } from '../services/native'
import {
  CompressionError,
  registerMedia,
  type CompressionMedia
} from '../services/compression'
import type { MediaKind } from '../constants/compression'

export interface QueueItem {
  /** Estável e local: o `handle_id` só existe depois do registro, e a lista
   *  precisa de chave antes disso para poder mostrar o item importando. */
  id: string
  path: string
  fileName: string
  status: 'importing' | 'ready' | 'rejected'
  media: CompressionMedia | null
  /** Chave de razão, nunca frase — quem exibe traduz (Princípio XIV). */
  reason: string | null
}

let contador = 0

export function useCompressionQueue() {
  const items = ref<QueueItem[]>([])
  const activeId = ref<string | null>(null)
  const importing = ref(false)

  const active = computed(() => items.value.find((i) => i.id === activeId.value) ?? null)
  const ready = computed(() => items.value.filter((i) => i.status === 'ready'))

  function byKind(kind: MediaKind): QueueItem[] {
    return ready.value.filter((i) => i.media?.media_kind === kind)
  }

  async function add(paths: string[]): Promise<void> {
    if (!paths.length) return
    importing.value = true

    // Os itens entram na lista **antes** do registro, já visíveis: registrar
    // primeiro deixaria a tela parada durante a sondagem de um lote grande, e
    // parado é indistinguível de travado.
    const novos: QueueItem[] = paths.map((path) => ({
      id: `q${++contador}`,
      path,
      fileName: baseName(path),
      status: 'importing',
      media: null,
      reason: null
    }))
    items.value = [...items.value, ...novos]

    for (const item of novos) {
      try {
        item.media = await registerMedia(item.path)
        item.status = 'ready'
      } catch (e) {
        // Um arquivo recusado **fica na lista**, marcado. Removê-lo em silêncio
        // deixaria a pessoa contando arquivos e achando que soltou de menos.
        item.status = 'rejected'
        item.reason = e instanceof CompressionError ? e.reason : 'unreadable'
      }
      if (!activeId.value && item.status === 'ready') activeId.value = item.id
    }

    importing.value = false
  }

  async function pick(): Promise<void> {
    if (!hasNativeApi) return
    const resultado = await api.selectFiles(['image', 'video', 'audio'])
    if (resultado.canceled) return
    await add(resultado.files.map((f) => f.path))
  }

  /** Arquivos soltos vêm como `File`; o caminho real só existe pela ponte do
   *  Electron — no navegador não há caminho, e a Central não tem o que fazer. */
  async function addDropped(files: File[]): Promise<void> {
    if (!hasNativeApi) return
    await add(files.map((f) => api.getPathForFile(f)).filter(Boolean))
  }

  function remove(id: string): void {
    const restantes = items.value.filter((i) => i.id !== id)
    items.value = restantes
    if (activeId.value === id) {
      activeId.value = restantes.find((i) => i.status === 'ready')?.id ?? null
    }
  }

  function clear(): void {
    items.value = []
    activeId.value = null
  }

  function select(id: string): void {
    activeId.value = id
  }

  return { items, activeId, active, ready, importing, byKind, add, addDropped, pick, remove, clear, select }
}

function baseName(path: string): string {
  // Sem `path.basename` no renderer, e os dois separadores aparecem: o Windows
  // aceita ambos, e um caminho vindo de um arraste pode ter os dois misturados.
  const partes = path.split(/[\/]/)
  return partes[partes.length - 1] || path
}

import { reactive } from 'vue'
import { installComponent, listComponents, type ComponentSummary } from '../services/api'
import { api, hasNativeApi } from '../services/native'

// Baixa os modelos que o instalador pediu ("Baixar os modelos de IA depois de
// ativar"), assim que a licenca fica ativa. O pedido e o estado desta conta
// vem do processo principal (src/main/installerOptions.ts).
//
// **Um modelo de cada vez.** O `POST /components/{id}/install` so' dispara o
// download e nao reporta bytes (mesma razao da tela de Componentes). Em serie,
// da' para mostrar "2 de 6" -- um progresso que e' verdade. Em paralelo, a
// barra ficaria parada e depois saltaria.
//
// **Em segundo plano.** O app segue usavel: musica, compressao e conversao nao
// dependem de modelo, e um recurso cujo modelo ainda nao chegou continua
// baixando no primeiro uso, como sempre.
//
// **Falhou, fica pendente.** Sem internet ou com um download interrompido, o
// estado da conta nao vira "concluido", e a proxima abertura tenta de novo.

export type FaseModelosIniciais = 'inativo' | 'baixando' | 'pronto' | 'erro'

export const modelosIniciais = reactive({
  fase: 'inativo' as FaseModelosIniciais,
  total: 0,
  concluidos: 0,
  visivel: false
})

export interface DependenciasModelosIniciais {
  estado(): Promise<'pendente' | 'concluido' | null>
  concluir(): Promise<void>
  listar(): Promise<ComponentSummary[]>
  instalar(id: string): Promise<unknown>
  esperar(ms: number): Promise<void>
}

const producao: DependenciasModelosIniciais = {
  estado: () => (hasNativeApi ? api.getInitialModelsState() : Promise.resolve(null)),
  concluir: () => (hasNativeApi ? api.completeInitialModels() : Promise.resolve()),
  listar: listComponents,
  instalar: installComponent,
  esperar: (ms) => new Promise((r) => setTimeout(r, ms))
}

const INTERVALO_MS = 2000
// Um download travado nao pode prender o aviso para sempre. Os modelos atuais
// tem ate' ~56 MB; 15 minutos cobre uma conexao lenta com folga.
const LIMITE_POR_MODELO_MS = 15 * 60 * 1000

/** O que falta baixar: disponivel nesta versao, nao embutido, nao instalado. */
export function faltando(componentes: ComponentSummary[]): ComponentSummary[] {
  return componentes.filter(
    (c) => c.available && !c.built_in && c.install_state === 'not_installed'
  )
}

async function aguardarInstalado(id: string, deps: DependenciasModelosIniciais): Promise<boolean> {
  for (let esperado = 0; esperado < LIMITE_POR_MODELO_MS; esperado += INTERVALO_MS) {
    await deps.esperar(INTERVALO_MS)
    const atual = (await deps.listar()).find((c) => c.id === id)
    if (!atual) return false
    if (atual.install_state === 'installed' || atual.install_state === 'update_available') {
      return true
    }
    // De volta a "nao instalado": o download terminou em erro.
    if (atual.install_state === 'not_installed') return false
  }
  return false
}

let emAndamento = false

/** Chamada quando a licenca fica ativa. Roda uma vez por sessao. */
export async function baixarModelosIniciais(
  deps: DependenciasModelosIniciais = producao
): Promise<void> {
  if (emAndamento || modelosIniciais.fase !== 'inativo') return
  emAndamento = true
  try {
    if ((await deps.estado()) !== 'pendente') return

    const lista = faltando(await deps.listar())
    if (lista.length === 0) {
      // Ja' estava tudo aqui (reinstalacao, ou baixados pela tela de
      // Componentes): nada a mostrar, so' encerrar o pedido.
      await deps.concluir()
      return
    }

    modelosIniciais.total = lista.length
    modelosIniciais.concluidos = 0
    modelosIniciais.fase = 'baixando'
    modelosIniciais.visivel = true

    let falhou = false
    for (const componente of lista) {
      try {
        await deps.instalar(componente.id)
        if (await aguardarInstalado(componente.id, deps)) modelosIniciais.concluidos++
        else falhou = true
      } catch {
        falhou = true
      }
    }

    if (falhou) {
      modelosIniciais.fase = 'erro'
      modelosIniciais.visivel = true
      return
    }
    await deps.concluir()
    modelosIniciais.fase = 'pronto'
  } catch {
    // Nem a lista de componentes veio (API fora do ar): tenta na proxima
    // abertura, sem aviso -- nao ha' nada util a dizer agora.
    modelosIniciais.fase = 'inativo'
  } finally {
    emAndamento = false
  }
}

export function fecharAvisoModelosIniciais(): void {
  // Fechar esconde o aviso; o download, se ainda estiver rodando, continua.
  modelosIniciais.visivel = false
}

/** So' para os testes: volta ao estado de uma sessao nova. */
export function _reiniciarParaTeste(): void {
  modelosIniciais.fase = 'inativo'
  modelosIniciais.total = 0
  modelosIniciais.concluidos = 0
  modelosIniciais.visivel = false
  emAndamento = false
}

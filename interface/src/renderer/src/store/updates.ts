import { reactive, watch } from 'vue'
import { api, hasNativeApi, type UpdatePhase, type UpdateSnapshot } from '../services/native'
import { countActiveJobs } from '../services/api'
import { settingsState } from './settings'

// A atualizacao em si acontece no processo principal (src/main/updater.ts):
// baixa em segundo plano e instala quando o app fecha. Este store so' espelha
// o estado de la' e guarda o que e' da interface -- o aviso, o pedido de ir
// ate' a secao, a confirmacao antes de reiniciar.

/** A versao cujo aviso ja' apareceu. O aviso sai uma vez por versao, nao a
 *  cada abertura: depois disso o selo da barra lateral e' o lembrete. */
const AVISO_KEY = 'eterzion-studio:update-toast-shown'

interface UpdatesState extends UpdateSnapshot {
  toastVisible: boolean
  /** Configuracoes deve rolar ate' a secao Atualizacoes ao abrir. */
  focusRequested: boolean
  /** Processamentos em andamento quando se pediu para reiniciar; com valor, a
   *  secao mostra a confirmacao. */
  confirmActiveJobs: number | null
  installing: boolean
}

export const updatesState = reactive<UpdatesState>({
  phase: 'idle' as UpdatePhase,
  version: null,
  percent: null,
  transferred: null,
  totalBytes: null,
  notes: null,
  toastVisible: false,
  focusRequested: false,
  confirmActiveJobs: null,
  installing: false
})

function avisoJaMostrado(version: string): boolean {
  try {
    if (localStorage.getItem(AVISO_KEY) === version) return true
    localStorage.setItem(AVISO_KEY, version)
  } catch {
    // Sem armazenamento, o aviso pode repetir numa proxima abertura: melhor
    // que nunca aparecer.
  }
  return false
}

function apply(snapshot: UpdateSnapshot): void {
  const eraPronta = updatesState.phase === 'ready'
  updatesState.phase = snapshot.phase
  updatesState.version = snapshot.version
  updatesState.percent = snapshot.percent
  updatesState.transferred = snapshot.transferred
  updatesState.totalBytes = snapshot.totalBytes
  updatesState.notes = snapshot.notes
  if (snapshot.phase === 'ready' && !eraPronta && snapshot.version) {
    if (!avisoJaMostrado(snapshot.version)) updatesState.toastVisible = true
  }
}

let started = false

/** Chamado uma vez na abertura (App.vue). */
export async function initUpdates(): Promise<void> {
  if (!hasNativeApi || started) return
  started = true
  api.onUpdateState(apply)
  try {
    apply(await api.getUpdateState())
  } catch {
    // Sem o canal, a secao fica em 'idle' e o app segue normal.
  }
  // O processo principal espera esta preferencia para comecar a procurar (e,
  // sem ela, assume ligada depois de um prazo -- ver updater.ts).
  watch(
    () => settingsState.autoCheckUpdates,
    (enabled) => void api.setAutoCheckUpdates(enabled).catch(() => undefined),
    { immediate: true }
  )
}

export async function checkForUpdates(): Promise<void> {
  if (!hasNativeApi) return
  try {
    apply(await api.checkForUpdates())
  } catch {
    updatesState.phase = 'error'
  }
}

/**
 * Primeiro passo de "Reiniciar e atualizar". Reiniciar cancela o que estiver
 * processando, entao, havendo algo, arma a confirmacao em vez de reiniciar.
 * Se o backend nao responder, nada esta' processando nele.
 */
export async function requestRestart(): Promise<'restarting' | 'confirm'> {
  let ativos = 0
  try {
    ativos = await countActiveJobs()
  } catch {
    ativos = 0
  }
  if (ativos > 0) {
    updatesState.confirmActiveJobs = ativos
    return 'confirm'
  }
  await installNow()
  return 'restarting'
}

export async function installNow(): Promise<void> {
  updatesState.confirmActiveJobs = null
  updatesState.toastVisible = false
  updatesState.installing = true
  const ok = await api.installUpdate().catch(() => false)
  if (!ok) updatesState.installing = false
}

export function cancelRestart(): void {
  updatesState.confirmActiveJobs = null
}

export function dismissToast(): void {
  updatesState.toastVisible = false
}

export function requestUpdatesFocus(): void {
  updatesState.focusRequested = true
}

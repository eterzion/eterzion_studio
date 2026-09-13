import { app, BrowserWindow, ipcMain } from 'electron'
import { autoUpdater, type UpdateInfo } from 'electron-updater'

import { API_BASE_URL } from './apiProcess'

/**
 * Atualização automática.
 *
 * Existe porque, sem ela, toda correção — de segurança, de bug, de domínio —
 * só alcança um usuário se ele baixar e instalar de novo por conta própria.
 * Não havia como saber quantos tinham feito, nem como forçar. Isso apareceu
 * de forma concreta na migração de domínio: o CSP vai empacotado no HTML, e
 * uma cópia instalada bloqueava o host novo mesmo com o servidor respondendo.
 *
 * O comportamento é deliberadamente discreto: baixa em segundo plano e
 * instala quando o app for fechado. Nada de diálogo interrompendo um upscale
 * em andamento, e nada de reinício forçado. A interface acompanha pelo estado
 * que este módulo publica (`updater:state`): avisa quando a versão nova está
 * pronta e oferece reiniciar agora, mas quem decide é a pessoa.
 */

/** Uma verificação ao abrir, e outra a cada seis horas para sessões longas. */
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000

/**
 * A preferência "Procurar atualizações automaticamente" mora no renderer
 * (localStorage, store/settings.ts), e é ele quem a informa aqui ao abrir.
 * Se essa mensagem nunca chegar -- um erro no renderer, uma tela que não
 * montou --, o app não pode ficar sem atualização para sempre: é justamente
 * por atualização que a correção desse erro chegaria. Passado este prazo, vale
 * o padrão (ligado).
 */
const ESPERA_PREFERENCIA_MS = 2 * 60 * 1000

/**
 * As atualizações saem do CDN privado do Studio (`cdn.eterzion.com/studio/`,
 * um bucket do R2), e não mais de um repositório público do GitHub. O Worker de
 * lá só serve com uma assinatura que o servidor de licenças emite -- e só para
 * instalação ativada com licença ativa. O backend local pede essa assinatura
 * (assinando o pedido com a chave desta instalação) e a entrega aqui.
 *
 * `useMultipleRangeRequest: false`: o R2 serve um intervalo por pedido. Com
 * vários intervalos num pedido só (o padrão), o download diferencial -- o que
 * baixa só o que mudou entre versões -- não funcionaria.
 */
type CredencialCdn = { base: string; token: string; exp: number; renew_after: number }

/** O backend pode estar subindo quando o app abre: algumas tentativas
 *  espaçadas antes de desistir desta rodada. */
const TENTATIVAS_CREDENCIAL = 6
const INTERVALO_TENTATIVA_MS = 10_000

/**
 * O que a interface precisa saber. `disabled`: build de desenvolvimento, sem
 * atualização possível. `error` cobre tanto falha de rede quanto ficar sem
 * credencial do CDN (licença inativa, servidor fora): para quem lê, as duas
 * dizem "não deu para procurar agora", e o detalhe fica no console.
 *
 * Espelhado em preload/index.ts e renderer/src/services/native.ts -- o preload
 * não importa do main.
 */
export type UpdatePhase =
  'disabled' | 'idle' | 'checking' | 'downloading' | 'ready' | 'up_to_date' | 'error'

export interface UpdateSnapshot {
  phase: UpdatePhase
  /** A versão encontrada (downloading/ready). */
  version: string | null
  /** 0-100, só em downloading. */
  percent: number | null
  /** As novidades que vieram no latest.yml, em texto; null se a versão não trouxe. */
  notes: string | null
}

let snapshot: UpdateSnapshot = { phase: 'idle', version: null, percent: null, notes: null }

function publish(next: Partial<UpdateSnapshot>): void {
  snapshot = { ...snapshot, ...next }
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) win.webContents.send('updater:state', snapshot)
  }
}

/** `releaseNotes` chega como texto ou, em alguns provedores, como lista por
 *  versão. A interface só mostra texto. */
function notesFrom(info: UpdateInfo): string | null {
  const notes = info.releaseNotes
  if (!notes) return null
  if (typeof notes === 'string') return notes.trim() || null
  const texto = notes
    .map((n) => n.note ?? '')
    .join('\n')
    .trim()
  return texto || null
}

async function credencialCdn(): Promise<CredencialCdn | null> {
  for (let tentativa = 0; tentativa < TENTATIVAS_CREDENCIAL; tentativa += 1) {
    try {
      const res = await fetch(`${API_BASE_URL}/downloads/token`)
      // 204: sem licença ativa, sem rede ou CDN não configurado. Não é erro
      // de rede; só não há o que verificar agora.
      if (res.status === 204) return null
      if (res.ok) return (await res.json()) as CredencialCdn
    } catch {
      // backend ainda subindo
    }
    await new Promise((resolve) => setTimeout(resolve, INTERVALO_TENTATIVA_MS))
  }
  return null
}

let periodicCheck: NodeJS.Timeout | undefined
let preferenceTimeout: NodeJS.Timeout | undefined
let autoCheck: boolean | null = null
let checking = false

function setAutoCheck(enabled: boolean): void {
  if (preferenceTimeout) {
    clearTimeout(preferenceTimeout)
    preferenceTimeout = undefined
  }
  const antes = autoCheck
  autoCheck = enabled
  if (!enabled) {
    if (periodicCheck) clearInterval(periodicCheck)
    periodicCheck = undefined
    return
  }
  if (!periodicCheck) {
    periodicCheck = setInterval(() => void checkQuietly(), CHECK_INTERVAL_MS)
    periodicCheck.unref?.()
  }
  // Ao abrir (primeira preferência recebida) e ao religar: procura já.
  if (antes !== true) void checkQuietly()
}

export function initializeUpdater(): void {
  ipcMain.handle('updater:get-state', () => snapshot)

  // Em desenvolvimento não há artefato assinado nem release para comparar, e
  // o electron-updater falharia a cada abertura. `isPackaged` é o mesmo sinal
  // que o próprio electron-builder usa. Os canais continuam registrados: a
  // tela pergunta o estado e recebe `disabled`.
  if (!app.isPackaged) {
    snapshot = { ...snapshot, phase: 'disabled' }
    ipcMain.handle('updater:check', () => snapshot)
    ipcMain.handle('updater:install', () => false)
    ipcMain.handle('updater:set-auto-check', () => undefined)
    return
  }

  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true

  // Uma versão de pré-lançamento nunca deve chegar a quem instalou a estável.
  autoUpdater.allowPrerelease = false

  autoUpdater.on('update-available', (info) => {
    console.info('[updater] versão disponível', info.version)
    publish({ phase: 'downloading', version: info.version, percent: 0, notes: notesFrom(info) })
  })

  autoUpdater.on('download-progress', (progress) => {
    publish({ phase: 'downloading', percent: Math.round(progress.percent) })
  })

  autoUpdater.on('update-not-available', () => {
    console.info('[updater] já está na versão mais recente')
    if (snapshot.phase !== 'ready') publish({ phase: 'up_to_date', percent: null })
  })

  autoUpdater.on('update-downloaded', (info) => {
    console.info('[updater] baixada, será instalada ao fechar', info.version)
    publish({ phase: 'ready', version: info.version, percent: null, notes: notesFrom(info) })
  })

  // Falha de atualização não pode derrubar o app nem aparecer como erro
  // técnico: ficar sem internet, ou atrás de um proxy corporativo, é normal e
  // não impede ninguém de usar o programa. A interface diz só "tente mais tarde".
  autoUpdater.on('error', (error) => {
    console.warn('[updater] verificação falhou', error?.message ?? error)
    if (snapshot.phase !== 'ready') publish({ phase: 'error', percent: null })
  })

  ipcMain.handle('updater:check', async () => {
    await checkQuietly()
    return snapshot
  })

  // Reinicia já, instalando a versão baixada. `isSilent`: o instalador roda
  // sem janela, como na instalação ao fechar; `isForceRunAfter`: o app abre de
  // novo sozinho -- quem pediu "reiniciar" espera vê-lo voltar.
  ipcMain.handle('updater:install', () => {
    if (snapshot.phase !== 'ready') return false
    setImmediate(() => autoUpdater.quitAndInstall(true, true))
    return true
  })

  ipcMain.handle('updater:set-auto-check', (_event, enabled: unknown) => {
    setAutoCheck(enabled !== false)
  })

  preferenceTimeout = setTimeout(() => {
    if (autoCheck === null) setAutoCheck(true)
  }, ESPERA_PREFERENCIA_MS)
  preferenceTimeout.unref?.()
}

export function stopUpdater(): void {
  if (periodicCheck) {
    clearInterval(periodicCheck)
    periodicCheck = undefined
  }
  if (preferenceTimeout) {
    clearTimeout(preferenceTimeout)
    preferenceTimeout = undefined
  }
}

/**
 * O `catch` é redundante com o handler de erro acima e existe mesmo assim: o
 * `checkForUpdates` rejeita a promise ALÉM de emitir o evento, e uma rejeição
 * não tratada derruba o processo principal em algumas versões do Electron.
 *
 * Uma verificação por vez: o clique em "Procurar atualizações" durante a
 * verificação periódica não abre outra. E nada a procurar com uma versão já
 * baixando ou pronta -- a próxima só vale depois de instalar esta.
 */
async function checkQuietly(): Promise<void> {
  if (checking || snapshot.phase === 'downloading' || snapshot.phase === 'ready') return
  checking = true
  try {
    publish({ phase: 'checking' })
    const credencial = await credencialCdn()
    if (!credencial) {
      console.info('[updater] sem credencial do CDN nesta rodada; verificação adiada')
      publish({ phase: 'error' })
      return
    }
    // A cada rodada, porque a credencial vence: a de agora vale por horas, e a
    // próxima verificação é daqui a seis.
    autoUpdater.setFeedURL({
      provider: 'generic',
      url: `${credencial.base}/updates`,
      useMultipleRangeRequest: false
    })
    autoUpdater.requestHeaders = { Authorization: `Bearer ${credencial.token}` }
    await autoUpdater.checkForUpdates()
  } catch {
    // Já registrado pelo handler de erro.
  } finally {
    checking = false
  }
}

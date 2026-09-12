import { app } from 'electron'
import { autoUpdater } from 'electron-updater'

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
 * em andamento, e nada de reinício forçado.
 */

/** Uma verificação ao abrir, e outra a cada seis horas para sessões longas. */
const CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000

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

async function credencialCdn(): Promise<CredencialCdn | null> {
  for (let tentativa = 0; tentativa < TENTATIVAS_CREDENCIAL; tentativa += 1) {
    try {
      const res = await fetch(`${API_BASE_URL}/downloads/token`)
      // 204: sem licença ativa, sem rede ou CDN não configurado. Não é erro;
      // só não há o que verificar agora.
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

export function initializeUpdater(): void {
  // Em desenvolvimento não há artefato assinado nem release para comparar, e
  // o electron-updater falharia a cada abertura. `isPackaged` é o mesmo sinal
  // que o próprio electron-builder usa.
  if (!app.isPackaged) {
    return
  }

  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true

  // Uma versão de pré-lançamento nunca deve chegar a quem instalou a estável.
  autoUpdater.allowPrerelease = false

  autoUpdater.on('update-available', (info) => {
    console.info('[updater] versão disponível', info.version)
  })

  autoUpdater.on('update-not-available', () => {
    console.info('[updater] já está na versão mais recente')
  })

  autoUpdater.on('update-downloaded', (info) => {
    console.info('[updater] baixada, será instalada ao fechar', info.version)
  })

  // Falha de atualização não pode derrubar o app nem aparecer para o usuário:
  // ficar sem internet, ou atrás de um proxy corporativo, é normal e não
  // impede ninguém de usar o programa.
  autoUpdater.on('error', (error) => {
    console.warn('[updater] verificação falhou', error?.message ?? error)
  })

  void checkQuietly()

  periodicCheck = setInterval(() => void checkQuietly(), CHECK_INTERVAL_MS)
  periodicCheck.unref?.()
}

export function stopUpdater(): void {
  if (periodicCheck) {
    clearInterval(periodicCheck)
    periodicCheck = undefined
  }
}

/**
 * O `catch` é redundante com o handler de erro acima e existe mesmo assim: o
 * `checkForUpdates` rejeita a promise ALÉM de emitir o evento, e uma rejeição
 * não tratada derruba o processo principal em algumas versões do Electron.
 */
async function checkQuietly(): Promise<void> {
  try {
    const credencial = await credencialCdn()
    if (!credencial) {
      console.info('[updater] sem credencial do CDN nesta rodada; verificação adiada')
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
  }
}

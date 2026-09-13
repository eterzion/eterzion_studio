import { reactive } from 'vue'
import {
  activateLicenseKey,
  BackendUnreachableError,
  getLicenseStatus,
  releaseLicense,
  type LicenseState
} from '../services/api'

// T036/T038: this store is now a thin wrapper over the LOCAL API's /license/*
// facade — it used to call the remote licensing service directly from the
// renderer, bypassing the real gate mechanism (offline tolerance, revalidation
// caching) entirely. The local API is always the one source of truth now.

export type UiLicenseStatus = LicenseState | 'checking' | 'error'

interface LicenseStoreState {
  status: UiLicenseStatus
  installationsUsed: number
  installationsLimit: number
  offlineDaysRemaining: number | null
  licenseLast4: string | null
  email: string | null
  error: string | null
  // Set the first time a check resolves to a usable status this session.
  // Once true, a later 'error' (can't reach the server right now) degrades
  // to an inline warning instead of yanking the user back to the full-page
  // block — only 'not_activated'/'blocked' are confirmed-bad states that
  // always warrant the full block, an unreachable server does not.
  everUsable: boolean
}

export const licenseState = reactive<LicenseStoreState>({
  status: 'checking',
  installationsUsed: 0,
  installationsLimit: 0,
  offlineDaysRemaining: null,
  licenseLast4: null,
  email: null,
  error: null,
  everUsable: false
})

/** Media/processing screens are usable in these states — offline_tolerance
 *  and offline_expiring both still work (FR-056/FR-057), and so does
 *  not_configured (no licensing service set up + ASTROS_DEV_ALLOW_UNLICENSED,
 *  the default out-of-the-box dev/local config — app.licensing's check_gate()
 *  already allows job creation in this state, the UI must not contradict it).
 *  Only blocked/not_activated require going through LicenseActivationView.vue
 *  (T039). */
export function isUsableLicenseState(status: UiLicenseStatus): boolean {
  return (
    status === 'active' ||
    status === 'offline_tolerance' ||
    status === 'offline_expiring' ||
    status === 'not_configured'
  )
}

/** Whether the app shell should be replaced entirely by
 *  LicenseActivationView.vue (no sidebar, no content). 'not_activated' and
 *  'blocked' always do — they're confirmed states, not just an unreachable
 *  server. 'checking'/'error' only do it before the first successful check
 *  this session; after that they degrade to an inline badge/banner instead. */
export function isHardBlocked(status: UiLicenseStatus, everUsable: boolean): boolean {
  if (status === 'not_activated' || status === 'blocked') return true
  if (isUsableLicenseState(status)) return false
  return !everUsable
}

export async function refreshLicenseStatus(): Promise<void> {
  licenseState.status = 'checking'
  licenseState.error = null
  try {
    const body = await getLicenseStatus()
    licenseState.status = body.state
    licenseState.installationsUsed = body.installations_used
    licenseState.installationsLimit = body.installations_limit
    licenseState.offlineDaysRemaining = body.offline_days_remaining
    licenseState.licenseLast4 = body.license_last4 ?? null
    licenseState.email = body.email ?? null
  } catch (error) {
    licenseState.status = 'error'
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
  if (isUsableLicenseState(licenseState.status)) licenseState.everUsable = true
}

/** Quanto esperar o backend local aceitar conexões, na abertura.
 *
 *  O executável empacotado importa torch e spandrel antes de escutar, e isso
 *  leva dezenas de segundos numa máquina fria. Consultar uma vez só, como esta
 *  função fazia, garantia a tela de erro em TODA abertura -- dizendo "verifique
 *  sua conexão de internet" para um serviço que roda em 127.0.0.1 e apenas
 *  ainda não subiu. O usuário via um erro de licença que não era de licença, e
 *  a saída era clicar em "Try again" sem saber por quê.
 *
 *  Generoso de propósito: esperar demais custa uma tela de carregamento;
 *  esperar de menos custa um erro que assusta e não orienta. */
const ESPERA_BACKEND_MS = 90_000
const INTERVALO_TENTATIVA_MS = 1_000

const dormir = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

/** Called once at app startup (App.vue). */
export async function initLicense(): Promise<void> {
  const limite = Date.now() + ESPERA_BACKEND_MS

  for (;;) {
    licenseState.status = 'checking'
    licenseState.error = null
    try {
      const body = await getLicenseStatus()
      licenseState.status = body.state
      licenseState.installationsUsed = body.installations_used
      licenseState.installationsLimit = body.installations_limit
      licenseState.offlineDaysRemaining = body.offline_days_remaining
      licenseState.licenseLast4 = body.license_last4 ?? null
      licenseState.email = body.email ?? null
      if (isUsableLicenseState(licenseState.status)) licenseState.everUsable = true
      return
    } catch (error) {
      // Só a ausência de resposta merece nova tentativa. Um erro vindo do
      // backend é resposta: ele subiu, e insistir esconderia o problema atrás
      // de uma tela de carregamento longa.
      if (!(error instanceof BackendUnreachableError) || Date.now() >= limite) {
        licenseState.status = 'error'
        licenseState.error = error instanceof Error ? error.message : String(error)
        return
      }
    }
    await dormir(INTERVALO_TENTATIVA_MS)
  }
}

export async function activateLicense(licenseId: string): Promise<void> {
  licenseState.status = 'checking'
  licenseState.error = null
  try {
    await activateLicenseKey(licenseId)
    await refreshLicenseStatus()
  } catch (error) {
    licenseState.status = 'error'
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
}

export async function deactivateLicense(): Promise<void> {
  licenseState.status = 'checking'
  licenseState.error = null
  try {
    await releaseLicense()
    await refreshLicenseStatus()
  } catch (error) {
    licenseState.status = 'error'
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
}

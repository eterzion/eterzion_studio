import { reactive } from 'vue'
import {
  activateLicenseKey,
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
  error: null,
  everUsable: false
})

/** Media/processing screens are usable in these states — offline_tolerance
 *  and offline_expiring both still work (FR-056/FR-057), only blocked/
 *  not_activated require going through LicenseActivationView.vue (T039). */
export function isUsableLicenseState(status: UiLicenseStatus): boolean {
  return status === 'active' || status === 'offline_tolerance' || status === 'offline_expiring'
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
  } catch (error) {
    licenseState.status = 'error'
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
  if (isUsableLicenseState(licenseState.status)) licenseState.everUsable = true
}

/** Called once at app startup (App.vue). */
export async function initLicense(): Promise<void> {
  await refreshLicenseStatus()
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

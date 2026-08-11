import { reactive } from 'vue'
import { activateLicenseKey, getLicenseStatus, releaseLicense, type LicenseState } from '../backend'

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
}

export const licenseState = reactive<LicenseStoreState>({
  status: 'checking',
  installationsUsed: 0,
  installationsLimit: 0,
  offlineDaysRemaining: null,
  error: null
})

/** Media/processing screens are usable in these states — offline_tolerance
 *  and offline_expiring both still work (FR-056/FR-057), only blocked/
 *  not_activated require going through LicenseActivationView.vue (T039). */
export function isUsableLicenseState(status: UiLicenseStatus): boolean {
  return status === 'active' || status === 'offline_tolerance' || status === 'offline_expiring'
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

import { reactive } from 'vue'
import { settingsState } from './settings'

const API_BASE_URL = 'http://127.0.0.1:8765'
const STORAGE_KEY = 'astros-upscale:license'

export type LicenseStatus = 'unconfigured' | 'checking' | 'not_activated' | 'activated' | 'error'

interface StoredLicense {
  licenseId: string
}

interface LicenseState {
  status: LicenseStatus
  installId: string | null
  licenseId: string | null
  error: string | null
}

export const licenseState = reactive<LicenseState>({
  status: 'unconfigured',
  installId: null,
  licenseId: null,
  error: null
})

function loadPersisted(): StoredLicense | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persist(value: StoredLicense | null): void {
  if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  else localStorage.removeItem(STORAGE_KEY)
}

interface IdentityResponse {
  install_id: string
  signing_public_key_b64: string
  encryption_public_key_b64: string
}

async function fetchIdentity(): Promise<IdentityResponse> {
  const resp = await fetch(`${API_BASE_URL}/identity`)
  if (!resp.ok)
    throw new Error(`Não foi possível obter a identidade da instalação (HTTP ${resp.status}).`)
  return resp.json()
}

/** Called once at app startup. Not an error if licensingServiceUrl is empty —
 * that's the default (no license infra deployed by default, see
 * docs/processing-protection-architecture.md) and just means the module
 * shows "não configurado" instead of trying to reach a service that doesn't
 * exist for this install. */
export async function initLicense(): Promise<void> {
  if (!settingsState.licensingServiceUrl) {
    licenseState.status = 'unconfigured'
    return
  }
  const persisted = loadPersisted()
  licenseState.licenseId = persisted?.licenseId ?? null
  licenseState.status = persisted ? 'activated' : 'not_activated'
  try {
    const identity = await fetchIdentity()
    licenseState.installId = identity.install_id
  } catch (error) {
    // Diagnostic only — the local API might just not be up yet. Doesn't
    // downgrade an already-activated status; activation only needs the
    // identity at the moment of activating, not on every load.
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
}

export async function activateLicense(licenseId: string): Promise<void> {
  if (!settingsState.licensingServiceUrl) {
    licenseState.status = 'error'
    licenseState.error = 'Nenhum servidor de licenciamento configurado (Configurações > Avançado).'
    return
  }
  licenseState.status = 'checking'
  licenseState.error = null
  try {
    const identity = licenseState.installId ? null : await fetchIdentity()
    if (identity) licenseState.installId = identity.install_id
    const fullIdentity = identity ?? (await fetchIdentity())
    const resp = await fetch(`${settingsState.licensingServiceUrl}/activations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        license_id: licenseId,
        install_id: fullIdentity.install_id,
        signing_public_key_b64: fullIdentity.signing_public_key_b64,
        encryption_public_key_b64: fullIdentity.encryption_public_key_b64
      })
    })
    if (!resp.ok) {
      const detail = await resp.json().catch(() => null)
      throw new Error(detail?.detail ?? `Falha na ativação (HTTP ${resp.status}).`)
    }
    licenseState.licenseId = licenseId
    licenseState.status = 'activated'
    persist({ licenseId })
  } catch (error) {
    licenseState.status = 'error'
    licenseState.error = error instanceof Error ? error.message : String(error)
  }
}

export function deactivateLicense(): void {
  licenseState.licenseId = null
  licenseState.status = settingsState.licensingServiceUrl ? 'not_activated' : 'unconfigured'
  licenseState.error = null
  persist(null)
}

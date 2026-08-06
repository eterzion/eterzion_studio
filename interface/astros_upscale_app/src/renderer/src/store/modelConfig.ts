import { reactive } from 'vue'
import type { ModelLicense } from '../data/modelLicenses'

const STORAGE_KEY = 'astros-upscale:default-model-config'

// Per the spec: never persist just the model id — snapshot the full license state at
// selection time, since permissions/versions can change on a later registry update.
export interface SavedModelConfig {
  modelId: string
  modelName: string
  modelVersion: string
  developer: string
  license: string
  commercialUse: ModelLicense['commercialUse']
  modificationAllowed: ModelLicense['modificationAllowed']
  redistributionAllowed: ModelLicense['redistributionAllowed']
  attributionRequired: ModelLicense['attributionRequired']
  restrictions: string[]
  licenseSourceUrl: string
  licenseSourceKind: ModelLicense['sourceKind']
  verifiedAt: string
  savedAt: string
}

export const modelConfigState = reactive<{ saved: SavedModelConfig | null }>({
  saved: load()
})

function load(): SavedModelConfig | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveDefaultModel(config: SavedModelConfig): void {
  modelConfigState.saved = config
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
}

export function clearDefaultModel(): void {
  modelConfigState.saved = null
  localStorage.removeItem(STORAGE_KEY)
}

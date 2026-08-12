import { ref, type ComputedRef, type Ref } from 'vue'
import { hasNativeApi } from '../nativeBridge'
import { previewDenoise, type DenoisePreview } from '../apiClient'

type DenoisePresetKey = 'low' | 'medium' | 'high' | 'custom'

const DENOISE_PRESETS: { key: DenoisePresetKey; label: string; strength: number | null }[] = [
  { key: 'low', label: 'Baixo', strength: 20 },
  { key: 'medium', label: 'Médio', strength: 45 },
  { key: 'high', label: 'Alto', strength: 75 },
  { key: 'custom', label: 'Personalizado', strength: null }
]

interface DenoiseJob {
  sourcePath: string
  scaleConfig: {
    denoiseFilterEnabled: boolean
    denoiseFilterStrength: number
  }
}

// Extracted from ImageEditorView.vue — the OpenCV-based denoise filter preview
// (independent of the AI model) is a self-contained async state machine: its
// own debounce, its own request/race-guard, no reference to viewport, export,
// or scale-config concerns. See specs/003-interface-restructure/research.md
// Decisão 3.
export function useDenoisePreview<T extends DenoiseJob>(
  job: ComputedRef<T | undefined>
): {
  DENOISE_PRESETS: { key: DenoisePresetKey; label: string; strength: number | null }[]
  denoiseActivePresetKey: Ref<DenoisePresetKey>
  denoisePreview: Ref<DenoisePreview | null>
  denoisePreviewLoading: Ref<boolean>
  denoisePreviewError: Ref<string | null>
  requestDenoisePreview: () => void
  setDenoisePreset: (preset: { key: DenoisePresetKey; strength: number | null }) => void
  toggleDenoiseFilter: () => void
} {
  // A ref, not inferred from the numeric value — a custom value can legitimately
  // coincide with a preset's number, and that shouldn't silently reassign it back
  // to that preset (or hide the "Personalizado" slider the user just opened).
  const denoiseActivePresetKey = ref<DenoisePresetKey>('medium')
  const denoisePreview = ref<DenoisePreview | null>(null)
  const denoisePreviewLoading = ref(false)
  const denoisePreviewError = ref<string | null>(null)
  let denoisePreviewTimer: ReturnType<typeof setTimeout> | undefined
  let denoisePreviewRequestId = 0

  function requestDenoisePreview(): void {
    const j = job.value
    if (!j || !j.scaleConfig.denoiseFilterEnabled || !hasNativeApi) return
    clearTimeout(denoisePreviewTimer)
    denoisePreviewTimer = setTimeout(async () => {
      const requestId = ++denoisePreviewRequestId
      denoisePreviewLoading.value = true
      denoisePreviewError.value = null
      try {
        const result = await previewDenoise(j.sourcePath, j.scaleConfig.denoiseFilterStrength)
        if (requestId === denoisePreviewRequestId) denoisePreview.value = result
      } catch (error) {
        if (requestId === denoisePreviewRequestId) {
          denoisePreviewError.value =
            error instanceof Error ? error.message : 'Falha ao gerar prévia.'
        }
      } finally {
        if (requestId === denoisePreviewRequestId) denoisePreviewLoading.value = false
      }
    }, 350)
  }

  function setDenoisePreset(preset: { key: DenoisePresetKey; strength: number | null }): void {
    if (!job.value) return
    denoiseActivePresetKey.value = preset.key
    if (preset.strength !== null) job.value.scaleConfig.denoiseFilterStrength = preset.strength
    requestDenoisePreview()
  }

  function toggleDenoiseFilter(): void {
    if (!job.value) return
    job.value.scaleConfig.denoiseFilterEnabled = !job.value.scaleConfig.denoiseFilterEnabled
    denoisePreview.value = null
    if (job.value.scaleConfig.denoiseFilterEnabled) {
      const matched = DENOISE_PRESETS.find(
        (p) => p.strength === job.value!.scaleConfig.denoiseFilterStrength
      )
      denoiseActivePresetKey.value = matched?.key ?? 'custom'
      requestDenoisePreview()
    }
  }

  return {
    DENOISE_PRESETS,
    denoiseActivePresetKey,
    denoisePreview,
    denoisePreviewLoading,
    denoisePreviewError,
    requestDenoisePreview,
    setDenoisePreset,
    toggleDenoiseFilter
  }
}

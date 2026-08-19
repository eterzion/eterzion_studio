import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { i18n } from '../i18n'
import { hasNativeApi } from '../services/native'
import { previewDenoise, type DenoisePreview } from '../services/api'

type DenoisePresetKey = 'low' | 'medium' | 'high' | 'custom'

// A function, not a const: a const built at import keeps whichever language
// was active then, and the preset row would stay in it forever.
const DENOISE_STRENGTHS: { key: DenoisePresetKey; strength: number | null }[] = [
  { key: 'low', strength: 20 },
  { key: 'medium', strength: 45 },
  { key: 'high', strength: 75 },
  { key: 'custom', strength: null }
]

export function denoisePresets(): {
  key: DenoisePresetKey
  label: string
  strength: number | null
}[] {
  const t = i18n.global.t
  return DENOISE_STRENGTHS.map((preset) => ({
    ...preset,
    label: t(`misc.denoise${preset.key[0].toUpperCase()}${preset.key.slice(1)}`)
  }))
}

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
  denoisePresets: ComputedRef<{ key: DenoisePresetKey; label: string; strength: number | null }[]>
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
  // to that preset (or hide the "Custom" slider the user just opened).
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
            error instanceof Error ? error.message : i18n.global.t('misc.previewFailed')
        }
      } finally {
        if (requestId === denoisePreviewRequestId) denoisePreviewLoading.value = false
      }
    }, 350)
  }

  // Switching to another file used to leave the previous one's before/after on
  // screen: the preview was only ever cleared by the toggle, and nothing watched
  // which job was active. Invalidating the in-flight request id too, so a reply
  // for the old file cannot land on the new one.
  watch(
    // sourcePath, not a job id: it is the file the preview is OF, and it is the
    // only identity this composable's minimal job contract carries.
    () => job.value?.sourcePath,
    () => {
      clearTimeout(denoisePreviewTimer)
      denoisePreviewRequestId++
      denoisePreview.value = null
      denoisePreviewError.value = null
      denoisePreviewLoading.value = false
      if (job.value?.scaleConfig.denoiseFilterEnabled) requestDenoisePreview()
    }
  )

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
      const matched = DENOISE_STRENGTHS.find(
        (p) => p.strength === job.value!.scaleConfig.denoiseFilterStrength
      )
      denoiseActivePresetKey.value = matched?.key ?? 'custom'
      requestDenoisePreview()
    }
  }

  return {
    denoisePresets: computed(() => denoisePresets()),
    denoiseActivePresetKey,
    denoisePreview,
    denoisePreviewLoading,
    denoisePreviewError,
    requestDenoisePreview,
    setDenoisePreset,
    toggleDenoiseFilter
  }
}

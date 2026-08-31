import { computed, reactive, ref, type Ref } from 'vue'

// T043 (specs/007-video-editor-player) — the five edit families, per video.
//
// Neutral values and ranges mirror api/eterzion_upscale_api/app/schemas.py, which
// in turn mirrors FFmpeg's `eq` filter. The three have to agree: the schema
// validates, the filter graph applies, and the shader previews. A bound changed
// in one place and not the others makes the preview lie (FR-015).

/** The six colour controls, each with its own on/off — the same shape the image
 *  editor uses for its filters, and for the same reason: a value parked at 0.6
 *  while the control is off is a decision the person made and can come back to,
 *  which a slider dragged back to neutral throws away.
 *
 *  `<key>_enabled` is mechanical on purpose: the panel derives the flag from the
 *  slider key, so adding a control cannot leave a flag behind. */
export interface VideoAdjustments {
  brightness: number
  brightness_enabled: boolean
  contrast: number
  contrast_enabled: boolean
  saturation: number
  saturation_enabled: boolean
  gamma: number
  gamma_enabled: boolean
  hue_degrees: number
  hue_degrees_enabled: boolean
  sharpness: number
  sharpness_enabled: boolean
}

export type AdjustmentKey =
  'brightness' | 'contrast' | 'saturation' | 'gamma' | 'hue_degrees' | 'sharpness'

export const ADJUSTMENT_NEUTRAL: Record<AdjustmentKey, number> = {
  brightness: 0,
  contrast: 1,
  saturation: 1,
  gamma: 1,
  hue_degrees: 0,
  sharpness: 0
}

/** The adjustments as they should actually be applied: a control that is off
 *  reads as its neutral value.
 *
 *  Every consumer must go through this — the shader, the disclosure check, and
 *  anything else that asks "what will this look like". The API honours the flags
 *  on its own side; if the preview read the raw values instead, a disabled
 *  control would show in the preview and not in the export, which is precisely
 *  what FR-015 forbids. */
export function effectiveAdjustments(a: VideoAdjustments): Record<AdjustmentKey, number> {
  const out = {} as Record<AdjustmentKey, number>
  for (const key of Object.keys(ADJUSTMENT_NEUTRAL) as AdjustmentKey[]) {
    out[key] = a[`${key}_enabled`] ? a[key] : ADJUSTMENT_NEUTRAL[key]
  }
  return out
}

export interface VideoEffects {
  denoise_enabled: boolean
  denoise_strength: number
  blur_enabled: boolean
  blur_strength: number
  grain_enabled: boolean
  grain_strength: number
}

export interface VideoCrop {
  x: number
  y: number
  width: number
  height: number
}

export interface VideoTransform {
  crop: VideoCrop | null
  rotation_degrees: 0 | 90 | 180 | 270
  flip_horizontal: boolean
  flip_vertical: boolean
  output_width: number | null
  output_height: number | null
}

export interface VideoTrim {
  start_seconds: number
  end_seconds: number
}

export interface VideoAudioEdit {
  mode: 'keep' | 'mute' | 'remove'
  volume: number
}

export interface VideoEditSet {
  adjustments: VideoAdjustments
  effects: VideoEffects
  transform: VideoTransform
  trim: VideoTrim | null
  audio: VideoAudioEdit
}

export function neutralAdjustments(): VideoAdjustments {
  // Todos desligados, como os filtros do editor de imagem começam. Um vídeo
  // recém-aberto não tem ajuste nenhum aplicado, que é o que já acontecia
  // quando os seis nasciam no valor neutro.
  return {
    brightness: 0,
    brightness_enabled: false,
    contrast: 1,
    contrast_enabled: false,
    saturation: 1,
    saturation_enabled: false,
    gamma: 1,
    gamma_enabled: false,
    hue_degrees: 0,
    hue_degrees_enabled: false,
    sharpness: 0,
    sharpness_enabled: false
  }
}

export function neutralEffects(): VideoEffects {
  return {
    denoise_enabled: false,
    denoise_strength: 45,
    blur_enabled: false,
    blur_strength: 0,
    grain_enabled: false,
    grain_strength: 0
  }
}

export function neutralTransform(): VideoTransform {
  return {
    crop: null,
    rotation_degrees: 0,
    flip_horizontal: false,
    flip_vertical: false,
    output_width: null,
    output_height: null
  }
}

export function neutralEdits(): VideoEditSet {
  return {
    adjustments: neutralAdjustments(),
    effects: neutralEffects(),
    transform: neutralTransform(),
    trim: null,
    audio: { mode: 'keep', volume: 1 }
  }
}

/** What the renderer's shader CANNOT reproduce faithfully, and therefore what
 *  triggers FR-015's disclosure. One place decides this, rather than each panel
 *  guessing — a panel that guessed wrong would show a silently untruthful
 *  preview, which is the exact failure FR-015 names.
 *
 *  Sharpness is in this list even though it lives under `adjustments` rather
 *  than `effects`. It maps to FFmpeg's `unsharp`, a 5×5 convolution; the shader
 *  implements `eq` and `hue` exactly and does not attempt unsharp. Claiming
 *  sharpness is previewed because it sits next to brightness would be the
 *  category error this function exists to prevent. */
export function hasUnpreviewableEffects(edits: VideoEditSet): boolean {
  const e = edits.effects
  return (
    (e.denoise_enabled && e.denoise_strength > 0) ||
    (e.blur_enabled && e.blur_strength > 0) ||
    (e.grain_enabled && e.grain_strength > 0) ||
    effectiveAdjustments(edits.adjustments).sharpness > 0
  )
}

export interface VideoEditsStore {
  /** Edits for the active video, or a neutral set when none is selected. */
  current: Ref<VideoEditSet>
  editsFor: (handleId: string) => VideoEditSet
  /** FR-004: discards ALL five families, not only the image adjustments. */
  reset: (handleId: string) => void
  /** Só os ajustes de cor. Um botão por painel: quem mexeu no brilho e quer
   *  recomeçar não deveria perder o corte e o áudio junto. */
  resetAdjustments: (handleId: string) => void
  /** Só os efeitos. Mesmo motivo. */
  resetEffects: (handleId: string) => void
  forget: (handleId: string) => void
  isNeutral: Ref<boolean>
  needsDisclosure: Ref<boolean>
}

export function useVideoEdits(activeHandleId: Ref<string | null>): VideoEditsStore {
  // Keyed by handle, so switching videos cannot carry one file's edits onto
  // another (FR-003) — the bug that would otherwise be invisible until export.
  const byHandle = reactive(new Map<string, VideoEditSet>())
  const fallback = ref(neutralEdits())

  function editsFor(handleId: string): VideoEditSet {
    let edits = byHandle.get(handleId)
    if (!edits) {
      edits = neutralEdits()
      byHandle.set(handleId, edits)
    }
    return edits
  }

  const current = computed<VideoEditSet>(() =>
    activeHandleId.value ? editsFor(activeHandleId.value) : fallback.value
  )

  function reset(handleId: string): void {
    // Replacing the whole set rather than resetting adjustments in place: FR-004
    // was ambiguous about this until the spec disambiguated "ajustes" from
    // "edições", and partial reset is exactly the wrong reading.
    byHandle.set(handleId, neutralEdits())
  }

  function resetAdjustments(handleId: string): void {
    Object.assign(editsFor(handleId).adjustments, neutralAdjustments())
  }

  function resetEffects(handleId: string): void {
    Object.assign(editsFor(handleId).effects, neutralEffects())
  }

  function forget(handleId: string): void {
    byHandle.delete(handleId)
  }

  const isNeutral = computed(() => JSON.stringify(current.value) === JSON.stringify(neutralEdits()))

  const needsDisclosure = computed(() => hasUnpreviewableEffects(current.value))

  return {
    current: current as Ref<VideoEditSet>,
    editsFor,
    reset,
    resetAdjustments,
    resetEffects,
    forget,
    isNeutral,
    needsDisclosure
  }
}

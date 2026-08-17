import { computed, reactive, ref, type Ref } from 'vue'

// T043 (specs/007-video-editor-player) — the five edit families, per video.
//
// Neutral values and ranges mirror api/astros_upscale_api/app/schemas.py, which
// in turn mirrors FFmpeg's `eq` filter. The three have to agree: the schema
// validates, the filter graph applies, and the shader previews. A bound changed
// in one place and not the others makes the preview lie (FR-015).

export interface VideoAdjustments {
  brightness: number
  contrast: number
  saturation: number
  gamma: number
  hue_degrees: number
  sharpness: number
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
  return { brightness: 0, contrast: 1, saturation: 1, gamma: 1, hue_degrees: 0, sharpness: 0 }
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
    edits.adjustments.sharpness > 0
  )
}

export interface VideoEditsStore {
  /** Edits for the active video, or a neutral set when none is selected. */
  current: Ref<VideoEditSet>
  editsFor: (handleId: string) => VideoEditSet
  /** FR-004: discards ALL five families, not only the image adjustments. */
  reset: (handleId: string) => void
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

  function forget(handleId: string): void {
    byHandle.delete(handleId)
  }

  const isNeutral = computed(() => JSON.stringify(current.value) === JSON.stringify(neutralEdits()))

  const needsDisclosure = computed(() => hasUnpreviewableEffects(current.value))

  return {
    current: current as Ref<VideoEditSet>,
    editsFor,
    reset,
    forget,
    isNeutral,
    needsDisclosure
  }
}

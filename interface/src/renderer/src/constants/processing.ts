import { i18n } from '../i18n'
import type { Profile, VideoContainer } from '../services/api'

// Shared by the Imagem, Vídeo and Áudio screens. These were only on Imagem, and
// copying them into the other two would have made three places to keep in sync —
// the same divergence that let one screen's wording drift from another's.

// Functions, not consts. A module-level const with translated labels is
// evaluated once at import and keeps whichever language was active then —
// switching the language afterwards leaves these two lists behind. Called
// inside a computed(), they re-run when the locale changes.

export interface LabelledOption<T = string> {
  value: T
  label: string
  description: string
}

const PROFILE_VALUES: Profile[] = ['fast', 'balanced', 'quality']
const DEVICE_VALUES = ['auto', 'cpu', 'cuda']

export function profileOptions(): LabelledOption<Profile>[] {
  const t = i18n.global.t
  return PROFILE_VALUES.map((value) => ({
    value,
    label: t(`processing.profile.${value}.label`),
    description: t(`processing.profile.${value}.description`)
  }))
}

export function deviceOptions(): LabelledOption[] {
  const t = i18n.global.t
  return DEVICE_VALUES.map((value) => ({
    value,
    label: t(`processing.device.${value}.label`),
    description: t(`processing.device.${value}.description`)
  }))
}

// specs/007-video-editor-player. Labels are placeholders resolved through i18n
// at the point of use (Princípio XIV) — the value is what reaches the API, and
// it is the only thing about the output format the client gets to choose.
// Which of these is actually usable comes from GET /video/export-options, not
// from this list: permitted is not present (Princípio XIII).
export const VIDEO_CONTAINER_OPTIONS: { value: VideoContainer; extension: string }[] = [
  { value: 'mp4', extension: '.mp4' },
  { value: 'mkv', extension: '.mkv' },
  { value: 'webm', extension: '.webm' },
  { value: 'mov', extension: '.mov' }
]

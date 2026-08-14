import type { Profile } from '../services/api'

// Shared by the Imagem, Vídeo and Áudio screens. These were only on Imagem, and
// copying them into the other two would have made three places to keep in sync —
// the same divergence that let one screen's wording drift from another's.

export const PROFILE_OPTIONS: { value: Profile; label: string; description: string }[] = [
  { value: 'fast', label: 'Rápido', description: 'Menos detalhe, termina antes' },
  { value: 'balanced', label: 'Equilibrado', description: 'Meio-termo entre detalhe e tempo' },
  { value: 'quality', label: 'Qualidade', description: 'Mais detalhe, leva mais tempo' }
]

export const DEVICE_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: 'auto', label: 'Automático', description: 'GPU quando houver, CPU caso contrário.' },
  { value: 'cpu', label: 'CPU', description: 'Mais lento, funciona em qualquer máquina.' },
  { value: 'cuda', label: 'GPU (CUDA)', description: 'Mais rápido, exige driver NVIDIA.' }
]

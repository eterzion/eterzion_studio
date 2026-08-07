// License metadata for every model in astros_upscale's registry (astros_upscale/core.py).
// Sourced from each model's OFFICIAL repository/model card — never inferred from the
// model's name — per the requirement that commercial-use claims must be traceable to
// an official source. Where the source couldn't be confirmed, `verified: false` and the
// commercial field is 'unverified' — never assume permissive just because nothing was found.
//
// Verified 2026-08-06. Re-check whenever a model's registry entry changes version/URL —
// license terms are pinned per specific release, not per model family.

export type CommercialUse = 'allowed' | 'restricted' | 'not_allowed' | 'unverified'

export interface ModelLicense {
  license: string // SPDX identifier where one exists (e.g. "BSD-3-Clause"), else the stated name
  developer: string
  commercialUse: CommercialUse
  modificationAllowed: boolean | 'unverified'
  redistributionAllowed: boolean | 'unverified'
  attributionRequired: boolean | 'unverified'
  restrictions: string[]
  sourceUrl: string
  sourceKind: 'official-repo-license' | 'official-model-card' | 'openmodeldb' | 'unverified'
  verifiedAt: string // ISO date
  needsManualReview?: string // set when a source conflict or ambiguity was found
}

export const MODEL_LICENSES: Record<string, ModelLicense> = {
  'realesrgan-x4': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  'realesrgan-x2': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  'realesr-general': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  'realesrnet-x4': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  ultrasharp: {
    license: 'CC-BY-NC-SA-4.0',
    developer: 'Kim2091',
    commercialUse: 'not_allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: [
      'Somente uso não comercial.',
      'Derivados devem manter a mesma licença (Share-Alike).',
      'Crédito ao autor original obrigatório.'
    ],
    sourceUrl: 'https://openmodeldb.info/models/4x-UltraSharp',
    sourceKind: 'openmodeldb',
    verifiedAt: '2026-08-06',
    needsManualReview:
      'O mirror de download usado (huggingface.co/uwg/upscaler) está marcado como "MIT" no próprio repositório, ' +
      'o que conflita com a licença CC-BY-NC-SA-4.0 atribuída ao modelo original pelo OpenModelDB. ' +
      'Priorizamos o OpenModelDB (fonte dedicada a este tipo de modelo), mas confirme manualmente antes de uso comercial.'
  },
  'nomos-webphoto': {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/4xNomosWebPhoto_RealPLKSR',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'nomos2-dat2': {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/4xNomos2_hq_dat2',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'realesrgan-anime': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  animesharp: {
    license: 'CC-BY-NC-SA-4.0',
    developer: 'Kim2091',
    commercialUse: 'not_allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: [
      'Somente uso não comercial.',
      'Derivados devem manter a mesma licença (Share-Alike).',
      'Crédito ao autor original obrigatório.'
    ],
    sourceUrl: 'https://huggingface.co/Kim2091/AnimeSharp',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'hfa2k-span': {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/2xHFA2kSPAN',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'realesr-animevideo': {
    license: 'BSD-3-Clause',
    developer: 'Xintao Wang (xinntao) / Real-ESRGAN',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Preservar aviso de copyright e isenção de responsabilidade do BSD-3-Clause.'],
    sourceUrl: 'https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE',
    sourceKind: 'official-repo-license',
    verifiedAt: '2026-08-06'
  },
  'hfa2k-avc': {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/2xHFA2kAVCCompact',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'nomosuni-span': {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/2xNomosUni_span_multijpg_ldl',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  },
  'liveaction-span': {
    license: 'CC-BY-NC-SA-4.0',
    developer: 'jcj83429',
    commercialUse: 'not_allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: [
      'Somente uso não comercial.',
      'Derivados devem manter a mesma licença (Share-Alike).',
      'Crédito ao autor original obrigatório.'
    ],
    sourceUrl: 'https://openmodeldb.info/models/2x-LiveActionV1-SPAN',
    sourceKind: 'openmodeldb',
    verifiedAt: '2026-08-06'
  },
  'nmkd-siax': {
    license: 'WTFPL',
    developer: 'Nmkd (Helaman)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: false,
    restrictions: [],
    sourceUrl: 'https://openmodeldb.info/models/4x-NMKD-Siax-CX',
    sourceKind: 'openmodeldb',
    verifiedAt: '2026-08-06'
  },
  'nmkd-superscale': {
    license: 'Não verificada',
    developer: 'Nmkd (Helaman)',
    commercialUse: 'unverified',
    modificationAllowed: 'unverified',
    redistributionAllowed: 'unverified',
    attributionRequired: 'unverified',
    restrictions: [],
    sourceUrl: 'https://openmodeldb.info/?q=NMKD-Superscale',
    sourceKind: 'unverified',
    verifiedAt: '2026-08-06',
    needsManualReview:
      'Não foi possível confirmar a licença exata numa fonte oficial (a página específica do modelo no ' +
      'OpenModelDB não pôde ser localizada de forma confiável). Não usar comercialmente sem verificação manual.'
  },
  denoise: {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://openmodeldb.info/models/1x-DeNoise-realplksr-otf',
    sourceKind: 'openmodeldb',
    verifiedAt: '2026-08-06'
  },
  dejpg: {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://openmodeldb.info/models/1x-DeJPG-realplksr-otf',
    sourceKind: 'openmodeldb',
    verifiedAt: '2026-08-06'
  },
  deh264: {
    license: 'CC-BY-4.0',
    developer: 'Philip Hofmann (Phhofm)',
    commercialUse: 'allowed',
    modificationAllowed: true,
    redistributionAllowed: true,
    attributionRequired: true,
    restrictions: ['Crédito ao autor original obrigatório.'],
    sourceUrl: 'https://huggingface.co/Phips/1xDeH264_realplksr',
    sourceKind: 'official-model-card',
    verifiedAt: '2026-08-06'
  }
}

export function getModelLicense(name: string): ModelLicense | undefined {
  return MODEL_LICENSES[name]
}

export const COMMERCIAL_USE_COPY: Record<
  CommercialUse,
  { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }
> = {
  allowed: { label: 'Uso comercial permitido', tone: 'success' },
  restricted: { label: 'Uso comercial com restrições', tone: 'warning' },
  not_allowed: { label: 'Somente uso não comercial', tone: 'danger' },
  unverified: { label: 'Licença não verificada — verificar antes de usar', tone: 'neutral' }
}

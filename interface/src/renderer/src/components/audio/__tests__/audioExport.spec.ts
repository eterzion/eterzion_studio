import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

// A exportacao do Audio: o painel oferece o que a maquina grava e so' mostra a
// qualidade onde ela existe; a tela manda o destino junto com o job, e
// "Perguntar" pergunta antes de processar.

const api = vi.hoisted(() => ({
  createLocalJob: vi.fn(),
  processJob: vi.fn(async () => undefined),
  getJob: vi.fn(async () => ({ status: 'queued' }))
}))
vi.mock('../../../services/api', async (original) => ({
  ...(await original<typeof import('../../../services/api')>()),
  ...api
}))
vi.mock('../../../services/compression', async (original) => ({
  ...(await original<typeof import('../../../services/compression')>()),
  getCapabilities: vi.fn(async () => ({
    audio: {
      formats: ['wav', 'flac', 'mp3', 'm4a', 'ogg', 'opus'].map((value) => ({
        value,
        available: value !== 'opus',
        unavailable_reason: value === 'opus' ? 'no_encoder_available' : null,
        requires_hardware: false
      })),
      codecs: []
    }
  }))
}))
vi.mock('../../../services/websocket', () => ({ subscribeJobProgress: () => () => undefined }))
vi.mock('../../../store/history', () => ({ recordSimpleJob: vi.fn() }))

import AudioExportPanel, { type AudioExport } from '../AudioExportPanel.vue'
import AudioView from '../../../views/AudioView.vue'
import { ComponentActionError } from '../../../services/api'
import { audioQueue, type AudioJob } from '../../../store/audioQueue'
import { i18n, setLocale } from '../../../i18n'

beforeEach(() => setLocale('pt-BR'))
afterEach(() => {
  vi.clearAllMocks()
  audioQueue.jobs.splice(0)
  audioQueue.activeId = null
  document.body.innerHTML = ''
})

const base = (mudanca: Partial<AudioExport> = {}): AudioExport => ({
  format: 'keep',
  profile: 'balanced',
  directory: null,
  filename: null,
  conflict: 'rename',
  ...mudanca
})

function painel(modelValue: AudioExport, sourceName = 'voz.mp3'): ReturnType<typeof mount> {
  return mount(AudioExportPanel, {
    props: { modelValue, sourceName },
    global: { plugins: [i18n] }
  })
}

const temQualidade = (w: ReturnType<typeof mount>): boolean =>
  w.text().includes(i18n.global.t('audio.export.qualityLabel'))

describe('AudioExportPanel', () => {
  it('a qualidade so aparece em formato com perda', async () => {
    expect(temQualidade(painel(base({ format: 'mp3' })))).toBe(true)
    expect(temQualidade(painel(base({ format: 'flac' })))).toBe(false)
    expect(temQualidade(painel(base({ format: 'wav' })))).toBe(false)
  })

  it('"Mesmo do original" segue o formato do arquivo', () => {
    expect(temQualidade(painel(base(), 'voz.mp3'))).toBe(true)
    expect(temQualidade(painel(base(), 'voz.flac'))).toBe(false)
  })
})

// ---------------------------------------------------------------- a tela --

function montarTela(): ReturnType<typeof mount> {
  const job: AudioJob = {
    id: 'a1',
    backendJobId: null,
    file: { path: 'C:\\audio\\voz.mp3', name: 'voz.mp3', kind: 'Áudio' } as AudioJob['file'],
    contentType: 'speech',
    profile: 'fast',
    device: 'auto',
    status: 'configuring',
    progress: 0,
    stage: null,
    createdAt: 0
  }
  audioQueue.jobs.push(job)
  audioQueue.activeId = 'a1'
  return mount(AudioView, { global: { plugins: [i18n] }, attachTo: document.body })
}

async function processar(w: ReturnType<typeof mount>): Promise<void> {
  const botao = w.findAll('button').find((b) => b.text() === i18n.global.t('imageEditor.process'))
  await botao!.trigger('click')
  await flushPromises()
}

describe('AudioView', () => {
  it('manda o destino junto com o job', async () => {
    api.createLocalJob.mockResolvedValueOnce('j1')
    const w = montarTela()
    await processar(w)
    expect(api.createLocalJob.mock.calls[0][0].output_target).toEqual({
      format: 'keep',
      profile: 'balanced',
      directory: null,
      filename: null,
      conflict: 'rename'
    })
    w.unmount()
  })

  it('no conflito pergunta, e "Manter os dois" pede de novo com renomear', async () => {
    api.createLocalJob.mockRejectedValueOnce(new Error('CONFLICT:C:\\audio\\voz.mp3'))
    api.createLocalJob.mockResolvedValueOnce('j2')
    const w = montarTela()
    await processar(w)

    const manter = [...document.body.querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === i18n.global.t('destination.dialog.keepBoth')
    )
    expect(manter, 'a caixa de conflito deveria estar aberta').toBeTruthy()
    manter!.click()
    await flushPromises()

    expect(api.createLocalJob).toHaveBeenCalledTimes(2)
    expect(api.createLocalJob.mock.calls[1][0].output_target.conflict).toBe('rename')
    w.unmount()
  })

  it('a recusa antes do job aparece na lingua do app', async () => {
    api.createLocalJob.mockRejectedValueOnce(
      new ComponentActionError('Não há espaço em disco para o resultado.', 'insufficient_disk')
    )
    setLocale('en')
    const w = montarTela()
    await processar(w)
    expect(audioQueue.jobs[0].error).toBe('Not enough disk space for the result.')
    w.unmount()
  })
})

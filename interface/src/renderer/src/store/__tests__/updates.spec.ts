import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

const ponte = vi.hoisted(() => ({
  ouvinte: null as null | ((s: unknown) => void),
  getUpdateState: vi.fn(() =>
    Promise.resolve({ phase: 'idle', version: null, percent: null, notes: null })
  ),
  checkForUpdates: vi.fn(),
  installUpdate: vi.fn(() => Promise.resolve(true)),
  setAutoCheckUpdates: vi.fn(() => Promise.resolve()),
  ativos: vi.fn(() => Promise.resolve(0))
}))

vi.mock('../../services/native', () => ({
  hasNativeApi: true,
  api: {
    getUpdateState: ponte.getUpdateState,
    checkForUpdates: ponte.checkForUpdates,
    installUpdate: ponte.installUpdate,
    setAutoCheckUpdates: ponte.setAutoCheckUpdates,
    onUpdateState: (cb: (s: unknown) => void) => {
      ponte.ouvinte = cb
      return () => undefined
    }
  }
}))
vi.mock('../../services/api', () => ({ countActiveJobs: ponte.ativos }))

import { dismissToast, initUpdates, requestRestart, updatesState } from '../updates'
import { settingsState } from '../settings'

function estado(phase: string, version: string | null = null): void {
  ponte.ouvinte?.({ phase, version, percent: null, notes: null })
}

describe('store/updates', () => {
  beforeAll(async () => {
    localStorage.clear()
    await initUpdates()
  })

  beforeEach(() => {
    ponte.installUpdate.mockClear()
    ponte.ativos.mockReset()
    updatesState.confirmActiveJobs = null
    updatesState.installing = false
  })

  it('informa ao processo principal a preferencia de procurar, e cada mudanca dela', async () => {
    expect(ponte.setAutoCheckUpdates).toHaveBeenLastCalledWith(true)
    settingsState.autoCheckUpdates = false
    await nextTick()
    expect(ponte.setAutoCheckUpdates).toHaveBeenLastCalledWith(false)
    settingsState.autoCheckUpdates = true
    await nextTick()
  })

  it('mostra o aviso uma vez por versao', () => {
    estado('downloading', '9.0.0')
    expect(updatesState.toastVisible).toBe(false)
    estado('ready', '9.0.0')
    expect(updatesState.toastVisible).toBe(true)
    dismissToast()

    // A mesma versao de novo (outra abertura do app, por exemplo): sem aviso.
    estado('idle')
    estado('ready', '9.0.0')
    expect(updatesState.toastVisible).toBe(false)

    estado('idle')
    estado('ready', '9.0.1')
    expect(updatesState.toastVisible).toBe(true)
    dismissToast()
  })

  it('com processamento em andamento, pede confirmacao em vez de reiniciar', async () => {
    ponte.ativos.mockResolvedValue(2)
    await expect(requestRestart()).resolves.toBe('confirm')
    expect(updatesState.confirmActiveJobs).toBe(2)
    expect(ponte.installUpdate).not.toHaveBeenCalled()
  })

  it('sem nada processando, reinicia direto', async () => {
    ponte.ativos.mockResolvedValue(0)
    await expect(requestRestart()).resolves.toBe('restarting')
    expect(ponte.installUpdate).toHaveBeenCalledTimes(1)
  })

  it('backend fora do ar conta como nada processando', async () => {
    ponte.ativos.mockRejectedValue(new Error('fora'))
    await expect(requestRestart()).resolves.toBe('restarting')
    expect(ponte.installUpdate).toHaveBeenCalledTimes(1)
  })
})

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const getLicenseStatus = vi.fn()

vi.mock('../../services/api', () => {
  class BackendUnreachableError extends Error {
    constructor(cause?: unknown) {
      super('O serviço local ainda não respondeu.', { cause })
      this.name = 'BackendUnreachableError'
    }
  }
  return {
    BackendUnreachableError,
    getLicenseStatus: () => getLicenseStatus(),
    activateLicenseKey: vi.fn(),
    releaseLicense: vi.fn()
  }
})

import { BackendUnreachableError } from '../../services/api'
import { initLicense, licenseState } from '../license'

const ok = {
  state: 'active',
  installations_used: 1,
  installations_limit: 3,
  offline_days_remaining: null
}

beforeEach(() => {
  vi.useFakeTimers()
  getLicenseStatus.mockReset()
  Object.assign(licenseState, {
    status: 'checking',
    installationsUsed: 0,
    installationsLimit: 0,
    offlineDaysRemaining: null,
    error: null,
    everUsable: false
  })
})

afterEach(() => vi.useRealTimers())

describe('initLicense', () => {
  it('espera o backend subir em vez de mostrar erro na primeira falha', async () => {
    // O executavel empacotado importa torch antes de escutar. Sem espera, TODA
    // abertura fria terminava na tela "verifique sua conexao de internet" --
    // para um servico em 127.0.0.1 que apenas ainda nao subiu.
    getLicenseStatus
      .mockRejectedValueOnce(new BackendUnreachableError())
      .mockRejectedValueOnce(new BackendUnreachableError())
      .mockResolvedValueOnce(ok)

    const p = initLicense()
    await vi.advanceTimersByTimeAsync(3_000)
    await p

    expect(licenseState.status).toBe('active')
    expect(licenseState.error).toBeNull()
    expect(getLicenseStatus).toHaveBeenCalledTimes(3)
  })

  it('nao insiste quando o backend RESPONDEU um erro', async () => {
    // Qualquer resposta HTTP significa que ele subiu. Repetir aqui esconderia
    // uma falha real atras de uma tela de carregamento de 90 segundos.
    getLicenseStatus.mockRejectedValue(new Error('Erro 500'))

    const p = initLicense()
    await vi.advanceTimersByTimeAsync(5_000)
    await p

    expect(licenseState.status).toBe('error')
    expect(licenseState.error).toBe('Erro 500')
    expect(getLicenseStatus).toHaveBeenCalledTimes(1)
  })

  it('desiste depois do limite e mostra o erro', async () => {
    getLicenseStatus.mockRejectedValue(new BackendUnreachableError())

    const p = initLicense()
    await vi.advanceTimersByTimeAsync(120_000)
    await p

    expect(licenseState.status).toBe('error')
    expect(licenseState.error).toContain('ainda não respondeu')
  })
})

import { reactive } from 'vue'
import { api, hasNativeApi } from '../api'

export const apiStatus = reactive<{ checking: boolean; ready: boolean; error: string | null }>({
  checking: false,
  ready: false,
  error: null
})

export async function checkApiStatus(): Promise<void> {
  if (!hasNativeApi) {
    apiStatus.checking = false
    apiStatus.ready = false
    apiStatus.error = 'Disponível apenas no aplicativo desktop.'
    return
  }
  apiStatus.checking = true
  apiStatus.error = null
  try {
    const result = await api.ensureApi()
    apiStatus.ready = result.ready
    apiStatus.error = result.ready ? null : (result.error ?? 'Não foi possível conectar ao servidor da API.')
  } catch (error) {
    apiStatus.ready = false
    apiStatus.error = error instanceof Error ? error.message : 'Falha ao verificar a API.'
  } finally {
    apiStatus.checking = false
  }
}

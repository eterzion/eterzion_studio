import { reactive } from 'vue'
import { i18n } from '../i18n'
import { api, hasNativeApi } from '../services/native'

export const apiStatus = reactive<{ checking: boolean; ready: boolean; error: string | null }>({
  checking: false,
  ready: false,
  error: null
})

export async function checkApiStatus(): Promise<void> {
  if (!hasNativeApi) {
    apiStatus.checking = false
    apiStatus.ready = false
    apiStatus.error = i18n.global.t('app.desktopOnly')
    return
  }
  apiStatus.checking = true
  apiStatus.error = null
  try {
    const result = await api.ensureApi()
    apiStatus.ready = result.ready
    apiStatus.error = result.ready ? null : (result.error ?? i18n.global.t('app.apiUnreachable'))
  } catch (error) {
    apiStatus.ready = false
    apiStatus.error = error instanceof Error ? error.message : i18n.global.t('app.apiCheckFailed')
  } finally {
    apiStatus.checking = false
  }
}

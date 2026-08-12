import { ElectronAPI } from '@electron-toolkit/preload'
import type { AstrosApi } from './index'

declare global {
  interface Window {
    electron: ElectronAPI
    api: AstrosApi
  }
}

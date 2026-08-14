import { contextBridge, ipcRenderer, webUtils } from 'electron'
import { join, basename, extname } from 'node:path'
import { pathToFileURL } from 'node:url'
import { electronAPI } from '@electron-toolkit/preload'

// Must match MEDIA_SCHEME in src/main/index.ts.
const MEDIA_SCHEME = 'astros-media'

/** Which media a screen can open. Mirrors MediaKind in
 *  src/main/ipc/dialog.ipc.ts — preload cannot import from main. */
export type MediaKind = 'image' | 'video' | 'audio'

export interface DescribedFile {
  path: string
  name: string
  ext: string
  kind: 'Imagem' | 'Vídeo' | 'Áudio' | null
  size: number
}

export interface PickResult {
  canceled: boolean
  files: DescribedFile[]
  rejected: string[]
}

export interface ApiReadyResult {
  ready: boolean
  baseUrl: string
  startedByApp: boolean
  error?: string
}

// Custom APIs for renderer
const api = {
  ensureApi: (): Promise<ApiReadyResult> => ipcRenderer.invoke('api:ensure'),
  // `kinds` narrows the dialog to what the calling screen can actually open;
  // omitting it keeps the previous behaviour (all supported media).
  selectFiles: (kinds?: MediaKind[]): Promise<PickResult> =>
    ipcRenderer.invoke('dialog:openFiles', kinds),
  selectFolder: (kinds?: MediaKind[]): Promise<PickResult> =>
    ipcRenderer.invoke('dialog:openFolder', kinds),
  selectOutputFolder: (defaultPath?: string): Promise<string | null> =>
    ipcRenderer.invoke('dialog:selectOutputFolder', defaultPath),
  statPath: (path: string): Promise<DescribedFile | null> =>
    ipcRenderer.invoke('fs:statPath', path),
  showItemInFolder: (path: string): Promise<void> =>
    ipcRenderer.invoke('shell:showItemInFolder', path),
  openPath: (path: string): Promise<string> => ipcRenderer.invoke('shell:openPath', path),
  getAppPaths: (): Promise<{ documents: string; repoRoot: string; apiBaseUrl: string }> =>
    ipcRenderer.invoke('app:paths'),
  getPathForFile: (file: File): string => webUtils.getPathForFile(file),
  // "astros-media://local/C:/Users/..." — the "local" host is mandatory because the
  // scheme is registered as standard (see MEDIA_SCHEME comment in src/main/index.ts);
  // Chromium rejects standard-scheme URLs with an empty host. Node's pathToFileURL
  // supplies the correct percent-encoding of the path.
  toFileUrl: (path: string): string =>
    `${MEDIA_SCHEME}://local/${pathToFileURL(path).href.slice('file:///'.length)}`,
  joinPath: (...parts: string[]): string => join(...parts),
  baseName: (path: string, suffix?: string): string => basename(path, suffix),
  extName: (path: string): string => extname(path),
  saveTempImage: (buffer: ArrayBuffer, ext: string): Promise<string> =>
    ipcRenderer.invoke('paste:saveImage', buffer, ext),
  getAppVersion: (): Promise<string> => ipcRenderer.invoke('app:version'),
  openDevTools: (): Promise<void> => ipcRenderer.invoke('debug:openDevTools')
}

export type AstrosApi = typeof api

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}

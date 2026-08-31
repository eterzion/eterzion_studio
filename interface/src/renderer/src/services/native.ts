/** Which media a screen can open. Mirrors MediaKind in preload/index.ts. */
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

/** True when running inside Electron with the preload bridge available.
 *  False when previewed in a plain browser tab (e.g. during UI development). */
export const hasNativeApi = typeof window !== 'undefined' && !!window.api

/** Electron-side bridge: native dialogs, local filesystem, and the eterzion_upscale_api
 *  FastAPI server lifecycle. For talking to the API itself (models, jobs), see services/api.ts. */
export const api = {
  ensureApi: (): Promise<ApiReadyResult> => window.api.ensureApi(),
  selectFiles: (kinds?: MediaKind[]): Promise<PickResult> => window.api.selectFiles(kinds),
  selectFolder: (kinds?: MediaKind[]): Promise<PickResult> => window.api.selectFolder(kinds),
  selectOutputFolder: (defaultPath?: string): Promise<string | null> =>
    window.api.selectOutputFolder(defaultPath),
  statPath: (path: string): Promise<DescribedFile | null> => window.api.statPath(path),
  showItemInFolder: (path: string): Promise<void> => window.api.showItemInFolder(path),
  openPath: (path: string): Promise<string> => window.api.openPath(path),
  getAppPaths: (): Promise<{ documents: string; repoRoot: string; apiBaseUrl: string }> =>
    window.api.getAppPaths(),
  getPathForFile: (file: File): string => window.api.getPathForFile(file),
  toFileUrl: (path: string): string => window.api.toFileUrl(path),
  joinPath: (...parts: string[]): string => window.api.joinPath(...parts),
  baseName: (path: string, suffix?: string): string => window.api.baseName(path, suffix),
  extName: (path: string): string => window.api.extName(path),
  saveTempImage: (buffer: ArrayBuffer, ext: string): Promise<string> =>
    window.api.saveTempImage(buffer, ext),
  getAppVersion: (): Promise<string> => window.api.getAppVersion(),
  openDevTools: (): Promise<void> => window.api.openDevTools()
}

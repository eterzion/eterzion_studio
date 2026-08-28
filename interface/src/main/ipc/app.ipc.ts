import { app, shell, ipcMain, BrowserWindow } from 'electron'
import { ensureApiRunning, API_BASE_URL } from '../apiProcess'

/** Registers the remaining 6 IPC channels (API lifecycle, shell, app info) —
 *  call once per BrowserWindow. */
export function registerAppIpc(win: BrowserWindow, repoRoot: string): void {
  ipcMain.handle('api:ensure', async () =>
    ensureApiRunning(repoRoot, process.resourcesPath, app.getPath('userData'))
  )

  ipcMain.handle('shell:showItemInFolder', async (_event, path: string) => {
    shell.showItemInFolder(path)
  })

  ipcMain.handle('shell:openPath', async (_event, path: string) => shell.openPath(path))

  ipcMain.handle('app:paths', async () => ({
    documents: app.getPath('documents'),
    repoRoot,
    apiBaseUrl: API_BASE_URL
  }))

  ipcMain.handle('app:version', async () => app.getVersion())

  ipcMain.handle('debug:openDevTools', async () => {
    win.webContents.openDevTools({ mode: 'right' })
  })
}

import { app, shell, ipcMain, BrowserWindow } from 'electron'
import { dirname } from 'node:path'
import { ensureApiRunning, API_BASE_URL } from '../apiProcess'
import { gravarEstado, registrarPedidoDoInstalador } from '../installerOptions'

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

  // So' o app empacotado segue o pedido do instalador. Em desenvolvimento o
  // `userData` e' o mesmo do app instalado; ler ou gravar este estado daqui
  // disparia (ou encerraria) o download da versao instalada.
  ipcMain.handle('modelos-iniciais:estado', async () =>
    app.isPackaged
      ? registrarPedidoDoInstalador(dirname(process.execPath), app.getPath('userData'))
      : null
  )
  ipcMain.handle('modelos-iniciais:concluir', async () => {
    if (app.isPackaged) gravarEstado(app.getPath('userData'), 'concluido')
  })

  ipcMain.handle('debug:openDevTools', async () => {
    win.webContents.openDevTools({ mode: 'right' })
  })
}

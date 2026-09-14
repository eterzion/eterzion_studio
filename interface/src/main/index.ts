import { app, BrowserWindow, shell } from 'electron'
import { readdirSync } from 'fs'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { resolveRepoRoot, stopOwnedApiProcess } from './apiProcess'
import { registerMediaProtocolHandler } from './protocols/mediaProtocol'
import { createWindow } from './windows/mainWindow'
import { registerDialogIpc } from './ipc/dialog.ipc'
import { registerAppIpc } from './ipc/app.ipc'
import { initializeUpdater, stopUpdater } from './updater'
import { APP_USER_MODEL_ID, reconcileShortcuts, shortcutDirs } from './windows/appUserModelId'

const repoRoot = resolveRepoRoot()

/** Traz para o id atual os atalhos que o instalador deixou com o antigo.
 *  So no Windows empacotado: em desenvolvimento o executavel e' o do Electron, e
 *  nenhum atalho aponta para ele. Adiado para nao atrasar a janela; uma falha
 *  aqui so' registra, porque o app funciona -- o que se perde e' o agrupamento. */
function alinharAtalhosAoAppUserModelId(): void {
  if (process.platform !== 'win32' || !app.isPackaged) return
  setImmediate(() => {
    const result = reconcileShortcuts(
      shortcutDirs(app.getPath('appData'), app.getPath('desktop')),
      process.execPath,
      APP_USER_MODEL_ID,
      {
        listDir: (dir) => readdirSync(dir),
        readShortcutLink: (path) => shell.readShortcutLink(path),
        writeShortcutLink: (path, target, id) => {
          if (!shell.writeShortcutLink(path, 'update', { target, appUserModelId: id })) {
            throw new Error('writeShortcutLink devolveu false')
          }
        }
      }
    )
    for (const path of result.atualizados) console.info('[aumid] atalho alinhado', path)
    for (const f of result.falhas) console.warn('[aumid] atalho nao alinhado', f.path, f.erro)
  })
}

function initWindow(): void {
  const win = createWindow()
  registerDialogIpc(win)
  registerAppIpc(win, repoRoot)
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Precisa bater com o appId do electron-builder -- ver appUserModelId.ts,
  // onde o valor mora e onde o teste confere os dois lados.
  electronApp.setAppUserModelId(APP_USER_MODEL_ID)
  alinharAtalhosAoAppUserModelId()

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  registerMediaProtocolHandler()

  initWindow()

  initializeUpdater()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) initWindow()
  })
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  stopUpdater()
  stopOwnedApiProcess()
})

import { app, shell, BrowserWindow, ipcMain, dialog, protocol } from 'electron'
import { join, basename, extname } from 'path'
import { readdirSync, statSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { randomUUID } from 'node:crypto'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { resolveRepoRoot, ensureApiRunning, stopOwnedApiProcess, API_BASE_URL } from './apiProcess'

const repoRoot = resolveRepoRoot()

// Local media (thumbnails, before/after preview) is served through this custom
// scheme instead of `file://` because in dev the renderer is loaded over
// `http://localhost` (Vite dev server), and Chromium blocks `file://` subresource
// loads from an `http:` page regardless of CSP. A registered "standard" scheme
// works the same from both the dev server and the packaged `file://` build.
const MEDIA_SCHEME = 'astros-media'

protocol.registerSchemesAsPrivileged([
  {
    scheme: MEDIA_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true
    }
  }
])

const IMAGE_EXT = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff']
const VIDEO_EXT = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
const AUDIO_EXT = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']

const MIME_TYPES: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.bmp': 'image/bmp',
  '.tif': 'image/tiff',
  '.tiff': 'image/tiff',
  '.gif': 'image/gif'
}

function kindForExt(ext: string): 'Imagem' | 'Vídeo' | 'Áudio' | null {
  const lower = ext.toLowerCase()
  if (IMAGE_EXT.includes(lower)) return 'Imagem'
  if (VIDEO_EXT.includes(lower)) return 'Vídeo'
  if (AUDIO_EXT.includes(lower)) return 'Áudio'
  return null
}

function describeFile(path: string): {
  path: string
  name: string
  ext: string
  kind: 'Imagem' | 'Vídeo' | 'Áudio' | null
  size: number
} | null {
  try {
    const stat = statSync(path)
    if (!stat.isFile()) return null
    const ext = extname(path)
    return { path, name: basename(path), ext, kind: kindForExt(ext), size: stat.size }
  } catch {
    return null
  }
}

function createWindow(): void {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
    if (is.dev) mainWindow.webContents.openDevTools({ mode: 'right' })
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  registerIpcHandlers(mainWindow)
}

function registerIpcHandlers(win: BrowserWindow): void {
  ipcMain.handle('api:ensure', async () => ensureApiRunning(repoRoot, process.resourcesPath))

  ipcMain.handle('dialog:openFiles', async () => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openFile', 'multiSelections'],
      filters: [
        {
          name: 'Mídia suportada',
          extensions: [...IMAGE_EXT, ...VIDEO_EXT, ...AUDIO_EXT].map((e) => e.slice(1))
        },
        { name: 'Todos os arquivos', extensions: ['*'] }
      ]
    })
    if (result.canceled) return { canceled: true, files: [], rejected: [] }
    const described = result.filePaths.map((p) => ({ path: p, described: describeFile(p) }))
    return {
      canceled: false,
      files: described.filter((d) => d.described !== null).map((d) => d.described!),
      rejected: described.filter((d) => d.described === null).map((d) => d.path)
    }
  })

  ipcMain.handle('dialog:openFolder', async () => {
    const result = await dialog.showOpenDialog(win, { properties: ['openDirectory'] })
    if (result.canceled) return { canceled: true, files: [], rejected: [] }
    const folder = result.filePaths[0]
    const entries = readdirSync(folder)
    const described = entries.map((entry) => {
      const path = join(folder, entry)
      return { path, described: describeFile(path) }
    })
    return {
      canceled: false,
      files: described
        .filter((d) => d.described !== null && d.described.kind !== null)
        .map((d) => d.described!),
      rejected: described
        .filter((d) => !d.described || d.described.kind === null)
        .map((d) => d.path)
    }
  })

  ipcMain.handle('dialog:selectOutputFolder', async (_event, defaultPath?: string) => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openDirectory', 'createDirectory'],
      defaultPath
    })
    if (result.canceled) return null
    return result.filePaths[0]
  })

  ipcMain.handle('fs:statPath', async (_event, path: string) => describeFile(path))

  ipcMain.handle('paste:saveImage', async (_event, buffer: ArrayBuffer, ext: string) => {
    const path = join(app.getPath('temp'), `astros-upscale-paste-${randomUUID()}${ext}`)
    await writeFile(path, Buffer.from(buffer))
    return path
  })

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

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.electron')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  protocol.handle(MEDIA_SCHEME, async (request) => {
    // request.url looks like "astros-media://local/C:/Users/.../file.png?v=169..." — built
    // by preload's toFileUrl(). The "local" host is required: schemes registered with
    // standard: true follow generic URI syntax (scheme://host/path), and Chromium rejects
    // a standard-scheme URL with an empty host ("astros-media:///C:/...") before it ever
    // reaches this handler — that was exactly the "image never loads" bug. Strip the
    // query/hash (cache-busting after re-export), rebuild a file:/// URL from the path
    // part, and serve the bytes with an explicit Content-Type (net.fetch's file://
    // handling returned responses the <img> tag silently refused to render).
    const withoutQuery = request.url.split(/[?#]/)[0]
    const prefix = `${MEDIA_SCHEME}://local/`
    const suffix = withoutQuery.startsWith(prefix)
      ? withoutQuery.slice(prefix.length)
      : withoutQuery.slice(`${MEDIA_SCHEME}://`.length).replace(/^\/+/, '')
    try {
      const filePath = fileURLToPath(`file:///${suffix}`)
      const data = await readFile(filePath)
      const contentType = MIME_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream'
      return new Response(new Uint8Array(data), { headers: { 'Content-Type': contentType } })
    } catch {
      return new Response(null, { status: 404 })
    }
  })

  createWindow()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
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
  stopOwnedApiProcess()
})

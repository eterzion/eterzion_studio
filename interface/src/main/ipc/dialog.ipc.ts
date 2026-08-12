import { app, dialog, ipcMain, BrowserWindow } from 'electron'
import { join, basename, extname } from 'path'
import { readdirSync, statSync } from 'node:fs'
import { writeFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'

const IMAGE_EXT = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff']
const VIDEO_EXT = ['.mp4', '.mkv', '.mov', '.avi', '.webm']
const AUDIO_EXT = ['.wav', '.mp3', '.flac', '.ogg', '.m4a']

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

/** Registers the 5 dialog/filesystem IPC channels — call once per BrowserWindow. */
export function registerDialogIpc(win: BrowserWindow): void {
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
}

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

/** Which media the calling screen can actually work with. Omitted (or empty)
 *  means all of it — the Exportar screen genuinely accepts all three, and that
 *  is also the behaviour every caller had before this parameter existed. */
export type MediaKind = 'image' | 'video' | 'audio'

const EXT_BY_KIND: Record<MediaKind, string[]> = {
  image: IMAGE_EXT,
  video: VIDEO_EXT,
  audio: AUDIO_EXT
}

const KIND_LABEL: Record<MediaKind, string> = {
  image: 'Imagens',
  video: 'Vídeos',
  audio: 'Áudio'
}

function allowedExtensions(kinds?: MediaKind[]): string[] {
  const selected = kinds?.length ? kinds : (Object.keys(EXT_BY_KIND) as MediaKind[])
  return selected.flatMap((k) => EXT_BY_KIND[k])
}

function dialogFilters(kinds?: MediaKind[]): { name: string; extensions: string[] }[] {
  const selected = kinds?.length ? kinds : (Object.keys(EXT_BY_KIND) as MediaKind[])
  const label = selected.length === 1 ? KIND_LABEL[selected[0]] : 'Mídia suportada'
  return [
    { name: label, extensions: allowedExtensions(kinds).map((e) => e.slice(1)) },
    { name: 'Todos os arquivos', extensions: ['*'] }
  ]
}

/** A file the screen can open: recognised media AND of a kind it asked for.
 *  The dialog's own filter is only a default the person can switch off, so the
 *  same rule has to be enforced on the way back — otherwise picking "Todos os
 *  arquivos" would drop a video into the Áudio screen. */
function acceptedByKind(ext: string, kinds?: MediaKind[]): boolean {
  return allowedExtensions(kinds).includes(ext.toLowerCase())
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
  ipcMain.handle('dialog:openFiles', async (_event, kinds?: MediaKind[]) => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openFile', 'multiSelections'],
      filters: dialogFilters(kinds)
    })
    if (result.canceled) return { canceled: true, files: [], rejected: [] }
    const described = result.filePaths.map((p) => ({ path: p, described: describeFile(p) }))
    const accepted = (d: (typeof described)[number]): boolean =>
      d.described !== null && acceptedByKind(d.described.ext, kinds)
    return {
      canceled: false,
      files: described.filter(accepted).map((d) => d.described!),
      rejected: described.filter((d) => !accepted(d)).map((d) => d.path)
    }
  })

  ipcMain.handle('dialog:openFolder', async (_event, kinds?: MediaKind[]) => {
    const result = await dialog.showOpenDialog(win, { properties: ['openDirectory'] })
    if (result.canceled) return { canceled: true, files: [], rejected: [] }
    const folder = result.filePaths[0]
    const entries = readdirSync(folder)
    const described = entries.map((entry) => {
      const path = join(folder, entry)
      return { path, described: describeFile(path) }
    })
    const accepted = (d: (typeof described)[number]): boolean =>
      d.described !== null && d.described.kind !== null && acceptedByKind(d.described.ext, kinds)
    return {
      canceled: false,
      files: described.filter(accepted).map((d) => d.described!),
      rejected: described.filter((d) => !accepted(d)).map((d) => d.path)
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

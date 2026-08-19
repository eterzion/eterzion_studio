import { protocol } from 'electron'
import { extname } from 'path'
import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { Readable } from 'node:stream'
import { fileURLToPath } from 'node:url'

// Local media (thumbnails, before/after preview) is served through this custom
// scheme instead of `file://` because in dev the renderer is loaded over
// `http://localhost` (Vite dev server), and Chromium blocks `file://` subresource
// loads from an `http:` page regardless of CSP. A registered "standard" scheme
// works the same from both the dev server and the packaged `file://` build.
export const MEDIA_SCHEME = 'astros-media'

// MUST run before app.whenReady() resolves — registerSchemesAsPrivileged() only
// has an effect if called before the app is ready, so this executes as a module
// load side-effect (import order in index.ts keeps this ahead of app.whenReady()).
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

const MIME_TYPES: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.bmp': 'image/bmp',
  '.tif': 'image/tiff',
  '.tiff': 'image/tiff',
  '.gif': 'image/gif',
  // Video/audio preview. Without a real media MIME type the <video>/<audio>
  // element gets application/octet-stream and refuses to decode it, which is
  // what left the Vídeo and Áudio screens showing a 0:00 player.
  '.mp4': 'video/mp4',
  '.m4v': 'video/mp4',
  '.mov': 'video/quicktime',
  '.mkv': 'video/x-matroska',
  '.webm': 'video/webm',
  '.avi': 'video/x-msvideo',
  '.mp3': 'audio/mpeg',
  '.m4a': 'audio/mp4',
  '.aac': 'audio/aac',
  '.ogg': 'audio/ogg',
  '.opus': 'audio/ogg',
  '.flac': 'audio/flac',
  '.wav': 'audio/wav'
}

/** Registers the `astros-media://` request handler — call once inside
 *  app.whenReady(), matching where this ran before the main-process split. */
export function registerMediaProtocolHandler(): void {
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
      const size = (await stat(filePath)).size
      const contentType = MIME_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream'

      // Media is streamed, and range-served when asked for. An image could be
      // answered with the whole buffer, but <video>/<audio> cannot: Chromium
      // seeks by asking for byte ranges, and a handler that only ever answers
      // 200 with the full body makes the timeline unseekable and pulls an
      // entire multi-GB file into memory to show a preview.
      const range = /^bytes=(\d*)-(\d*)$/.exec(request.headers.get('Range') ?? '')
      if (range && size > 0) {
        const start = range[1] ? Number(range[1]) : 0
        const end = range[2] ? Math.min(Number(range[2]), size - 1) : size - 1
        if (start >= size || start > end) {
          return new Response(null, {
            status: 416,
            headers: { 'Content-Range': `bytes */${size}` }
          })
        }
        return new Response(
          Readable.toWeb(createReadStream(filePath, { start, end })) as ReadableStream,
          {
            status: 206,
            headers: {
              'Content-Type': contentType,
              'Content-Length': String(end - start + 1),
              'Content-Range': `bytes ${start}-${end}/${size}`,
              'Accept-Ranges': 'bytes',
              // WebGL refuses a cross-origin texture, and this scheme IS a
              // different origin from the renderer. Without this header the
              // video decodes fine but texImage2D throws, which killed the
              // draw loop and left a black canvas over a working player.
              'Access-Control-Allow-Origin': '*'
            }
          }
        )
      }

      return new Response(Readable.toWeb(createReadStream(filePath)) as ReadableStream, {
        headers: {
          'Content-Type': contentType,
          'Access-Control-Allow-Origin': '*',
          'Content-Length': String(size),
          'Accept-Ranges': 'bytes'
        }
      })
    } catch {
      return new Response(null, { status: 404 })
    }
  })
}

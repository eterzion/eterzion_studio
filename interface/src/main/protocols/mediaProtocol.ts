import { protocol } from 'electron'
import { extname } from 'path'
import { readFile } from 'node:fs/promises'
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
  '.gif': 'image/gif'
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
      const data = await readFile(filePath)
      const contentType = MIME_TYPES[extname(filePath).toLowerCase()] ?? 'application/octet-stream'
      return new Response(new Uint8Array(data), { headers: { 'Content-Type': contentType } })
    } catch {
      return new Response(null, { status: 404 })
    }
  })
}

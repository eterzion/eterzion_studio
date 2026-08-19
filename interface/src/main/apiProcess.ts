import { spawn, ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

// 8051 is the packaged default; development uses 8050, set by
// electron.vite.config.ts and passed to the Python process below as
// ASTROS_PORT. They differ so a dev run and a packaged build can be open at the
// same time without one refusing to start.
export const API_PORT = process.env.ASTROS_API_PORT || '8051'
export const API_BASE_URL = `http://127.0.0.1:${API_PORT}`

/** Locates the bundled FFmpeg binary's directory (electron-builder extraResources,
 *  see electron-builder.yml win/linux `extraResources: ... to: ffmpeg`), if one was
 *  packaged for this platform. Returns null in dev or on platforms without a
 *  bundled build (currently macOS — see docs/models/MODEL_LICENSES.md §5) so the
 *  Python backend falls back to a PATH-installed ffmpeg. */
export function resolveBundledFfmpegDir(resourcesPath: string): string | null {
  const binaryName = process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg'
  const dir = join(resourcesPath, 'ffmpeg')
  return existsSync(join(dir, binaryName)) ? dir : null
}

/** Locates the astros_upscale repo root — the directory that has both an `api/`
 *  and an `interface/` subfolder, per the api/+interface/ repository layout — from
 *  the compiled main process location (out/main) or, in dev, from process.cwd().
 *  This folder is `interface/` itself now (there's no astros_upscale_app/ nesting
 *  level anymore), so candidate depths are one shallower than before the
 *  api/+interface/ reorganisation. `pyproject.toml` used to be the marker, but it
 *  now lives at api/pyproject.toml, not at the repo root, so it can't be used here
 *  anymore — see specs/002-api-interface-split/research.md Decisão 7. */
export function resolveRepoRoot(): string {
  const candidates = [resolve(__dirname, '../../..'), resolve(process.cwd(), '..'), process.cwd()]
  for (const candidate of candidates) {
    if (existsSync(join(candidate, 'api')) && existsSync(join(candidate, 'interface'))) {
      return candidate
    }
  }
  return candidates[0]
}

export function resolvePythonExecutable(repoRoot: string): string {
  const winVenv = join(repoRoot, '.venv', 'Scripts', 'python.exe')
  const posixVenv = join(repoRoot, '.venv', 'bin', 'python')
  if (process.platform === 'win32' && existsSync(winVenv)) return winVenv
  if (process.platform !== 'win32' && existsSync(posixVenv)) return posixVenv
  return process.platform === 'win32' ? 'python' : 'python3'
}

let ownedProcess: ChildProcess | null = null

async function pingHealth(timeoutMs: number): Promise<boolean> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

export interface ApiReadyResult {
  ready: boolean
  baseUrl: string
  startedByApp: boolean
  error?: string
}

/** Ensures the astros_upscale_api FastAPI server is reachable at API_BASE_URL — reuses
 *  it if the user already started it manually (e.g. `python run.py` in a terminal),
 *  otherwise spawns it from the repo's api/astros_upscale_api/ folder using the shared .venv.
 *  `resourcesPath` (Electron's `process.resourcesPath`) is used to locate a bundled
 *  FFmpeg, if any, for this platform. */
export async function ensureApiRunning(
  repoRoot: string,
  resourcesPath: string
): Promise<ApiReadyResult> {
  if (await pingHealth(800)) {
    return { ready: true, baseUrl: API_BASE_URL, startedByApp: false }
  }

  const apiDir = join(repoRoot, 'api', 'astros_upscale_api')
  const runScript = join(apiDir, 'run.py')
  if (!existsSync(runScript)) {
    return {
      ready: false,
      baseUrl: API_BASE_URL,
      startedByApp: false,
      error: `Servidor da API não encontrado em ${runScript}.`
    }
  }

  const python = resolvePythonExecutable(repoRoot)
  const bundledFfmpegDir = resolveBundledFfmpegDir(resourcesPath)
  // ASTROS_PORT is the API's own setting name (app/config.py, env_prefix
  // 'ASTROS_'). Passing it explicitly rather than relying on inheritance means
  // the child binds the port this process is already pointing at.
  const env = {
    ...process.env,
    ASTROS_PORT: API_PORT,
    ...(bundledFfmpegDir ? { ASTROS_FFMPEG_DIR: bundledFfmpegDir } : {})
  }
  const child = spawn(python, [runScript], { cwd: apiDir, env })
  ownedProcess = child

  let stderrTail = ''
  child.stderr?.on('data', (chunk: Buffer) => {
    stderrTail = (stderrTail + chunk.toString()).slice(-2000)
  })

  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      return {
        ready: false,
        baseUrl: API_BASE_URL,
        startedByApp: true,
        error: `O servidor da API encerrou inesperadamente (código ${child.exitCode}).\n${stderrTail}`
      }
    }
    if (await pingHealth(500)) {
      return { ready: true, baseUrl: API_BASE_URL, startedByApp: true }
    }
    await sleep(400)
  }

  return {
    ready: false,
    baseUrl: API_BASE_URL,
    startedByApp: true,
    error: 'Tempo esgotado esperando o servidor da API iniciar.'
  }
}

export function stopOwnedApiProcess(): void {
  if (ownedProcess && ownedProcess.exitCode === null) {
    ownedProcess.kill()
  }
  ownedProcess = null
}

import { spawn, ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

export const API_BASE_URL = 'http://127.0.0.1:8765'

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

/** Locates the astros_upscale repo root (the folder with pyproject.toml) from the
 *  compiled main process location (out/main) or, in dev, from process.cwd(). */
export function resolveRepoRoot(): string {
  const candidates = [
    resolve(__dirname, '../../../..'),
    resolve(process.cwd(), '../..'),
    resolve(process.cwd(), '..'),
    process.cwd()
  ]
  for (const candidate of candidates) {
    if (existsSync(join(candidate, 'pyproject.toml'))) return candidate
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
 *  otherwise spawns it from the repo's astros_upscale_api/ folder using the shared .venv.
 *  `resourcesPath` (Electron's `process.resourcesPath`) is used to locate a bundled
 *  FFmpeg, if any, for this platform. */
export async function ensureApiRunning(
  repoRoot: string,
  resourcesPath: string
): Promise<ApiReadyResult> {
  if (await pingHealth(800)) {
    return { ready: true, baseUrl: API_BASE_URL, startedByApp: false }
  }

  const apiDir = join(repoRoot, 'interface', 'astros_upscale_api')
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
  const env = bundledFfmpegDir
    ? { ...process.env, ASTROS_FFMPEG_DIR: bundledFfmpegDir }
    : process.env
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

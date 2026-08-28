import { spawn, ChildProcess } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

// A porta vem por variável, e não fixada: o app empacotado e uma execução de
// desenvolvimento precisam poder ficar abertos ao mesmo tempo sem um recusar
// iniciar. 8051 é o padrão do empacotado; o desenvolvimento usa 8050, definido
// em electron.vite.config.ts e repassado ao processo Python como ASTROS_PORT.
export const API_PORT = process.env.ASTROS_API_PORT || '8051'
export const API_BASE_URL = `http://127.0.0.1:${API_PORT}`

// Fixados no runtime do app empacotado: a URL do licenciamento e a chave
// pública que verifica as respostas dele. Deixá-los como variável de ambiente
// permitiria apontar o app para outro servidor de licença.
export const LICENSING_SERVICE_URL = 'https://license.eterzion.com'
export const LICENSING_SERVICE_PUBLIC_KEY_B64 =
  '2zo5YW9vKdQdBPNCELH/+ukuMlJkZhObsY6N8Qu4wpA='

/** Locates the FFmpeg binary's directory: the packaged one first (electron-builder
 *  extraResources, see electron-builder.yml win/linux `extraResources: ... to:
 *  ffmpeg`), then the one `npm run fetch:ffmpeg` leaves in the repo for
 *  development.
 *
 *  The dev fallback is not a convenience. Without it, a developer run resolved
 *  ffmpeg from PATH — a different binary from the one users get, usually a GPL
 *  build — and that gap is where three separate defects lived unnoticed: a GPL
 *  encoder default, two GPL filters absent from the LGPL build, and an ffprobe
 *  the bundle did not carry. On a machine with no system FFmpeg it was worse
 *  than a gap: every import failed with `unreadable`, because nothing answered
 *  the probe at all.
 *
 *  Still returns null on platforms without a bundled build (currently macOS —
 *  see docs/models/MODEL_LICENSES.md §5), where PATH remains the only option. */
export function resolveBundledFfmpegDir(resourcesPath: string, repoRoot?: string): string | null {
  const binaryName = process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg'
  const packaged = join(resourcesPath, 'ffmpeg')
  if (existsSync(join(packaged, binaryName))) return packaged

  if (repoRoot) {
    // Same layout fetch-ffmpeg.mjs writes: resources/ffmpeg/<platform>/.
    const platformDir = process.platform === 'win32' ? 'win32' : 'linux'
    const dev = join(repoRoot, 'interface', 'resources', 'ffmpeg', platformDir)
    if (existsSync(join(dev, binaryName))) return dev
  }
  return null
}

export function resolveBundledApiExecutable(resourcesPath: string): string | null {
  if (process.platform !== 'win32') return null
  const executable = join(resourcesPath, 'backend', 'eterzion-studio-api.exe')
  return existsSync(executable) ? executable : null
}

export function resolveBundledModelsDir(resourcesPath: string): string | null {
  const modelsDir = join(resourcesPath, 'models')
  return existsSync(modelsDir) ? modelsDir : null
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
  resourcesPath: string,
  userDataPath: string
): Promise<ApiReadyResult> {
  const bundledApi = resolveBundledApiExecutable(resourcesPath)
  if (await pingHealth(800)) {
    if (!bundledApi) {
      return { ready: true, baseUrl: API_BASE_URL, startedByApp: false }
    }
    if (ownedProcess && ownedProcess.exitCode === null) {
      return { ready: true, baseUrl: API_BASE_URL, startedByApp: true }
    }
    return {
      ready: false,
      baseUrl: API_BASE_URL,
      startedByApp: false,
      error: `A porta local ${API_PORT} já está em uso por outro processo. Feche-o e abra o aplicativo novamente.`
    }
  }

  // O segundo argumento é o fallback para a árvore do repositório: sem ele,
  // uma execução de desenvolvimento não acha o FFmpeg empacotado e cai num do
  // PATH, que a máquina pode não ter.
  const bundledFfmpegDir = resolveBundledFfmpegDir(resourcesPath, repoRoot)
  const bundledModelsDir = resolveBundledModelsDir(resourcesPath)
  const storageDir = join(userDataPath, 'storage')
  mkdirSync(join(storageDir, 'uploads'), { recursive: true })
  mkdirSync(join(storageDir, 'outputs'), { recursive: true })

  let command: string
  let args: string[]
  let cwd: string
  // ASTROS_PORT é o nome da configuração da própria API (app/config.py,
  // env_prefix 'ASTROS_'). Passá-lo explicitamente, em vez de contar com
  // herança, garante que o filho escute na porta para a qual este processo já
  // está apontando.
  // Anotado como ProcessEnv: sem o tipo, o TypeScript infere um literal com
  // apenas as chaves escritas aqui, e as atribuições condicionais abaixo
  // (modelos, FFmpeg, licenciamento) deixam de compilar.
  let env: NodeJS.ProcessEnv = { ...process.env, ASTROS_PORT: API_PORT }

  if (bundledApi) {
    command = bundledApi
    args = []
    cwd = join(resourcesPath, 'backend')
    env = {
      ...env,
      ASTROS_LICENSING_SERVICE_URL: LICENSING_SERVICE_URL,
      ASTROS_LICENSING_SERVICE_PUBLIC_KEY_B64: LICENSING_SERVICE_PUBLIC_KEY_B64,
      ASTROS_DEV_ALLOW_UNLICENSED: 'false',
      ASTROS_UPLOADS_DIR: join(storageDir, 'uploads'),
      ASTROS_OUTPUTS_DIR: join(storageDir, 'outputs')
    }
    if (bundledModelsDir) env.ASTROS_MODELS_DIR = bundledModelsDir
  } else {
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
    command = resolvePythonExecutable(repoRoot)
    args = [runScript]
    cwd = apiDir
  }

  if (bundledFfmpegDir) env.ASTROS_FFMPEG_DIR = bundledFfmpegDir

  const child = spawn(command, args, { cwd, env, windowsHide: true })

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

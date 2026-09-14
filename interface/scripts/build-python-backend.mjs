#!/usr/bin/env node
import { existsSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import process from 'node:process'

const platform = process.argv[2]
// O PyInstaller nao cruza plataformas: o backend Linux precisa ser construido
// num Linux (a CI usa um Ubuntu 22.04 -- a glibc dele e' o piso de suporte).
if (platform !== 'win32' && platform !== 'linux') {
  console.error(`Unsupported backend target: ${platform || '(missing)'}`)
  process.exit(1)
}
if (platform !== process.platform) {
  console.error(`O backend ${platform} precisa ser construido em ${platform} (este e' ${process.platform}).`)
  process.exit(1)
}

const interfaceDir = resolve(import.meta.dirname, '..')
const repoRoot = resolve(interfaceDir, '..')
const apiDir = resolve(repoRoot, 'api', 'eterzion_upscale_api')
const specPath = resolve(apiDir, 'eterzion-studio-api.spec')
const distPath = resolve(interfaceDir, 'resources', 'backend', platform)
const workPath = resolve(apiDir, 'build', 'pyinstaller')
const python = process.env.PYTHON_EXE || process.env.PYTHON || 'python'
const executableName = platform === 'win32' ? 'eterzion-studio-api.exe' : 'eterzion-studio-api'
const executable = resolve(distPath, 'eterzion-studio-api', executableName)

// Empacotar o PyTorch leva ~4,5 minutos e domina o tempo do release, mas o
// resultado só muda quando `api/**`, o `.spec` ou os requirements mudam. Com
// `REUSE_BACKEND_BUILD=1` um executável já presente é aceito como está — a CI
// liga isso e deixa a decisão para a chave do cache, que é quem sabe se as
// entradas mudaram. Fora da CI a variável fica desligada e o build é sempre do
// zero, que é o comportamento seguro para quem roda na mão.
if (process.env.REUSE_BACKEND_BUILD === '1' && existsSync(executable)) {
  console.log(`[build-python-backend] reaproveitando: ${executable}`)
  process.exit(0)
}

rmSync(distPath, { recursive: true, force: true })

const result = spawnSync(
  python,
  [
    '-m',
    'PyInstaller',
    '--clean',
    '--noconfirm',
    '--distpath',
    distPath,
    '--workpath',
    workPath,
    specPath
  ],
  { cwd: apiDir, env: process.env, stdio: 'inherit' }
)

if (result.error) {
  console.error(result.error.message)
  process.exit(1)
}
if (result.status !== 0) process.exit(result.status ?? 1)

if (!existsSync(executable)) {
  console.error(`PyInstaller completed without producing ${executable}`)
  process.exit(1)
}

console.log(`[build-python-backend] ready: ${executable}`)

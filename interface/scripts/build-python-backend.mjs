#!/usr/bin/env node
import { existsSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import process from 'node:process'

const platform = process.argv[2]
if (platform !== 'win32') {
  console.error(`Unsupported backend target: ${platform || '(missing)'}`)
  process.exit(1)
}

const interfaceDir = resolve(import.meta.dirname, '..')
const repoRoot = resolve(interfaceDir, '..')
const apiDir = resolve(repoRoot, 'api', 'astros_upscale_api')
const specPath = resolve(apiDir, 'eterzion-studio-api.spec')
const distPath = resolve(interfaceDir, 'resources', 'backend', platform)
const workPath = resolve(apiDir, 'build', 'pyinstaller')
const python = process.env.PYTHON_EXE || process.env.PYTHON || 'python'

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

const executable = resolve(distPath, 'eterzion-studio-api', 'eterzion-studio-api.exe')
if (!existsSync(executable)) {
  console.error(`PyInstaller completed without producing ${executable}`)
  process.exit(1)
}

console.log(`[build-python-backend] ready: ${executable}`)

#!/usr/bin/env node
/**
 * Downloads the LGPL "shared" FFmpeg builds published by BtbN/FFmpeg-Builds
 * (https://github.com/BtbN/FFmpeg-Builds) and extracts just the ffmpeg binary
 * plus its dynamic libraries into resources/ffmpeg/<platform>/, ready for
 * electron-builder's per-platform extraResources.
 *
 * These builds are compiled WITHOUT --enable-gpl and WITHOUT --enable-nonfree
 * (no libx264/libx265, no fdk-aac) and link every optional component
 * dynamically, satisfying the LGPL terms recorded in
 * docs/models/MODEL_LICENSES.md §5: dynamic linking, replaceable DLLs, and a
 * documented source pointer (kept below and in that doc).
 *
 * Pinned to a DATED release tag, not to "latest". Pinning the asset name and a
 * SHA256 against a moving tag does not pin anything: BtbN re-tags "latest" every
 * day, the bytes behind the same filename change, and the checksum stops
 * matching. This script then refuses — correctly — and the installer cannot be
 * built at all. That is exactly what happened on 2026-08-21, when the previous
 * pin ("latest" + a sha from an earlier day) had already gone stale.
 *
 * A dated tag is immutable, so the filename+SHA256 pair stays true. The asset
 * names under a dated tag carry the exact build id, which is why they look
 * longer than the ones "latest" serves.
 *
 * IMMUTABLE IS NOT THE SAME AS RETAINED, and that gap broke CI on 04/09/2026:
 * autobuild-2026-08-21-13-40 stopped existing and every job that fetches
 * FFmpeg started failing with HTTP 404 -- on pull requests that had nothing to
 * do with FFmpeg. BtbN keeps daily autobuilds for roughly two weeks.
 *
 * PIN ONLY TO A MONTH-END AUTOBUILD. Those are kept indefinitely: at the time
 * of writing the releases list runs 2025-10-31, 2025-11-30, 2025-12-31,
 * 2026-01-31 ... 2026-07-31, and then only the last two weeks of dailies. A
 * mid-month tag is a time bomb with a two-week fuse, however immutable it is.
 *
 * To move to a newer version: pick a MONTH-END tag from
 * https://github.com/BtbN/FFmpeg-Builds/releases, then update FFMPEG_RELEASE_TAG,
 * FFMPEG_SOURCE_VERSION, both archiveName values and both sha256 values together
 * (the digests are on each asset in the GitHub API, or in the release's
 * checksums.sha256), re-run `npm run fetch:ffmpeg` and re-verify with
 * `ffmpeg -version` per docs/models/MODEL_LICENSES.md §5.
 *
 * macOS is intentionally not covered here — BtbN does not publish macOS
 * builds and no equivalent verifiable/automatable LGPL source was found.
 * See docs/models/MODEL_LICENSES.md §5 for that pendency.
 */
import { createHash } from 'node:crypto'
import {
  existsSync,
  mkdirSync,
  rmSync,
  chmodSync,
  readdirSync,
  symlinkSync,
  copyFileSync,
  readFileSync,
  writeFileSync
} from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const RESOURCES_ROOT = join(__dirname, '..', 'resources', 'ffmpeg')
export const FFMPEG_RELEASE_TAG = 'autobuild-2026-08-31-13-27'
const RELEASE_BASE = `https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_RELEASE_TAG}`

export const FFMPEG_SOURCE_VERSION = 'n8.1.2-50-g1a748fe2cd'
export const FFMPEG_SOURCE_URL = 'https://github.com/BtbN/FFmpeg-Builds'

const TARGETS = {
  win32: {
    archiveName: 'ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-shared-8.1.zip',
    sha256: 'e9712ffbdb03ef71bbab660c75b835bfe698ef6fad0247c76d8d394a39a3db63',
    // Runtime files only: ffmpeg.exe, ffprobe.exe and their DLLs. Drops
    // ffplay.exe and the .def/.lib import-library files (link-time only, no use
    // in a packaged app that never compiles against these).
    //
    // ffprobe used to be dropped here as "not needed". It is needed:
    // astros_upscale.media.ffprobe_json() shells out to it for every duration,
    // frame-rate, resolution and audio-track question the product asks, which is
    // most of video import. Excluding it meant the packaged app fell back to a
    // PATH ffprobe that an end-user machine has no reason to have. It costs
    // ~0.5 MB and reuses the DLLs already here.
    keepFromBinDir: (name) => /\.(exe|dll)$/i.test(name) && !/^ffplay\.exe$/i.test(name),
    binarySubpath: 'ffmpeg.exe'
  },
  linux: {
    archiveName: 'ffmpeg-n8.1.2-50-g1a748fe2cd-linux64-lgpl-shared-8.1.tar.xz',
    sha256: '5634d61d98fd647acb3b2d8f08f20e7ab858c5f5341f1cea36069d8ef45c48c4',
    keepFromBinDir: (name) => name === 'ffmpeg' || name === 'ffprobe',
    binarySubpath: 'ffmpeg'
  }
}

function sha256File(path) {
  const data = readFileSync(path)
  return createHash('sha256').update(data).digest('hex')
}

async function download(url, destPath) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`GET ${url} -> HTTP ${res.status}`)
  const buffer = Buffer.from(await res.arrayBuffer())
  mkdirSync(dirname(destPath), { recursive: true })
  writeFileSync(destPath, buffer)
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: 'inherit', ...opts })
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed with exit code ${result.status}`)
  }
}

function findWindowsXzDir() {
  // bsdtar (below) shells out to an external `xz` to decompress .tar.xz — it
  // has no built-in LZMA support. Windows doesn't ship one, but Git for
  // Windows (a near-universal dev-machine prerequisite for this repo) bundles
  // it, just not on PATH by default and not at a fixed layout: depending on
  // the install, `where git` may resolve to \cmd\git.exe, \bin\git.exe or
  // \mingw64\bin\git.exe, and xz.exe itself has been found at \mingw64\bin
  // (not \usr\bin, despite most other *nix tools living there). Rather than
  // hardcode one layout, check every plausible sibling dir of every git.exe
  // `where` reports.
  const where = spawnSync('where', ['git'], { encoding: 'utf8' })
  if (where.status !== 0 || !where.stdout) return null
  const gitExePaths = where.stdout
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  for (const gitExe of gitExePaths) {
    const gitBin = dirname(gitExe)
    const gitRoot = dirname(gitBin)
    const gitRoot2 = dirname(gitRoot)
    const candidates = [
      gitBin,
      join(gitRoot, 'mingw64', 'bin'),
      join(gitRoot, 'usr', 'bin'),
      join(gitRoot2, 'mingw64', 'bin'),
      join(gitRoot2, 'usr', 'bin')
    ]
    for (const dir of candidates) {
      if (existsSync(join(dir, 'xz.exe'))) return dir
    }
  }
  return null
}

function extractArchive(archivePath, destDir) {
  mkdirSync(destDir, { recursive: true })
  // bsdtar (libarchive) transparently handles both .zip and .tar.xz, and lets
  // positional args after the archive select which members to extract by glob
  // — no --wildcards flag needed, unlike GNU tar. We only need bin/ and lib/
  // out of an archive whose bulk is a full include/ header tree (thousands of
  // small files), so restricting extraction to those two globs is what keeps
  // this fast: extracting everything made every file a target for the OS's
  // real-time antivirus scan, stretching a few-second unzip into minutes.
  //
  // On Windows, plain `tar` on PATH commonly resolves to Git's MSYS/GNU tar,
  // which misparses native "C:\..." paths as remote host specs ("C:" looks
  // like a host prefix). Force the OS-bundled bsdtar (System32\tar.exe,
  // present since Windows 10 1803) instead.
  const isWin = process.platform === 'win32'
  const cmd = isWin ? join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe') : 'tar'
  // GNU tar (used when this script runs on Linux CI) only expands glob members
  // with --wildcards; bsdtar (Windows) does it by default and doesn't have the flag.
  const wildcardFlag = isWin ? [] : ['--wildcards']

  let env = process.env
  if (isWin && archivePath.endsWith('.xz')) {
    const xzDir = findWindowsXzDir()
    if (!xzDir) {
      throw new Error(
        'Extracting .tar.xz on Windows needs an `xz` executable on PATH (bsdtar shells out to ' +
          "it) and none was found, including Git for Windows' bundled copy. Install Git for " +
          'Windows (https://git-scm.com/download/win) or 7-Zip, or add an `xz.exe` to PATH.'
      )
    }
    env = { ...process.env, PATH: `${xzDir};${process.env.PATH || ''}` }
  }

  run(cmd, ['-xf', archivePath, '-C', destDir, ...wildcardFlag, '*/bin/*', '*/lib/*'], { env })
}

function tryRmSync(path) {
  // Best-effort cleanup: on Windows, a just-downloaded/extracted large file can
  // stay transiently locked by antivirus real-time scanning. The fetch itself
  // already succeeded (outDir is populated) by the time this runs, so a leftover
  // .tmp-<platform> directory is not a failure — just re-run with --force later.
  try {
    rmSync(path, { recursive: true, force: true })
  } catch (error) {
    console.warn(
      `[fetch-ffmpeg] could not clean up ${path} (${error.message}); leaving it in place`
    )
  }
}

function findSingleTopLevelDir(dir) {
  const entries = readdirSync(dir, { withFileTypes: true }).filter((e) => e.isDirectory())
  if (entries.length !== 1) {
    throw new Error(`Expected exactly one top-level directory in ${dir}, found ${entries.length}`)
  }
  return join(dir, entries[0].name)
}

/**
 * Recria os symlinks de soname (libfoo.so.62 -> libfoo.so.62.28.102).
 *
 * O tar os extrai, mas copyDirFiltered copia apenas `entry.isFile()` e os
 * descarta em silencio. Sem eles o binario nao carrega: o rpath encontra o
 * diretorio e procura ali pelo soname exato, que nao existe como arquivo.
 * O resultado e um ffmpeg que falha so em runtime, depois de o download e a
 * verificacao de SHA terem passado.
 *
 * No Windows nao ha equivalente: DLLs sao referenciadas pelo nome completo.
 */
function createSonameLinks(dir) {
  for (const name of readdirSync(dir)) {
    const match = /^(.+\.so\.\d+)\..+$/u.exec(name)
    if (!match) continue
    const link = join(dir, match[1])
    if (existsSync(link)) continue
    symlinkSync(name, link)
  }
}

function copyDirFiltered(srcDir, destDir, keep) {
  mkdirSync(destDir, { recursive: true })
  for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue
    if (keep && !keep(entry.name)) continue
    const src = join(srcDir, entry.name)
    const dest = join(destDir, entry.name)
    copyFileSync(src, dest)
  }
}

async function fetchPlatform(platform, { force }) {
  const target = TARGETS[platform]
  if (!target)
    throw new Error(`Unknown platform "${platform}". Known: ${Object.keys(TARGETS).join(', ')}`)

  const outDir = join(RESOURCES_ROOT, platform)
  const binaryOut = join(outDir, target.binarySubpath)
  if (!force && existsSync(binaryOut)) {
    console.log(
      `[fetch-ffmpeg] ${platform}: already present at ${binaryOut} (use --force to re-fetch)`
    )
    return
  }

  const workDir = join(RESOURCES_ROOT, `.tmp-${platform}`)
  tryRmSync(workDir)
  mkdirSync(workDir, { recursive: true })

  const archivePath = join(workDir, target.archiveName)
  const url = `${RELEASE_BASE}/${target.archiveName}`
  console.log(`[fetch-ffmpeg] ${platform}: downloading ${url}`)
  await download(url, archivePath)

  const actualSha256 = sha256File(archivePath)
  if (actualSha256 !== target.sha256) {
    throw new Error(
      `[fetch-ffmpeg] ${platform}: SHA256 mismatch for ${target.archiveName}\n` +
        `  expected: ${target.sha256}\n` +
        `  actual:   ${actualSha256}\n` +
        'Refusing to use an unverified FFmpeg binary.'
    )
  }
  console.log(`[fetch-ffmpeg] ${platform}: SHA256 verified`)

  const extractDir = join(workDir, 'extracted')
  extractArchive(archivePath, extractDir)

  const topLevel = findSingleTopLevelDir(extractDir)
  const binDir = join(topLevel, 'bin')
  const libDir = join(topLevel, 'lib')

  rmSync(outDir, { recursive: true, force: true })
  copyDirFiltered(binDir, outDir, target.keepFromBinDir)
  // Windows bin/ already contains the DLLs the exe needs — nothing else to copy.
  // Linux ships the runtime .so files under lib/ instead (bin/ only has the ELF
  // binaries), e aqui elas ficam planas ao lado do executavel, mesmo layout das
  // DLLs do Windows. Only .so* files are taken — skip any .a/.la link-time
  // artifacts that might ship alongside them.
  //
  // ATENCAO: no Linux isso NAO basta para executar. O RPATH gravado no binario
  // do BtbN e literalmente "-Wl:../lib" -- a flag do linker vazou para dentro
  // do campo em vez de $ORIGIN (confirmado com readelf -d). Quem for executar
  // esses binarios precisa de LD_LIBRARY_PATH apontando para este diretorio.
  if (platform !== 'win32' && existsSync(libDir)) {
    copyDirFiltered(libDir, outDir, (name) => name.includes('.so'))
  }

  if (platform !== 'win32') {
    createSonameLinks(outDir)
    chmodSync(binaryOut, 0o755)
  }

  tryRmSync(workDir)
  console.log(`[fetch-ffmpeg] ${platform}: ready at ${outDir}`)
}

async function main() {
  const args = process.argv.slice(2)
  const force = args.includes('--force')
  const requested = args.filter((a) => !a.startsWith('--'))
  const platforms = requested.length > 0 ? requested : Object.keys(TARGETS)

  for (const platform of platforms) {
    await fetchPlatform(platform, { force })
  }
}

main().catch((error) => {
  console.error(error.message || error)
  process.exit(1)
})

import { join, win32 } from 'path'

// A identidade do app para o Windows (AppUserModelID). E' ela que decide sob
// qual icone da barra de tarefas a janela aparece, se ela agrupa com o atalho
// fixado, e em nome de quem sai a notificacao de "job concluido".
//
// **Tem que ser igual ao `appId` do electron-builder.yml**, porque o instalador
// grava esse valor nos atalhos que cria (`WinShell::SetLnkAUMI "${APP_ID}"`).
// O teste confere os dois lados, e existe porque este valor ja divergiu: ficou
// `com.astrosupscale.app` depois da renomeacao, com um comentario ao lado dizendo
// que precisava bater com o appId. A intencao estava certa e a string, errada --
// e nada acusa, porque o app abre normalmente com qualquer id.
export const APP_USER_MODEL_ID = 'com.eterzion.studio'

export interface ShortcutInfo {
  target: string
  appUserModelId?: string
}

/** O que a reconciliacao precisa do sistema. Injetado para ser testavel sem
 *  Electron: em producao vem de `shell.readShortcutLink`/`writeShortcutLink`. */
export interface ShortcutDeps {
  listDir(dir: string): string[]
  readShortcutLink(path: string): ShortcutInfo
  /** `target` vai junto porque o Electron o exige mesmo em 'update'; e' o
   *  mesmo alvo lido do atalho, entao nada alem do id muda. */
  writeShortcutLink(path: string, target: string, appUserModelId: string): void
}

export interface ReconcileResult {
  /** Todo atalho que abre este executavel, com o id lido nele. E' o que diz,
   *  no log, por que um atalho foi ou nao regravado. */
  doApp: { path: string; appUserModelId: string }[]
  atualizados: string[]
  falhas: { path: string; erro: string }[]
}

function mesmoArquivo(a: string, b: string): boolean {
  return win32.resolve(a).toLowerCase() === win32.resolve(b).toLowerCase()
}

/**
 * Regrava com `appUserModelId` os atalhos que abrem **este** executavel e ainda
 * carregam outro id.
 *
 * Por que isso e' necessario, e nao so trocar a constante: o instalador so grava
 * o id quando **cria** o atalho. Numa atualizacao ele preserva o do Menu
 * Iniciar (`keepShortcuts`), entao quem instalou com o id antigo continua com o
 * id antigo no atalho para sempre. Trocar so o codigo inverteria o defeito --
 * consertaria quem instala do zero e quebraria o agrupamento e as notificacoes
 * de quem ja tinha o app.
 *
 * Toca apenas atalhos cujo alvo e' o proprio executavel. Um atalho do usuario
 * apontando para outra coisa, na mesma pasta, fica como esta.
 */
export function reconcileShortcuts(
  dirs: string[],
  execPath: string,
  appUserModelId: string,
  deps: ShortcutDeps
): ReconcileResult {
  const result: ReconcileResult = { doApp: [], atualizados: [], falhas: [] }

  for (const dir of dirs) {
    let nomes: string[]
    try {
      nomes = deps.listDir(dir)
    } catch {
      // Pasta ausente e' o caso comum (ninguem fixou na barra de tarefas, ou
      // apagou o atalho da area de trabalho), nao uma falha.
      continue
    }

    for (const nome of nomes) {
      if (!nome.toLowerCase().endsWith('.lnk')) continue
      const path = join(dir, nome)
      try {
        const link = deps.readShortcutLink(path)
        if (!link.target || !mesmoArquivo(link.target, execPath)) continue
        result.doApp.push({ path, appUserModelId: link.appUserModelId ?? '' })
        if (link.appUserModelId === appUserModelId) continue
        deps.writeShortcutLink(path, link.target, appUserModelId)
        result.atualizados.push(path)
      } catch (error) {
        result.falhas.push({ path, erro: error instanceof Error ? error.message : String(error) })
      }
    }
  }

  return result
}

/** As pastas onde o instalador, ou o usuario, deixam atalhos para o app. */
export function shortcutDirs(appData: string, desktop: string): string[] {
  return [
    join(appData, 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
    desktop,
    // Onde o Windows guarda o que o usuario fixou na barra de tarefas. E' este
    // atalho que precisa bater com o id da janela para ela agrupar com ele.
    join(appData, 'Microsoft', 'Internet Explorer', 'Quick Launch', 'User Pinned', 'TaskBar')
  ]
}

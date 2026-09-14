import { existsSync, mkdirSync, readdirSync, renameSync, rmdirSync } from 'node:fs'
import { dirname, join } from 'node:path'

// Onde ficam os modelos baixados sob demanda.
//
// Ficavam em `userData/models`, e `userData` e' o lugar errado para eles nos
// dois sistemas:
//
// - **Windows:** `userData` e' %APPDATA%, o perfil *Roaming*. Em maquina de
//   dominio com perfil movel, tudo ali e' copiado pela rede a cada logon e
//   logoff -- centenas de MB hoje, GB com os modelos de video e voz. O lugar de
//   dado grande e refazivel e' %LOCALAPPDATA%, que nunca viaja.
// - **Linux:** `userData` e' ~/.config/eterzion-studio. O XDG reserva
//   ~/.config para configuracao; dado de aplicativo vai em $XDG_DATA_HOME
//   (~/.local/share), onde a chave de ativacao do app ja' mora.

export interface Ambiente {
  platform: NodeJS.Platform
  env: NodeJS.ProcessEnv
  homedir: string
}

/** A pasta de dados locais do app: nao sincroniza, nao e' configuracao. */
export function localDataDir({ platform, env, homedir }: Ambiente): string {
  if (platform === 'win32') {
    return join(env.LOCALAPPDATA || join(homedir, 'AppData', 'Local'), 'eterzion-studio')
  }
  // So' vale um XDG_DATA_HOME absoluto: a especificacao manda ignorar um
  // relativo, e usa-lo gravaria em algum lugar relativo ao cwd do processo.
  const xdg = env.XDG_DATA_HOME
  const base = xdg && xdg.startsWith('/') ? xdg : join(homedir, '.local', 'share')
  return join(base, 'eterzion-studio')
}

export type Migracao =
  | { dir: string; resultado: 'nada-a-mover' | 'movida' | 'ja-migrada' }
  | { dir: string; resultado: 'mantida-antiga'; erro: string }

function vazia(dir: string): boolean {
  return readdirSync(dir).length === 0
}

/**
 * Devolve a pasta de modelos a usar, trazendo a antiga para o lugar novo se
 * for preciso.
 *
 * **Move, nunca copia.** No mesmo volume o `rename` e' instantaneo, qualquer
 * que seja o tamanho. Se ele falhar -- Roaming redirecionado para outro volume,
 * ou um arquivo preso por um backend que nao fechou --, a sessao usa a pasta
 * antiga como estava e a proxima abertura tenta de novo. Copiar GB aqui
 * travaria a abertura do app, e apagar forcaria baixar tudo outra vez.
 *
 * **Nunca apaga modelo.** Se as duas pastas tiverem conteudo (o que so'
 * acontece se alguem criou a nova a mao), vence a nova e a antiga fica onde
 * esta.
 */
export function migrarPastaDeModelos(antiga: string, nova: string): Migracao {
  const temAntiga = existsSync(antiga) && !vazia(antiga)
  const temNova = existsSync(nova) && !vazia(nova)

  if (temNova || !temAntiga) {
    mkdirSync(nova, { recursive: true })
    return { dir: nova, resultado: temNova ? 'ja-migrada' : 'nada-a-mover' }
  }

  try {
    // Uma pasta nova vazia, criada por uma abertura anterior, impede o rename
    // no Windows (EPERM). Vazia, nao ha' nada nela a perder.
    if (existsSync(nova)) rmdirSync(nova)
    mkdirSync(dirname(nova), { recursive: true })
    renameSync(antiga, nova)
    return { dir: nova, resultado: 'movida' }
  } catch (error) {
    return {
      dir: antiga,
      resultado: 'mantida-antiga',
      erro: error instanceof Error ? error.message : String(error)
    }
  }
}

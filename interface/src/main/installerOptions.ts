import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

// "Baixar os modelos de IA depois de ativar", a caixa da pagina de Opcoes do
// instalador (build/installer.nsh).
//
// O instalador nao baixa nada: roda antes da ativacao, e o download pelo nosso
// servidor exige licenca ativa. Ele so' grava a escolha em
// `<pasta do app>/installer-options.json`, e o app faz o resto quando a
// licenca ficar ativa (store/modelosIniciais.ts, no renderer).
//
// O arquivo na pasta do app nao dura: a proxima atualizacao recria a pasta
// sem ele. Por isso, na primeira abertura, o pedido vira estado desta conta,
// em `userData`, que sobrevive a atualizacoes -- e e' dali que sai o "tentar
// de novo na proxima abertura" quando um download falha. Numa instalacao
// "para todos", cada conta leva o pedido para o seu `userData` ao abrir.

export type EstadoModelosIniciais = 'pendente' | 'concluido' | null

const ARQUIVO_DO_INSTALADOR = 'installer-options.json'
const ARQUIVO_DA_CONTA = 'modelos-iniciais.json'

function lerJson(caminho: string): unknown {
  try {
    return JSON.parse(readFileSync(caminho, 'utf8'))
  } catch {
    // Ausente (instalacao antiga, atualizacao, desenvolvimento) ou corrompido:
    // nos dois casos o instalador nao pediu nada que valha seguir.
    return null
  }
}

export function instaladorPediuModelos(pastaDoApp: string): boolean {
  const opcoes = lerJson(join(pastaDoApp, ARQUIVO_DO_INSTALADOR))
  return (
    typeof opcoes === 'object' &&
    opcoes !== null &&
    (opcoes as { downloadModelsAfterActivation?: unknown }).downloadModelsAfterActivation === true
  )
}

export function lerEstado(userData: string): EstadoModelosIniciais {
  const estado = (lerJson(join(userData, ARQUIVO_DA_CONTA)) as { estado?: unknown } | null)?.estado
  return estado === 'pendente' || estado === 'concluido' ? estado : null
}

export function gravarEstado(userData: string, estado: 'pendente' | 'concluido'): void {
  mkdirSync(userData, { recursive: true })
  writeFileSync(join(userData, ARQUIVO_DA_CONTA), JSON.stringify({ estado }))
}

/**
 * Traz para esta conta o pedido do instalador, uma vez so'.
 *
 * Um estado ja' gravado sempre vence. "Concluido" continua concluido mesmo que
 * o instalador peca de novo, porque quem removeu um modelo pela tela de
 * Componentes nao quer ve-lo voltar sozinho. "Pendente" continua pendente ate'
 * o download terminar, com ou sem o arquivo do instalador.
 */
export function registrarPedidoDoInstalador(
  pastaDoApp: string,
  userData: string
): EstadoModelosIniciais {
  const atual = lerEstado(userData)
  if (atual !== null) return atual
  if (!instaladorPediuModelos(pastaDoApp)) return null
  gravarEstado(userData, 'pendente')
  return 'pendente'
}

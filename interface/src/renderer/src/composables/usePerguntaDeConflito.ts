import { ref, type Ref } from 'vue'

// "Perguntar" quando o arquivo de destino ja' existe. O backend recusa com 409
// `conflict` ANTES de criar o job (app/destino.py); a tela pergunta e, com a
// resposta, pede de novo com "renomear" ou "substituir". Nada foi processado
// ate' aqui, entao cancelar nao desfaz nada.
//
// Uma pergunta aberta por vez, por tela. Na fila da Compressao, o proximo
// arquivo espera a resposta do anterior -- e' o que faz sentido para quem esta'
// respondendo.

export type RespostaDeConflito = 'rename' | 'overwrite' | null

export interface PerguntaDeConflito {
  /** O caminho que ja' existe, enquanto a pergunta esta' aberta. */
  caminho: Ref<string | null>
  /** Abre a pergunta. `null` = a pessoa cancelou. */
  perguntar: (caminho: string) => Promise<RespostaDeConflito>
  responder: (resposta: RespostaDeConflito) => void
}

export function usePerguntaDeConflito(): PerguntaDeConflito {
  const caminho = ref<string | null>(null)
  let pendente: ((resposta: RespostaDeConflito) => void) | null = null

  function responder(resposta: RespostaDeConflito): void {
    const resolver = pendente
    pendente = null
    caminho.value = null
    resolver?.(resposta)
  }

  function perguntar(existente: string): Promise<RespostaDeConflito> {
    // Uma pergunta nova fecha a anterior como cancelada: duas promessas
    // esperando a mesma caixa, uma delas nunca seria respondida.
    responder(null)
    caminho.value = existente
    return new Promise((resolve) => {
      pendente = resolve
    })
  }

  return { caminho, perguntar, responder }
}

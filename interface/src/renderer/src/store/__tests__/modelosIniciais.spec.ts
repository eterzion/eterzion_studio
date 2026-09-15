import { beforeEach, describe, expect, it } from 'vitest'
import type { ComponentSummary, InstallState } from '../../services/api'
import {
  baixarModelosIniciais,
  faltando,
  modelosIniciais,
  _reiniciarParaTeste,
  type DependenciasModelosIniciais
} from '../modelosIniciais'

// O download que o instalador pediu, contra uma API falsa que se comporta como
// a real: o POST de instalar so' dispara, e o estado muda depois, visto por
// consulta. Cada componente pode terminar instalado ou voltar a "nao
// instalado" (o download falhou).

function comp(
  id: string,
  install_state: InstallState,
  extra: Partial<ComponentSummary> = {}
): ComponentSummary {
  return {
    id,
    capability_label: id,
    size_mb: 0,
    install_state,
    update_available: false,
    available: true,
    ...extra
  }
}

function api(
  inicial: ComponentSummary[],
  opcoes: { estado?: 'pendente' | 'concluido' | null; falham?: string[] } = {}
): DependenciasModelosIniciais & { concluido: boolean; instalados: string[] } {
  const componentes = inicial.map((c) => ({ ...c }))
  const pendentes = new Set<string>()
  const r = {
    concluido: false,
    instalados: [] as string[],
    estado: async () => (opcoes.estado === undefined ? 'pendente' : opcoes.estado),
    concluir: async () => {
      r.concluido = true
    },
    listar: async () => componentes.map((c) => ({ ...c })),
    instalar: async (id: string) => {
      r.instalados.push(id)
      const c = componentes.find((x) => x.id === id)!
      c.install_state = 'installing'
      pendentes.add(id)
    },
    // Cada espera "passa o tempo": o que estava baixando termina.
    esperar: async () => {
      for (const id of pendentes) {
        const c = componentes.find((x) => x.id === id)!
        c.install_state = opcoes.falham?.includes(id) ? 'not_installed' : 'installed'
      }
      pendentes.clear()
    }
  }
  return r
}

beforeEach(() => _reiniciarParaTeste())

describe('faltando', () => {
  it('so conta o que esta disponivel, nao vem embutido e ainda nao foi baixado', () => {
    const lista = faltando([
      comp('foto', 'not_installed'),
      comp('video', 'installed'),
      comp('musica', 'not_installed', { built_in: true }),
      comp('sonicmaster', 'not_installed', { available: false }),
      comp('voz', 'update_available')
    ])
    expect(lista.map((c) => c.id)).toEqual(['foto'])
  })
})

describe('baixarModelosIniciais', () => {
  it('baixa o que falta, um de cada vez, e encerra o pedido', async () => {
    const a = api([
      comp('foto', 'not_installed'),
      comp('voz', 'not_installed'),
      comp('video', 'installed')
    ])
    await baixarModelosIniciais(a)
    expect(a.instalados).toEqual(['foto', 'voz'])
    expect(modelosIniciais).toMatchObject({
      fase: 'pronto',
      total: 2,
      concluidos: 2,
      visivel: true
    })
    expect(a.concluido).toBe(true)
  })

  it('se um falha, o pedido continua pendente para a proxima abertura', async () => {
    const a = api([comp('foto', 'not_installed'), comp('voz', 'not_installed')], {
      falham: ['foto']
    })
    await baixarModelosIniciais(a)
    // Os outros seguem: uma falha nao impede o resto de baixar.
    expect(a.instalados).toEqual(['foto', 'voz'])
    expect(modelosIniciais).toMatchObject({ fase: 'erro', concluidos: 1, total: 2 })
    expect(a.concluido).toBe(false)
  })

  it('sem pedido do instalador, nao faz nada', async () => {
    for (const estado of [null, 'concluido'] as const) {
      _reiniciarParaTeste()
      const a = api([comp('foto', 'not_installed')], { estado })
      await baixarModelosIniciais(a)
      expect(a.instalados).toEqual([])
      expect(modelosIniciais.visivel).toBe(false)
    }
  })

  it('com tudo ja baixado, encerra o pedido sem mostrar aviso', async () => {
    const a = api([comp('foto', 'installed')])
    await baixarModelosIniciais(a)
    expect(a.concluido).toBe(true)
    expect(modelosIniciais.visivel).toBe(false)
  })

  it('roda uma vez por sessao, mesmo chamada de novo', async () => {
    // A licenca pode passar por "ativa" mais de uma vez na mesma sessao.
    const a = api([comp('foto', 'not_installed')])
    await Promise.all([baixarModelosIniciais(a), baixarModelosIniciais(a)])
    await baixarModelosIniciais(a)
    expect(a.instalados).toEqual(['foto'])
  })

  it('API fora do ar: nenhum aviso, e o pedido fica para depois', async () => {
    const a = api([comp('foto', 'not_installed')])
    a.listar = async () => {
      throw new Error('conexao recusada')
    }
    await baixarModelosIniciais(a)
    expect(modelosIniciais).toMatchObject({ fase: 'inativo', visivel: false })
    expect(a.concluido).toBe(false)
  })
})

import { ref, type Ref } from 'vue'
import { api, hasNativeApi } from '../services/native'
import { settingsState } from '../store/settings'
import type { ImageExport } from '../store/jobs'
import { usePerguntaDeConflito, type PerguntaDeConflito } from './usePerguntaDeConflito'

// A exportacao da Imagem numa etapa so': formato, qualidade, pasta, nome e
// conflito sao escolhidos antes de processar, como no Video e no Audio, e o
// job entrega o resultado direto no destino (app/exportacao_de_imagem.py).
// Antes era uma segunda etapa, depois do processamento, por uma rota propria.
//
// As escolhas valem para a tela; o nome, so' para a imagem ativa -- "Processar
// todos" usa o nome de cada original.
export function useExportPanel(): {
  exportacao: Ref<ImageExport>
  exportFilename: Ref<string | null>
  pergunta: PerguntaDeConflito
  pickExportFolder: () => Promise<void>
} {
  const exportacao = ref<ImageExport>({
    format: settingsState.defaultExportFormat,
    profile: settingsState.defaultImageProfile,
    directory: settingsState.defaultOutputFolder,
    conflict: 'rename'
  })
  const exportFilename = ref<string | null>(null)
  const pergunta = usePerguntaDeConflito()

  async function pickExportFolder(): Promise<void> {
    if (!hasNativeApi) return
    const folder = await api.selectOutputFolder(exportacao.value.directory ?? undefined)
    // Cancelar mantem a pasta que estava.
    if (folder) exportacao.value.directory = folder
  }

  return { exportacao, exportFilename, pergunta, pickExportFolder }
}

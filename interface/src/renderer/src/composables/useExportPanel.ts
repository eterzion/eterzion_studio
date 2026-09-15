import { ref, type Ref } from 'vue'
import { api, hasNativeApi } from '../services/native'
import { settingsState } from '../store/settings'
import { exportOne, type Job } from '../store/jobs'
import { usePerguntaDeConflito, type PerguntaDeConflito } from './usePerguntaDeConflito'

// Extracted from ImageEditorView.vue — the export panel (format/quality/
// destination/filename/conflict-resolution) is a self-contained state
// machine, operated on whichever job is passed to its functions — it
// doesn't need to track the active job itself. See
// specs/003-interface-restructure/research.md Decisão 3.
export function useExportPanel(): {
  exportFormat: Ref<'png' | 'jpg' | 'webp'>
  exportQuality: Ref<number>
  exportDestFolder: Ref<string | null>
  exportFilename: Ref<string | null>
  exportConflict: Ref<'overwrite' | 'rename' | 'ask'>
  /** A mesma pergunta dos outros modos (ConflictDialog). */
  pergunta: PerguntaDeConflito
  runExport: (j: Job) => Promise<void>
  pickExportFolder: () => Promise<void>
} {
  const exportFormat = ref<'png' | 'jpg' | 'webp'>(settingsState.defaultExportFormat)
  const exportQuality = ref(settingsState.defaultQuality)
  const exportDestFolder = ref<string | null>(settingsState.defaultOutputFolder)
  const exportFilename = ref<string | null>(null)
  const exportConflict = ref<'overwrite' | 'rename' | 'ask'>('rename')
  const pergunta = usePerguntaDeConflito()

  function exportar(
    j: Job,
    conflict: 'overwrite' | 'rename' | 'ask'
  ): ReturnType<typeof exportOne> {
    return exportOne(j, {
      format: exportFormat.value,
      quality: exportQuality.value,
      outputDir: exportDestFolder.value,
      filename: exportFilename.value,
      conflict
    })
  }

  async function runExport(j: Job): Promise<void> {
    const result = await exportar(j, exportConflict.value)
    if (result.ok || !j.exportConflicted || exportConflict.value !== 'ask') return
    const resposta = await pergunta.perguntar(j.exportConflictPath ?? '')
    if (resposta) {
      await exportar(j, resposta)
      return
    }
    // Cancelar a pergunta nao e' falha: nada foi gravado.
    j.exportState = 'idle'
    j.exportError = undefined
    j.exportConflicted = false
  }

  async function pickExportFolder(): Promise<void> {
    if (!hasNativeApi) return
    const folder = await api.selectOutputFolder(exportDestFolder.value ?? undefined)
    if (folder) exportDestFolder.value = folder
  }

  return {
    exportFormat,
    exportQuality,
    exportDestFolder,
    exportFilename,
    exportConflict,
    pergunta,
    runExport,
    pickExportFolder
  }
}

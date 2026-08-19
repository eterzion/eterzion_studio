import { ref, type Ref } from 'vue'
import { api, hasNativeApi } from '../services/native'
import { settingsState } from '../store/settings'
import { exportOne, type Job } from '../store/jobs'

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
  conflictPrompt: Ref<{ job: Job } | null>
  runExport: (j: Job) => Promise<void>
  resolveConflict: (mode: 'overwrite' | 'rename') => Promise<void>
  pickExportFolder: () => Promise<void>
} {
  const exportFormat = ref<'png' | 'jpg' | 'webp'>(settingsState.defaultExportFormat)
  const exportQuality = ref(settingsState.defaultQuality)
  const exportDestFolder = ref<string | null>(settingsState.defaultOutputFolder)
  const exportFilename = ref<string | null>(null)
  const exportConflict = ref<'overwrite' | 'rename' | 'ask'>('rename')
  const conflictPrompt = ref<{ job: Job } | null>(null)

  async function runExport(j: Job): Promise<void> {
    const result = await exportOne(j, {
      format: exportFormat.value,
      quality: exportQuality.value,
      outputDir: exportDestFolder.value,
      filename: exportFilename.value,
      conflict: exportConflict.value
    })
    if (!result.ok && j.exportConflicted && exportConflict.value === 'ask') {
      conflictPrompt.value = { job: j }
    }
  }

  async function resolveConflict(mode: 'overwrite' | 'rename'): Promise<void> {
    if (!conflictPrompt.value) return
    const j = conflictPrompt.value.job
    conflictPrompt.value = null
    await exportOne(j, {
      format: exportFormat.value,
      quality: exportQuality.value,
      outputDir: exportDestFolder.value,
      filename: exportFilename.value,
      conflict: mode
    })
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
    conflictPrompt,
    runExport,
    resolveConflict,
    pickExportFolder
  }
}

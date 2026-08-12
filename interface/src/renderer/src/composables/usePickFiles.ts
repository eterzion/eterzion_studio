import type { Ref } from 'vue'
import { api, hasNativeApi, type DescribedFile } from '../nativeBridge'

// Consolidates the native "pick files → per-file callback" shell that was
// byte-identical across VideoView/AudioView/CompressConvertView/ConverterView
// (confirmed via diff, see specs/003-interface-restructure/research.md) — each
// view still owns its own per-file validation/job shape via `addFile`.
// ImageEditorView.vue is NOT a consumer: its intake flow batches through
// store/jobs.ts's addFiles() and shares state (uploading/reportImportResult)
// with pickFolder/handleFilesDropped/handlePaste, which this app has nowhere
// else — see research.md for why that stays inline instead of being split.
export function usePickFiles(
  addFile: (file: DescribedFile) => void | Promise<void>,
  importError: Ref<string | null>
): { pickFiles: () => Promise<void> } {
  async function pickFiles(): Promise<void> {
    if (!hasNativeApi) {
      importError.value = 'Seleção de arquivos disponível apenas no aplicativo desktop.'
      return
    }
    const result = await api.selectFiles()
    if (result.canceled) return
    importError.value = null
    for (const f of result.files) await addFile(f)
  }

  return { pickFiles }
}

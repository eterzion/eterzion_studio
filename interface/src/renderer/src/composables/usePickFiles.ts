import { ref, type Ref } from 'vue'
import { i18n } from '../i18n'
import { api, hasNativeApi, type DescribedFile, type MediaKind } from '../services/native'

// Consolidates the native "pick files → per-file callback" shell that was
// byte-identical across VideoView/AudioView
// (confirmed via diff, see specs/003-interface-restructure/research.md) — each
// view still owns its own per-file validation/job shape via `addFile`.
// ImageEditorView.vue is NOT a consumer: its intake flow batches through
// store/jobs.ts's addFiles() and shares state (uploading/reportImportResult)
// with pickFolder/handleFilesDropped/handlePaste, which this app has nowhere
// else — see research.md for why that stays inline instead of being split.
// `pickFolder`/`handleFilesDropped`/`uploading` live here (not per-view) because
// every consumer now renders the same UploadZone, which emits all three intake
// events — duplicating them across Áudio/Vídeo/Otimizar/Converter would be the
// exact copy-paste this composable was created to remove.
export function usePickFiles(
  addFile: (file: DescribedFile) => void | Promise<void>,
  importError: Ref<string | null>,
  /** What this screen can open. The native dialog offers only these formats,
      and anything else is rejected on the way back — the dialog's filter is a
      default the person can switch off, not a guarantee. */
  kinds?: MediaKind[]
): {
  pickFiles: () => Promise<void>
  pickFolder: () => Promise<void>
  handleFilesDropped: (dropped: File[]) => Promise<void>
  uploading: Ref<boolean>
} {
  const uploading = ref(false)

  async function pickFiles(): Promise<void> {
    if (!hasNativeApi) {
      importError.value = i18n.global.t('importing.filesDesktopOnly')
      return
    }
    uploading.value = true
    try {
      const result = await api.selectFiles(kinds)
      if (result.canceled) return
      importError.value = null
      for (const f of result.files) await addFile(f)
    } catch (error) {
      importError.value =
        error instanceof Error ? error.message : i18n.global.t('importing.pickFilesFailed')
    } finally {
      uploading.value = false
    }
  }

  async function pickFolder(): Promise<void> {
    if (!hasNativeApi) {
      importError.value = i18n.global.t('importing.folderDesktopOnly')
      return
    }
    uploading.value = true
    try {
      const result = await api.selectFolder(kinds)
      if (result.canceled) return
      if (result.files.length === 0) {
        importError.value = i18n.global.t('importing.noFilesInFolder')
        return
      }
      importError.value = null
      for (const f of result.files) await addFile(f)
    } catch (error) {
      importError.value =
        error instanceof Error ? error.message : i18n.global.t('importing.pickFolderFailed')
    } finally {
      uploading.value = false
    }
  }

  async function handleFilesDropped(dropped: File[]): Promise<void> {
    if (!hasNativeApi) {
      importError.value = i18n.global.t('importing.dropDesktopOnly')
      return
    }
    uploading.value = true
    try {
      const described = await Promise.all(
        dropped.map((file) => api.statPath(api.getPathForFile(file)))
      )
      importError.value = null
      for (const d of described) if (d) await addFile(d)
    } catch (error) {
      importError.value = error instanceof Error ? error.message : i18n.global.t('upload.failed')
    } finally {
      uploading.value = false
    }
  }

  return { pickFiles, pickFolder, handleFilesDropped, uploading }
}

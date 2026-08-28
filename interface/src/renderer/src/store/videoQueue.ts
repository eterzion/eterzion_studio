import { reactive } from 'vue'
import type { MediaHandle } from '../services/api'

// The video list lived inside VideoEditorView as a `ref`, which had two costs:
// the Início queue could not see it (it only reads store/jobs.ts, so videos and
// audio were simply absent from "Fila de processamento"), and the list only
// survived a tab switch because App.vue wraps the screen in <KeepAlive>. A
// module store fixes both — the queue is data, and data outlives the component
// that happens to be showing it.

export interface EditorVideo {
  handle: MediaHandle
  /** For the eterzion-media:// preview URL and the enhance route, which predates
      handles. Never sent to the edit routes — those take handle_id only
      (Princípio XIII). */
  sourcePath: string
}

export const videoQueue = reactive<{ videos: EditorVideo[]; activeId: string | null }>({
  videos: [],
  activeId: null
})

export function addVideo(video: EditorVideo): void {
  videoQueue.videos.push(video)
  videoQueue.activeId ??= video.handle.handle_id
}

export function removeVideo(handleId: string): void {
  videoQueue.videos = videoQueue.videos.filter((v) => v.handle.handle_id !== handleId)
  if (videoQueue.activeId === handleId) {
    videoQueue.activeId = videoQueue.videos[0]?.handle.handle_id ?? null
  }
}

/** Move one video to a new index. Used by the Início queue's drag-to-reorder:
 *  processing is serial, so the order of this array is the order they run in. */
export function reorderVideo(fromIndex: number, toIndex: number): void {
  const list = videoQueue.videos
  if (fromIndex < 0 || fromIndex >= list.length) return
  if (toIndex < 0 || toIndex >= list.length) return
  const [moved] = list.splice(fromIndex, 1)
  list.splice(toIndex, 0, moved)
}

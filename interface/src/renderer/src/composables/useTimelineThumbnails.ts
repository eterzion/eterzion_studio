import { ref, watch, type Ref } from 'vue'
import { BASE_URL, type MediaHandle } from '../services/api'

// T038 (specs/007-video-editor-player) — the timeline's thumbnail strip.
//
// Follows the shape the old denoise preview established for asynchronous preview
// state (research.md Decisão 2): its own request-race guard, and invalidation
// when the subject changes. Reusing that shape rather than inventing another is
// Princípio II applied to a pattern instead of to a function.

export interface TimelineThumbnails {
  spriteUrl: Ref<string | null>
  count: Ref<number>
  intervalSeconds: Ref<number>
  thumbWidth: Ref<number>
  thumbHeight: Ref<number>
  loading: Ref<boolean>
  /** Non-null when the strip could not be built. The timeline still works
      without it — a missing strip degrades navigation, it does not break it. */
  error: Ref<string | null>
}

export function useTimelineThumbnails(handle: Ref<MediaHandle | null>): TimelineThumbnails {
  const spriteUrl = ref<string | null>(null)
  const count = ref(0)
  const intervalSeconds = ref(0)
  const thumbWidth = ref(0)
  const thumbHeight = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let requestId = 0

  function reset(): void {
    // Revoking matters: a sprite for a three-hour file is not small, and
    // leaking one per file switch would accumulate for the session.
    if (spriteUrl.value) URL.revokeObjectURL(spriteUrl.value)
    spriteUrl.value = null
    count.value = 0
    intervalSeconds.value = 0
    error.value = null
  }

  async function load(): Promise<void> {
    const current = handle.value
    reset()
    if (!current) return

    const id = ++requestId
    loading.value = true
    try {
      const res = await fetch(`${BASE_URL}/media/handles/${current.handle_id}/thumbnails`)
      if (!res.ok) throw new Error(String(res.status))
      const blob = await res.blob()
      // A reply for the previous file must not land on the current one — the
      // exact bug the old denoise preview was fixed for.
      if (id !== requestId) return
      spriteUrl.value = URL.createObjectURL(blob)
      count.value = Number(res.headers.get('X-Astros-Thumb-Count') ?? 0)
      intervalSeconds.value = Number(res.headers.get('X-Astros-Thumb-Interval') ?? 0)
      thumbWidth.value = Number(res.headers.get('X-Astros-Thumb-Width') ?? 0)
      thumbHeight.value = Number(res.headers.get('X-Astros-Thumb-Height') ?? 0)
    } catch (cause) {
      if (id === requestId) error.value = cause instanceof Error ? cause.message : 'unknown'
    } finally {
      if (id === requestId) loading.value = false
    }
  }

  // content_key, not handle_id: the same file with changed content must rebuild
  // the strip (FR-017). Keying on the identifier alone would show frames from
  // content that no longer exists.
  watch(() => [handle.value?.handle_id, handle.value?.content_key], load, { immediate: true })

  return { spriteUrl, count, intervalSeconds, thumbWidth, thumbHeight, loading, error }
}

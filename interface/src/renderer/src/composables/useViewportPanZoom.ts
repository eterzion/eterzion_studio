import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { api, hasNativeApi } from '../services/native'

interface ViewportJob {
  id: string
  sourcePath: string
  status: string
  outputPath?: string
}

// Extracted from ImageEditorView.vue — pan/zoom/space-held-preview-toggle is a
// self-contained interaction module: it only reads the active job's source/
// export paths and status, it doesn't reference any of the editor's other
// concerns (denoise, export panel, scale config). See
// specs/003-interface-restructure/research.md Decisão 3.
export function useViewportPanZoom<T extends ViewportJob>(
  job: ComputedRef<T | undefined>
): {
  zoom: Ref<number>
  pan: Ref<{ x: number; y: number }>
  zoomLevels: number[]
  viewMode: Ref<'slider' | 'side-by-side'>
  spaceHeld: Ref<boolean>
  panning: Ref<boolean>
  mediaStyle: ComputedRef<{ transform: string; transformOrigin: string }>
  resetView: () => void
  onWheelZoom: (e: WheelEvent) => void
  onPanDown: (e: PointerEvent) => void
  onPanMove: (e: PointerEvent) => void
  onPanUp: () => void
  beforeSrc: ComputedRef<string>
  afterSrc: ComputedRef<string>
  onKeyDown: (e: KeyboardEvent) => void
  onKeyUp: (e: KeyboardEvent) => void
} {
  const zoom = ref(100)
  const pan = ref({ x: 0, y: 0 })
  const zoomLevels = [25, 50, 100, 200]
  const viewMode = ref<'slider' | 'side-by-side'>('slider')
  const spaceHeld = ref(false)
  const panning = ref(false)
  let panOrigin = { x: 0, y: 0, panX: 0, panY: 0 }

  // Single viewportState shared by every preview mode (spec 6.2) — applied to
  // the images via CSS transform, so slider divider/labels stay unscaled.
  const mediaStyle = computed(() => ({
    transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value / 100})`,
    transformOrigin: 'center center'
  }))

  function resetView(): void {
    zoom.value = 100
    pan.value = { x: 0, y: 0 }
  }

  function onWheelZoom(e: WheelEvent): void {
    zoom.value = Math.min(400, Math.max(10, zoom.value - Math.sign(e.deltaY) * 10))
  }

  function onPanDown(e: PointerEvent): void {
    panning.value = true
    panOrigin = { x: e.clientX, y: e.clientY, panX: pan.value.x, panY: pan.value.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  function onPanMove(e: PointerEvent): void {
    if (!panning.value) return
    pan.value = {
      x: panOrigin.panX + (e.clientX - panOrigin.x),
      y: panOrigin.panY + (e.clientY - panOrigin.y)
    }
  }
  function onPanUp(): void {
    panning.value = false
  }

  const beforeSrc = computed(() =>
    job.value && hasNativeApi ? api.toFileUrl(job.value.sourcePath) : ''
  )
  const afterSrc = computed(() => {
    if (!job.value || !hasNativeApi || job.value.status !== 'done' || !job.value.outputPath)
      return beforeSrc.value
    return api.toFileUrl(job.value.outputPath)
  })

  function onKeyDown(e: KeyboardEvent): void {
    if (e.code === 'Space' && job.value?.status === 'done') {
      e.preventDefault()
      spaceHeld.value = true
    }
  }
  function onKeyUp(e: KeyboardEvent): void {
    if (e.code === 'Space') spaceHeld.value = false
  }

  // Reset the viewport whenever the user switches to another image.
  watch(
    () => job.value?.id,
    () => resetView()
  )

  return {
    zoom,
    pan,
    zoomLevels,
    viewMode,
    spaceHeld,
    panning,
    mediaStyle,
    resetView,
    onWheelZoom,
    onPanDown,
    onPanMove,
    onPanUp,
    beforeSrc,
    afterSrc,
    onKeyDown,
    onKeyUp
  }
}

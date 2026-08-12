import { onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'

/** True only while the element's content is actually clipped by ellipsis —
 * so a tooltip can show up only when it adds information, not on every
 * option regardless of whether its text fits. */
export function useTruncated(
  el: Ref<HTMLElement | null>,
  watchSource?: Ref<unknown>
): Ref<boolean> {
  const truncated = ref(false)

  function check(): void {
    const node = el.value
    truncated.value = !!node && node.scrollWidth > node.clientWidth + 1
  }

  let observer: ResizeObserver | null = null
  onMounted(() => {
    check()
    observer = new ResizeObserver(check)
    if (el.value) observer.observe(el.value)
  })
  onBeforeUnmount(() => observer?.disconnect())
  if (watchSource) watch(watchSource, () => requestAnimationFrame(check))

  return truncated
}

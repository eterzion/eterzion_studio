/** Insert into a reactive collection and get back what Vue will actually watch.
 *
 * This exists because the same mistake was made three times in one codebase,
 * each time costing a debugging session and each time looking like a different
 * bug on screen:
 *
 *   store/jobs.ts       the detected content type never appeared until an
 *                       unrelated edit forced a re-render
 *   AudioView.vue       the card stayed on "Detectando…" forever
 *   VideoEditorView.vue the scale tabs kept showing the old mode after a click
 *
 * The cause is always the same. `reactive()` wraps a target in a Proxy, and the
 * collection stores that proxy — but the local variable still points at the raw
 * object underneath. Writing through the raw one changes the value, so reading
 * it back proves nothing, and never runs the proxy's set trap, so no watcher
 * and no render effect ever learns anything happened.
 *
 *   const job = { ... }
 *   state.jobs.push(job)
 *   job.status = 'done'        // updates, re-renders nothing
 *
 * The fix is one line and easy to forget, which is exactly why it belongs
 * behind a name instead of a comment.
 */

/** push, and return the element as the array now holds it. */
export function pushReactive<T extends object>(target: T[], item: T): T {
  target.push(item)
  return target[target.length - 1]
}

/** set, and return the value as the map now holds it. */
export function setReactive<K, V extends object>(target: Map<K, V>, key: K, value: V): V {
  target.set(key, value)
  return target.get(key) as V
}

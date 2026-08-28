import { nextTick, reactive, watch } from 'vue'
import { describe, expect, it } from 'vitest'

import { pushReactive, setReactive } from '../reactiveInsert'

// These pin the difference the helpers exist for, which is invisible if you
// only read the value back: writing to the raw object updates it just fine and
// notifies nobody. Every assertion here is about the effect firing, because
// that is what broke three times — the field on screen never changed.

describe('pushReactive', () => {
  it('returns something a watcher can see mutated', async () => {
    const state = reactive<{ items: { status: string }[] }>({ items: [] })
    const stored = pushReactive(state.items, { status: 'novo' })

    let fired = 0
    watch(
      () => state.items[0]?.status,
      () => (fired += 1)
    )

    stored.status = 'pronto'
    await nextTick()
    expect(fired).toBe(1)
  })

  it('the raw object handed in does NOT notify — the bug this prevents', async () => {
    const state = reactive<{ items: { status: string }[] }>({ items: [] })
    const raw = { status: 'novo' }
    state.items.push(raw)

    let fired = 0
    watch(
      () => state.items[0]?.status,
      () => (fired += 1)
    )

    raw.status = 'pronto'
    await nextTick()
    expect(state.items[0].status).toBe('pronto') // o valor mudou...
    expect(fired).toBe(0) // ...e nada foi avisado
  })

  it('still appends, and keeps order', () => {
    const state = reactive<{ items: { n: number }[] }>({ items: [] })
    pushReactive(state.items, { n: 1 })
    pushReactive(state.items, { n: 2 })
    expect(state.items.map((i) => i.n)).toEqual([1, 2])
  })
})

describe('setReactive', () => {
  it('returns something a watcher can see mutated', async () => {
    const map = reactive(new Map<string, { scale: string }>())
    const stored = setReactive(map, 'a', { scale: 'none' })

    let fired = 0
    watch(
      () => map.get('a')?.scale,
      () => (fired += 1)
    )

    stored.scale = '2x'
    await nextTick()
    expect(fired).toBe(1)
  })

  it('the raw object handed in does NOT notify', async () => {
    const map = reactive(new Map<string, { scale: string }>())
    const raw = { scale: 'none' }
    map.set('a', raw)

    let fired = 0
    watch(
      () => map.get('a')?.scale,
      () => (fired += 1)
    )

    raw.scale = '2x'
    await nextTick()
    expect(fired).toBe(0)
  })

  it('stores under the key given', () => {
    const map = reactive(new Map<string, { n: number }>())
    setReactive(map, 'chave', { n: 7 })
    expect(map.get('chave')?.n).toBe(7)
  })
})

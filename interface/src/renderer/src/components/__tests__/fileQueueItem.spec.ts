import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import FileQueueItem from '../FileQueueItem.vue'
import type { QueueEntry } from '../../store/mediaQueue'

// Reordering broke because the component declared a prop called `draggable`.
// Vue takes a declared prop out of the fallthrough attrs, so the native
// attribute of the same name never reached the root element and the browser
// never started a drag. These tests pin the attribute itself, not the prop:
// asserting on the prop would have passed happily while reordering stayed dead.

const i18n = createI18n({ legacy: false, locale: 'en', missingWarn: false, fallbackWarn: false })

function entry(overrides: Partial<QueueEntry> = {}): QueueEntry {
  return {
    id: 'a',
    kind: 'image',
    fileName: 'foto.png',
    sizeBytes: 1024,
    // Só uma entrada ainda em configuração pode ser reordenada (canReorder).
    status: 'configuring',
    progress: 0,
    ...overrides
  } as QueueEntry
}

function render(props: Record<string, unknown>) {
  return mount(FileQueueItem, { props, global: { plugins: [i18n] } })
}

describe('FileQueueItem — arraste para reordenar', () => {
  it('deixa a linha arrastável enquanto o punho está pressionado', async () => {
    const w = render({ entry: entry(), allowReorder: true })
    const row = w.get('.queue-item')

    // Em repouso a linha NÃO arrasta: ela também é o alvo de clique que abre o
    // arquivo, e arrastar a linha inteira tornaria esse clique arriscado.
    expect(row.attributes('draggable')).toBe('false')

    await w.get('.drag-handle').trigger('mousedown')
    expect(row.attributes('draggable')).toBe('true')

    await row.trigger('dragend')
    expect(row.attributes('draggable')).toBe('false')
  })

  it('não oferece punho quando a entrada não pode ser reordenada', () => {
    const w = render({ entry: entry(), allowReorder: false })
    expect(w.find('.drag-handle').exists()).toBe(false)
    expect(w.get('.queue-item').attributes('draggable')).toBe('false')
  })

  it('não oferece punho depois que a entrada saiu da configuração', () => {
    // Já enfileirada: mexer na ordem agora não mudaria mais nada.
    const w = render({ entry: entry({ status: 'queued' }), allowReorder: true })
    expect(w.find('.drag-handle').exists()).toBe(false)
  })

  it('não abre o arquivo ao clicar no punho', async () => {
    const w = render({ entry: entry(), allowReorder: true })
    await w.get('.drag-handle').trigger('click')
    expect(w.emitted('click')).toBeUndefined()
  })
})

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronDown, Search, AlertCircle, Check } from '@lucide/vue'
import AppSpinner from './atoms/AppSpinner.vue'
import { useTruncated } from '../composables/useTruncated'

export interface SelectOption {
  value: string | number
  label: string
  description?: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: string | number | null
    options: SelectOption[]
    placeholder?: string
    searchable?: boolean
    loading?: boolean
    error?: string | null
    disabled?: boolean
  }>(),
  {
    placeholder: 'Selecione…',
    searchable: false,
    loading: false,
    error: null,
    disabled: false
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const open = ref(false)
const query = ref('')
const activeIndex = ref(-1)
const root = ref<HTMLElement | null>(null)
const searchInput = ref<HTMLInputElement | null>(null)
const menu = ref<HTMLElement | null>(null)
const openUpward = ref(false)
const menuStyle = ref<{ left: string; width: string; top?: string; bottom?: string }>({
  left: '0px',
  width: '0px'
})

const effectiveSearchable = computed(() => props.searchable || props.options.length > 8)

const filteredOptions = computed(() => {
  if (!effectiveSearchable.value || !query.value.trim()) return props.options
  const q = query.value.trim().toLowerCase()
  return props.options.filter(
    (o) => o.label.toLowerCase().includes(q) || o.description?.toLowerCase().includes(q)
  )
})

const selected = computed(() => props.options.find((o) => o.value === props.modelValue))

const triggerLabelEl = ref<HTMLElement | null>(null)
const triggerLabelTruncated = useTruncated(triggerLabelEl, selected)

function openMenu(): void {
  if (props.disabled || props.loading) return
  open.value = true
  query.value = ''
  activeIndex.value = filteredOptions.value.findIndex((o) => o.value === props.modelValue)
  nextTick(() => {
    positionMenu()
    if (effectiveSearchable.value) searchInput.value?.focus()
    else root.value?.querySelector<HTMLElement>('.trigger')?.focus()
    scrollActiveIntoView()
  })
}

function closeMenu(): void {
  open.value = false
  activeIndex.value = -1
}

function toggleMenu(): void {
  if (open.value) closeMenu()
  else openMenu()
}

// The menu is teleported to <body> (see template) so it can float above any
// ancestor with overflow:hidden (e.g. CollapsiblePanel's collapse-animation
// clipping) — position:absolute relative to the trigger no longer applies once
// teleported, so it's positioned as position:fixed from the trigger's real
// on-screen rect instead, recomputed on open/scroll/resize.
function positionMenu(): void {
  const el = root.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  const spaceAbove = rect.top
  openUpward.value = spaceBelow < 260 && spaceAbove > spaceBelow
  menuStyle.value = openUpward.value
    ? {
        left: `${rect.left}px`,
        width: `${rect.width}px`,
        bottom: `${window.innerHeight - rect.top + 4}px`
      }
    : { left: `${rect.left}px`, width: `${rect.width}px`, top: `${rect.bottom + 4}px` }
}

function onWindowChange(): void {
  if (open.value) positionMenu()
}

function selectOption(option: SelectOption): void {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  closeMenu()
  root.value?.querySelector<HTMLElement>('.trigger')?.focus()
}

function scrollActiveIntoView(): void {
  nextTick(() => {
    const el = menu.value?.querySelector<HTMLElement>('[data-active="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  })
}

function onTriggerKeydown(e: KeyboardEvent): void {
  if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
    e.preventDefault()
    if (!open.value) openMenu()
    else if (e.key === 'Enter' && activeIndex.value >= 0)
      selectOption(filteredOptions.value[activeIndex.value])
  }
}

function onMenuKeydown(e: KeyboardEvent): void {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(filteredOptions.value.length - 1, activeIndex.value + 1)
    scrollActiveIntoView()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
    scrollActiveIntoView()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (activeIndex.value >= 0) selectOption(filteredOptions.value[activeIndex.value])
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closeMenu()
    root.value?.querySelector<HTMLElement>('.trigger')?.focus()
  } else if (e.key === 'Tab') {
    closeMenu()
  }
}

function onDocClick(e: MouseEvent): void {
  const target = e.target as Node
  if (!open.value) return
  const insideTrigger = root.value?.contains(target)
  const insideMenu = menu.value?.contains(target)
  if (!insideTrigger && !insideMenu) closeMenu()
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('mousedown', onDocClick)
    window.addEventListener('scroll', onWindowChange, true)
    window.addEventListener('resize', onWindowChange)
  } else {
    document.removeEventListener('mousedown', onDocClick)
    window.removeEventListener('scroll', onWindowChange, true)
    window.removeEventListener('resize', onWindowChange)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  window.removeEventListener('scroll', onWindowChange, true)
  window.removeEventListener('resize', onWindowChange)
})

watch(filteredOptions, () => {
  activeIndex.value = filteredOptions.value.length ? 0 : -1
})
</script>

<template>
  <div ref="root" class="app-select" :class="{ disabled, error: !!error }">
    <button
      class="trigger"
      type="button"
      :disabled="disabled || loading"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggleMenu"
      @keydown="onTriggerKeydown"
    >
      <span class="trigger-content">
        <slot name="selected" :option="selected">
          <span
            v-if="selected"
            ref="triggerLabelEl"
            class="trigger-label"
            :title="triggerLabelTruncated ? selected.label : undefined"
            >{{ selected.label }}</span
          >
          <span v-else class="trigger-placeholder">{{ placeholder }}</span>
        </slot>
      </span>
      <AppSpinner v-if="loading" :size="15" class="trigger-icon" />
      <ChevronDown v-else :size="15" class="trigger-icon chevron" :class="{ open }" />
    </button>

    <p v-if="error" class="error-text"><AlertCircle :size="12" /> {{ error }}</p>

    <Teleport to="body">
      <div
        v-if="open"
        ref="menu"
        class="menu"
        :class="{ upward: openUpward }"
        :style="menuStyle"
        role="listbox"
        tabindex="-1"
        @keydown="onMenuKeydown"
      >
        <div v-if="effectiveSearchable" class="search-row">
          <Search :size="14" class="search-icon" />
          <input
            ref="searchInput"
            v-model="query"
            type="text"
            placeholder="Buscar…"
            class="search-input"
          />
        </div>

        <div class="options" :class="{ empty: !filteredOptions.length }">
          <p v-if="!filteredOptions.length" class="empty-text">Nenhum resultado.</p>
          <button
            v-for="(option, i) in filteredOptions"
            :key="option.value"
            type="button"
            role="option"
            class="option"
            :class="{
              active: i === activeIndex,
              selected: option.value === modelValue,
              disabled: option.disabled
            }"
            :data-active="i === activeIndex"
            :aria-selected="option.value === modelValue"
            :disabled="option.disabled"
            @click="selectOption(option)"
            @mouseenter="activeIndex = i"
          >
            <slot name="option" :option="option" :selected="option.value === modelValue">
              <span class="option-text">
                <span class="option-label">{{ option.label }}</span>
                <span v-if="option.description" class="option-description">{{
                  option.description
                }}</span>
              </span>
            </slot>
            <Check v-if="option.value === modelValue" :size="14" class="option-check" />
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.app-select {
  position: relative;
  width: 100%;
}

.trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: var(--fs-label);
  font-family: inherit;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.trigger:hover:not(:disabled) {
  background: var(--surface-2);
}

.trigger:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.app-select.error .trigger {
  border-color: var(--color-danger);
}

.trigger-content {
  flex: 1;
  min-width: 0;
  text-align: left;
  overflow: hidden;
}

.trigger-label {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trigger-placeholder {
  color: var(--text-tertiary);
}

.trigger-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.chevron {
  transition: transform var(--transition-fast);
}

.chevron.open {
  transform: rotate(180deg);
}

.error-text {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-danger);
  margin-top: 4px;
}

.menu {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  z-index: 30;
  min-width: 200px;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  max-height: 280px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.menu.upward {
  top: auto;
  bottom: calc(100% + 4px);
}

.search-row {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  padding: 8px 10px;
  border-bottom: 1px solid var(--surface-border-soft);
  flex-shrink: 0;
}

.search-icon {
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: var(--fs-label);
  font-family: inherit;
}

.search-input:focus {
  outline: none;
}

.options {
  overflow-y: auto;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.empty-text {
  padding: var(--space-3);
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--fs-label);
  font-family: inherit;
  cursor: pointer;
}

.option.active {
  background: var(--surface-3);
}

.option.selected {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.option.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.option-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.option-label {
  overflow-wrap: break-word;
  word-break: break-word;
  white-space: normal;
}

.option-description {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow-wrap: break-word;
  word-break: break-word;
  white-space: normal;
}

.option-check {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--color-primary);
}

@media (max-width: 480px) {
  .menu {
    max-height: 220px;
  }
}
</style>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NavKey } from '../types'
import {
  Atom,
  Home,
  Image,
  Film,
  Headphones,
  Rocket,
  Layers,
  History,
  Settings,
  Moon,
  Sun,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  ChevronDown,
  LifeBuoy,
  Globe,
  BookOpen,
  Code2,
  MessageCircle,
  Mail,
  HelpCircle,
  ExternalLink,
  ShieldCheck
} from '@lucide/vue'

defineProps<{
  active: NavKey
  darkMode: boolean
}>()

const emit = defineEmits<{
  navigate: [key: NavKey]
  toggleTheme: []
}>()

const { t } = useI18n()

const items = computed<{ key: NavKey; label: string; icon: unknown }[]>(() => [
  { key: 'home', label: t('nav.home'), icon: Home },
  { key: 'imagem', label: t('nav.image'), icon: Image },
  { key: 'video', label: t('nav.video'), icon: Film },
  { key: 'audio', label: t('nav.audio'), icon: Headphones },
  { key: 'otimizar', label: t('nav.optimize'), icon: Rocket },
  { key: 'modelos', label: t('nav.models'), icon: Layers },
  { key: 'historico', label: t('nav.history'), icon: History }
])

// TODO(config): substituir pelos endereços reais antes de publicar — estes
// são placeholders para o módulo de suporte não abrir links inexistentes.
const supportLinks = computed<{ label: string; icon: unknown; url: string }[]>(() => [
  { label: t('sidebar.links.site'), icon: Globe, url: 'https://example.com/astros-upscale' },
  {
    label: t('sidebar.links.docs'),
    icon: BookOpen,
    url: 'https://example.com/astros-upscale/docs'
  },
  {
    label: t('sidebar.links.github'),
    icon: Code2,
    url: 'https://github.com/example/astros-upscale'
  },
  { label: t('sidebar.links.discord'), icon: MessageCircle, url: 'https://discord.gg/example' },
  {
    label: t('sidebar.links.faq'),
    icon: HelpCircle,
    url: 'https://example.com/astros-upscale/faq'
  },
  {
    label: t('sidebar.links.help'),
    icon: LifeBuoy,
    url: 'https://example.com/astros-upscale/help'
  },
  { label: t('sidebar.links.email'), icon: Mail, url: 'mailto:suporte@example.com' }
])

const collapsed = ref(localStorage.getItem('astros-upscale:sidebar-collapsed') === '1')
const supportOpen = ref(false)

function toggleCollapsed(): void {
  collapsed.value = !collapsed.value
  localStorage.setItem('astros-upscale:sidebar-collapsed', collapsed.value ? '1' : '0')
  if (collapsed.value) supportOpen.value = false
}

function toggleSupport(): void {
  if (collapsed.value) {
    collapsed.value = false
    supportOpen.value = true
    return
  }
  supportOpen.value = !supportOpen.value
}

function openExternal(url: string): void {
  // main/index.ts's setWindowOpenHandler routes this to shell.openExternal
  // and denies the in-app popup — opens in the OS's default browser.
  window.open(url, '_blank')
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="brand">
      <div class="brand-icon"><Atom :size="20" /></div>
      <div v-if="!collapsed" class="brand-text">
        <span class="brand-name">Astros Upscale</span>
      </div>
      <button
        class="collapse-btn"
        type="button"
        :title="collapsed ? t('sidebar.expand') : t('sidebar.collapse')"
        @click="toggleCollapsed"
      >
        <component :is="collapsed ? ChevronsRight : ChevronsLeft" :size="15" />
      </button>
    </div>

    <p v-if="!collapsed" class="section-label">{{ t('sidebar.navigation') }}</p>
    <nav class="nav">
      <button
        v-for="item in items"
        :key="item.key"
        class="nav-item"
        :class="{ active: active === item.key }"
        type="button"
        :title="item.label"
        @click="emit('navigate', item.key)"
      >
        <span class="active-bar" />
        <component :is="item.icon" :size="18" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <p v-if="!collapsed" class="section-label">{{ t('sidebar.support') }}</p>
      <div class="support-block">
        <button
          class="nav-item support-toggle"
          :class="{ active: supportOpen && !collapsed }"
          type="button"
          :title="t('sidebar.support')"
          @click="toggleSupport"
        >
          <LifeBuoy :size="18" class="nav-icon" />
          <span v-if="!collapsed" class="nav-item-text">
            <span class="nav-label">{{ t('sidebar.support') }}</span>
            <span class="nav-sublabel">{{ t('sidebar.links.help') }}</span>
          </span>
          <component
            :is="supportOpen ? ChevronDown : ChevronRight"
            v-if="!collapsed"
            :size="15"
            class="chevron"
          />
        </button>
        <Transition name="support-collapse">
          <div v-if="supportOpen && !collapsed" class="support-list">
            <button
              v-for="link in supportLinks"
              :key="link.label"
              class="support-link"
              type="button"
              @click="openExternal(link.url)"
            >
              <component :is="link.icon" :size="14" class="support-link-icon" />
              <span class="support-link-label">{{ link.label }}</span>
              <ExternalLink :size="11" class="support-link-ext" />
            </button>
          </div>
        </Transition>
      </div>

      <button
        class="nav-item"
        :class="{ active: active === 'configuracoes' }"
        type="button"
        :title="t('nav.settings')"
        @click="emit('navigate', 'configuracoes')"
      >
        <span class="active-bar" />
        <Settings :size="18" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{ t('nav.settings') }}</span>
        <ChevronRight v-if="!collapsed" :size="15" class="chevron" />
      </button>

      <p v-if="!collapsed" class="section-label">{{ t('sidebar.darkMode') }}</p>
      <button
        class="nav-item theme-toggle"
        type="button"
        :title="t('sidebar.toggleTheme')"
        @click="emit('toggleTheme')"
      >
        <component :is="darkMode ? Moon : Sun" :size="16" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{
          darkMode ? t('sidebar.darkMode') : t('sidebar.lightMode')
        }}</span>
        <span v-if="!collapsed" class="switch" :class="{ on: darkMode }"
          ><span class="knob"
        /></span>
      </button>

      <div v-if="!collapsed" class="version-badge">
        <ShieldCheck :size="16" class="version-badge-icon" />
        <div class="version-badge-text">
          <span class="version-badge-name">Astros Upscale</span>
          <span class="version-badge-number">v2.0.0</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 224px;
  flex-shrink: 0;
  height: 100vh;
  background: var(--surface-1);
  border-right: 1px solid var(--surface-border-soft);
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
  gap: var(--space-3);
  transition: width 180ms ease;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 68px;
  padding: var(--space-2);
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-1);
  width: 100%;
}

.sidebar.collapsed .brand {
  justify-content: center;
  padding: var(--space-2) 0;
}

.brand-icon {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6, var(--color-primary));
}

.brand-text {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.brand-name {
  font-weight: var(--fw-semibold);
  font-size: 15px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collapse-btn {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.collapse-btn:hover {
  background: var(--surface-3);
  color: var(--text-primary);
}

/* Collapsed: stack icon above the toggle instead of hiding it — hiding it
   left no way back to expanded state, a real dead end found via user report. */
.sidebar.collapsed .brand {
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 10px;
  font-weight: var(--fw-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  padding: 0 var(--space-2);
  margin: 0;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 11px var(--space-3);
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.nav-item-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  flex: 1;
}

.nav-sublabel {
  font-size: 11px;
  font-weight: var(--fw-regular, 400);
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
}

.chevron {
  flex-shrink: 0;
  margin-left: auto;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.nav-item.active .chevron {
  color: var(--color-primary);
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
  width: 44px;
}

.nav-item:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.nav-item:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.nav-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: var(--fw-semibold);
}

.active-bar {
  position: absolute;
  left: -1px;
  top: 4px;
  bottom: 4px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--color-primary);
  opacity: 0;
  transform: scaleY(0.4);
  transition:
    opacity 160ms ease,
    transform 160ms ease;
}

.nav-item.active .active-bar {
  opacity: 1;
  transform: scaleY(1);
}

.nav-icon {
  flex-shrink: 0;
}

.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.support-block {
  display: flex;
  flex-direction: column;
}

.support-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 2px var(--space-1) 6px 30px;
  overflow: hidden;
}

.support-collapse-enter-active,
.support-collapse-leave-active {
  transition:
    max-height 180ms ease,
    opacity 140ms ease;
  max-height: 220px;
}

.support-collapse-enter-from,
.support-collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

.support-link {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  padding: 6px var(--space-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.support-link:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.support-link:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.support-link-icon {
  flex-shrink: 0;
}

.support-link-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.support-link-ext {
  flex-shrink: 0;
  opacity: 0.6;
}

.switch {
  margin-left: auto;
  width: 32px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 999px;
  background: var(--surface-3);
  position: relative;
  transition: background var(--transition-fast);
}

.switch.on {
  background: var(--color-primary);
}

.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  transition: transform var(--transition-fast);
}

.switch.on .knob {
  transform: translateX(14px);
}

.version-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  padding: 9px var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
}

.version-badge-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}

.version-badge-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.version-badge-name {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-badge-number {
  font-size: 10px;
  color: var(--text-tertiary);
}

@media (max-width: 880px) {
  .sidebar:not(.collapsed) {
    width: 68px;
    padding: var(--space-2);
  }

  .sidebar:not(.collapsed) .brand {
    justify-content: center;
    padding: var(--space-2) 0;
  }

  .sidebar:not(.collapsed) .brand-text,
  .sidebar:not(.collapsed) .nav-label,
  .sidebar:not(.collapsed) .nav-item-text,
  .sidebar:not(.collapsed) .chevron,
  .sidebar:not(.collapsed) .section-label,
  .sidebar:not(.collapsed) .switch,
  .sidebar:not(.collapsed) .support-list,
  .sidebar:not(.collapsed) .version-badge {
    display: none;
  }

  .sidebar:not(.collapsed) .brand {
    flex-direction: column;
    gap: 6px;
  }

  .sidebar:not(.collapsed) .nav-item,
  .sidebar:not(.collapsed) .theme-toggle {
    justify-content: center;
    padding: 10px;
  }
}
</style>

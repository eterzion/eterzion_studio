<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, hasNativeApi } from '../services/native'
import type { NavKey } from '../types'
import type { SupportEndpoints } from '../constants/support'
import { configuredSupportLinks } from '../constants/support'
import AppButton from './atoms/AppButton.vue'
import {
  Home,
  Image,
  Film,
  Music,
  Minimize2,
  History,
  HardDrive,
  Settings,
  Moon,
  Sun,
  ChevronsLeft,
  ChevronsRight,
  ChevronRight,
  ChevronDown,
  LifeBuoy,
  Globe,
  MessageCircle,
  Mail,
  HelpCircle,
  ExternalLink,
  Tag
} from '@lucide/vue'

const props = defineProps<{
  active: NavKey
  darkMode: boolean
}>()

const emit = defineEmits<{
  navigate: [key: NavKey]
  toggleTheme: []
}>()

const { t } = useI18n()

// Official brand logo served by cdn.eterzion.com.
//
// **O sufixo nomeia o tema a que a arte serve, não a cor da tinta dela.**
// `logo-dark` tem traço claro (luminância média 201/255) e existe para fundo
// escuro; `logo-light` tem traço escuro (73/255), para fundo claro. Ler o nome
// ao contrário desenha o logo na cor do fundo — ele não some com erro nenhum,
// simplesmente deixa de ser visível, e o console fica limpo.
//
// O caminho anterior era `assets.ericinacio.com/branding/logo-256.webp`, e
// ele **existia** — foi removido do CDN em 13/08/2026, quando a marca do
// site passou a ter um diretório por variante (eterzion_assets 4c9610bf1,
// `11856 -> 0 bytes`). A convenção de lá hoje é um diretório por variante, e
// um caminho de segmento único cai no fallback de SPA da raiz do host: pedir
// uma imagem devolve `200 text/html`, então nem o código de status denuncia
// o engano.
//
// Consequência para quem tem uma cópia antiga instalada: o logo dela está
// quebrado desde aquela remoção, e nenhuma mudança de servidor conserta --
// o CSP empacotado só aceita o host antigo, que hoje nem responde. Manter
// `assets.ericinacio.com` no ar também não resolveria, porque o arquivo que
// aquelas builds pedem não existe mais.
//
// **E aconteceu de novo em 06/09/2026**, agora com `assets.eterzion.com`: o
// host foi aposentado e o catálogo passou a ser servido por
// `cdn.eterzion.com`, direto do R2. As builds 1.0.4 e anteriores continuam
// pedindo o host antigo e ficam sem logo para sempre, pelo mesmo motivo -- a
// CSP viaja dentro do pacote.
//
// Duas vezes é padrão, não azar: **o host da marca está fixo em dois lugares
// que precisam mudar juntos** -- esta URL e o `img-src` do CSP em
// `index.html`. Trocar só a URL não dá erro de rede; o navegador bloqueia a
// imagem e o sintoma é um espaço vazio. Se houver uma terceira migração, é
// sinal de que este valor deveria vir de configuração, e não daqui.
const brandLogoUrl = computed(() =>
  props.darkMode
    ? 'https://cdn.eterzion.com/branding/ez-logo-white/logo-256.webp'
    : 'https://cdn.eterzion.com/branding/ez-logo-black/logo-256.webp'
)

// `module` ties a nav entry to its accent (theme.css [data-module]), so the
// active item is tinted with the same colour as the screen it opens. Entries
// without one (Início, Histórico) keep the neutral accent.
// A versão vinha fixa como `v2.0.0` no template, e continuou dizendo isso
// durante as 1.0.4, 1.0.5, 1.0.6 e 1.0.7 — um usuário que relatasse um problema
// citando o número da tela daria a informação errada, e ninguém desconfiaria de
// um rótulo. O canal `app:version` já existia no main e no preload; só o
// componente não o usava.
//
// Sem valor inicial de propósito: um `'2.0.0'` de partida voltaria a mentir
// durante o primeiro quadro, que é exatamente o que se quer evitar.
const appVersion = ref('')

onMounted(async () => {
  // `hasNativeApi` é falso ao pré-visualizar num navegador comum, onde a ponte
  // do Electron não existe. Aí o distintivo fica vazio em vez de quebrar.
  if (!hasNativeApi) return
  try {
    appVersion.value = await api.getAppVersion()
  } catch {
    // Não vale derrubar a barra lateral por um rótulo.
  }
})

const items = computed<{ key: NavKey; label: string; icon: unknown; module?: string }[]>(() => [
  { key: 'home', label: t('nav.home'), icon: Home },
  { key: 'imagem', label: t('nav.image'), icon: Image, module: 'image' },
  { key: 'video', label: t('nav.video'), icon: Film, module: 'video' },
  { key: 'audio', label: t('nav.audio'), icon: Music, module: 'audio' },
  { key: 'compressao', label: t('nav.compression'), icon: Minimize2, module: 'compression' },
  { key: 'historico', label: t('nav.history'), icon: History }
])

// Só aparece o canal que tem endereço em constants/support.ts — o rótulo vem do
// i18n (Princípio XIV), o ícone daqui, e o endereço de lá. Nenhum link para
// lugar nenhum: se a lista sair vazia, o bloco Suporte inteiro não é renderizado.
const SUPPORT_ICONS: Record<keyof SupportEndpoints, unknown> = {
  site: Globe,
  discord: MessageCircle,
  faq: HelpCircle,
  help: LifeBuoy,
  email: Mail
}

const supportLinks = computed<{ label: string; icon: unknown; url: string }[]>(() =>
  configuredSupportLinks().map(({ key, url }) => ({
    label: t(`sidebar.links.${key}`),
    icon: SUPPORT_ICONS[key],
    url
  }))
)

const collapsed = ref(localStorage.getItem('eterzion-studio:sidebar-collapsed') === '1')
const supportOpen = ref(false)

function toggleCollapsed(): void {
  collapsed.value = !collapsed.value
  localStorage.setItem('eterzion-studio:sidebar-collapsed', collapsed.value ? '1' : '0')
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
      <div class="brand-icon">
        <img
          :src="brandLogoUrl"
          alt="Eterzion Studio"
          width="32"
          height="32"
          decoding="async"
          class="brand-logo"
        />
      </div>
      <div v-if="!collapsed" class="brand-text">
        <span class="brand-name">Eterzion Studio</span>
      </div>
      <AppButton
        variant="ghost"
        icon-only
        size="sm"
        :title="collapsed ? t('sidebar.expand') : t('sidebar.collapse')"
        @click="toggleCollapsed"
      >
        <template #icon
          ><component :is="collapsed ? ChevronsRight : ChevronsLeft" :size="15"
        /></template>
      </AppButton>
    </div>

    <nav class="nav">
      <button
        v-for="item in items"
        :key="item.key"
        class="nav-item"
        :class="{ active: active === item.key }"
        :data-module="item.module"
        type="button"
        :title="item.label"
        @click="emit('navigate', item.key)"
      >
        <component :is="item.icon" :size="18" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <!-- Sem nenhum canal configurado não há o que abrir, e um menu vazio é
           pior do que a ausência do item — ver constants/support.ts -->
      <div v-if="supportLinks.length > 0" class="support-block">
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
        :class="{ active: active === 'componentes' }"
        type="button"
        :title="t('nav.components')"
        @click="emit('navigate', 'componentes')"
      >
        <HardDrive :size="18" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{ t('nav.components') }}</span>
        <ChevronRight v-if="!collapsed" :size="15" class="chevron" />
      </button>

      <button
        class="nav-item"
        :class="{ active: active === 'configuracoes' }"
        type="button"
        :title="t('nav.settings')"
        @click="emit('navigate', 'configuracoes')"
      >
        <Settings :size="18" class="nav-icon" />
        <span v-if="!collapsed" class="nav-label">{{ t('nav.settings') }}</span>
        <ChevronRight v-if="!collapsed" :size="15" class="chevron" />
      </button>

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
        <Tag :size="16" class="version-badge-icon" />
        <span class="version-badge-number">v{{ appVersion }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 248px;
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
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.brand-text {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
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

/* Collapsed: stack icon above the toggle instead of hiding it — hiding it
   left no way back to expanded state, a real dead end found via user report. */
.sidebar.collapsed .brand {
  flex-direction: column;
  gap: var(--space-1-5);
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
  border-radius: var(--radius-full);
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
  border-radius: var(--radius-sm);
  background: #fff;
  transition: transform var(--transition-fast);
}

.switch.on .knob {
  transform: translateX(14px);
}

.version-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  margin-top: 4px;
  padding: 9px var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
}

.version-badge-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}

.version-badge-number {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
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
    gap: var(--space-1-5);
  }

  .sidebar:not(.collapsed) .nav-item,
  .sidebar:not(.collapsed) .theme-toggle {
    justify-content: center;
    padding: 10px;
  }
}
</style>

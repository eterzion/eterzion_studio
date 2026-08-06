<script setup lang="ts">
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
  Sun
} from '@lucide/vue'

defineProps<{
  active: NavKey
  darkMode: boolean
}>()

const emit = defineEmits<{
  navigate: [key: NavKey]
  toggleTheme: []
}>()

const items: { key: NavKey; label: string; icon: unknown }[] = [
  { key: 'home', label: 'Home', icon: Home },
  { key: 'imagem', label: 'Imagem', icon: Image },
  { key: 'video', label: 'Vídeo', icon: Film },
  { key: 'audio', label: 'Áudio', icon: Headphones },
  { key: 'otimizar', label: 'Otimizar', icon: Rocket },
  { key: 'modelos', label: 'Modelos', icon: Layers },
  { key: 'historico', label: 'Histórico', icon: History },
  { key: 'configuracoes', label: 'Configurações', icon: Settings }
]
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-icon"><Atom :size="20" /></div>
      <div class="brand-text">
        <span class="brand-name">Astros Upscale</span>
        <span class="brand-version">v2.0.0</span>
      </div>
    </div>

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
        <component :is="item.icon" :size="18" class="nav-icon" />
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <button class="theme-toggle" type="button" @click="emit('toggleTheme')">
        <component :is="darkMode ? Moon : Sun" :size="16" />
        <span>Modo {{ darkMode ? 'escuro' : 'claro' }}</span>
        <span class="switch" :class="{ on: darkMode }"><span class="knob" /></span>
      </button>
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
  gap: var(--space-4);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-1);
}

.brand-icon {
  width: 32px;
  height: 32px;
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
}

.brand-name {
  font-weight: var(--fw-semibold);
  font-size: 15px;
  color: var(--text-primary);
}

.brand-version {
  font-size: 10px;
  font-weight: var(--fw-semibold);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  padding: 1px 6px;
  border-radius: 999px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 9px var(--space-2);
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  text-align: left;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.nav-item:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.nav-icon {
  flex-shrink: 0;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  cursor: pointer;
  padding: var(--space-1);
}

.switch {
  margin-left: auto;
  width: 32px;
  height: 18px;
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

@media (max-width: 880px) {
  .sidebar {
    width: 68px;
    padding: var(--space-2);
  }

  .brand {
    justify-content: center;
    padding: var(--space-2) 0;
  }

  .brand-text,
  .nav-label,
  .theme-toggle span:not(.switch),
  .switch {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 10px;
  }

  .theme-toggle {
    justify-content: center;
  }
}
</style>

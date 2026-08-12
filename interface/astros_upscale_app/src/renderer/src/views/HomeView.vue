<script setup lang="ts">
import TopBar from '../components/TopBar.vue'
import { Image, Film, Headphones, Rocket, ArrowRight } from '@lucide/vue'
import type { NavKey } from '../types'

const emit = defineEmits<{
  navigate: [key: NavKey]
}>()

// Home is a pure launcher now — each category tab (Imagem/Vídeo/Áudio/
// Otimizar) owns its own upload zone and queue directly (Imagem's used to
// live here and require a detour through Home; it's self-contained now,
// matching how the other three already worked).
const CATEGORIES: { key: NavKey; label: string; description: string; icon: unknown }[] = [
  {
    key: 'imagem',
    label: 'Imagem',
    description: 'Aumente a resolução de fotos e ilustrações com IA.',
    icon: Image
  },
  {
    key: 'video',
    label: 'Vídeo',
    description: 'Aumente a resolução de vídeos preservando fps e áudio.',
    icon: Film
  },
  {
    key: 'audio',
    label: 'Áudio',
    description: 'Reduza ruído, normalize volume e melhore a clareza da voz ou música.',
    icon: Headphones
  },
  {
    key: 'otimizar',
    label: 'Otimizar',
    description: 'Comprima ou converta imagens, vídeos e áudios sem IA.',
    icon: Rocket
  }
]
</script>

<template>
  <div class="home-view">
    <TopBar title="Home" />

    <div class="home-content">
      <p class="intro">O que você quer melhorar hoje?</p>

      <div class="category-grid">
        <button
          v-for="category in CATEGORIES"
          :key="category.key"
          class="category-card"
          type="button"
          @click="emit('navigate', category.key)"
        >
          <div class="category-icon">
            <component :is="category.icon" :size="22" />
          </div>
          <div class="category-text">
            <span class="category-label">{{ category.label }}</span>
            <span class="category-description">{{ category.description }}</span>
          </div>
          <ArrowRight :size="18" class="category-arrow" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

.home-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.intro {
  font-size: var(--fs-h3, 1.1rem);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.category-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-align: left;
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.category-card:hover {
  background: var(--surface-2);
  border-color: var(--color-primary-soft);
}

.category-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.category-icon {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.category-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.category-description {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.category-arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
}
</style>

<script setup lang="ts">
import { computed } from 'vue'

// Custom neon "pixel dissolve" artwork for the Home category cards — a
// scatter of small squares (unprocessed/pixelated) resolving into a crisp
// glowing glyph (enhanced), echoing what the app actually does to media.
// One shared pixel-cloud layout is reused across variants; only the crisp
// glyph on the right differs per category.
const props = defineProps<{
  variant: 'imagem' | 'video' | 'audio' | 'otimizar' | 'converter'
  tint: string
}>()

const glowId = computed(() => `cat-glow-${props.variant}`)

// Shared scatter of small squares, sparse at the edges and denser toward the
// glyph — reused as-is for every category, tinted via currentColor.
const PIXELS: { x: number; y: number; s: number; o: number }[] = [
  { x: 8, y: 20, s: 3, o: 0.12 },
  { x: 16, y: 14, s: 4, o: 0.16 },
  { x: 22, y: 26, s: 3, o: 0.16 },
  { x: 10, y: 34, s: 5, o: 0.2 },
  { x: 24, y: 40, s: 4, o: 0.24 },
  { x: 14, y: 48, s: 6, o: 0.28 },
  { x: 28, y: 54, s: 5, o: 0.32 },
  { x: 34, y: 32, s: 6, o: 0.34 },
  { x: 22, y: 18, s: 4, o: 0.22 },
  { x: 38, y: 46, s: 7, o: 0.4 },
  { x: 42, y: 28, s: 6, o: 0.4 },
  { x: 46, y: 58, s: 8, o: 0.46 },
  { x: 50, y: 40, s: 7, o: 0.5 },
  { x: 54, y: 50, s: 9, o: 0.55 },
  { x: 58, y: 33, s: 8, o: 0.5 },
  { x: 36, y: 63, s: 6, o: 0.32 },
  { x: 44, y: 68, s: 5, o: 0.28 },
  { x: 30, y: 70, s: 4, o: 0.2 },
  { x: 18, y: 60, s: 4, o: 0.22 },
  { x: 12, y: 46, s: 3, o: 0.16 }
]
</script>

<template>
  <svg class="category-icon-art" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <filter :id="glowId" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="4.5" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>

    <g :fill="tint">
      <rect
        v-for="(p, i) in PIXELS"
        :key="i"
        :x="p.x"
        :y="p.y"
        :width="p.s"
        :height="p.s"
        :opacity="p.o"
        rx="1"
      />
    </g>

    <g :filter="`url(#${glowId})`" :stroke="tint" :fill="tint">
      <!-- Imagem: frame + sun + mountain -->
      <template v-if="variant === 'imagem'">
        <rect x="60" y="18" width="46" height="38" rx="6" fill="none" stroke-width="4.5" />
        <circle cx="73" cy="30" r="4.5" :fill="tint" stroke="none" />
        <path
          d="M66 50 L79 36 L89 46 L98 34 L106 50"
          fill="none"
          stroke-width="4.5"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
      </template>

      <!-- Vídeo: frame + play + sprockets -->
      <template v-else-if="variant === 'video'">
        <rect x="58" y="16" width="38" height="46" rx="6" fill="none" stroke-width="4.5" />
        <path d="M72 32 L72 50 L88 41 Z" stroke="none" :fill="tint" stroke-linejoin="round" />
        <rect x="100" y="20" width="5" height="5" rx="1" stroke="none" :fill="tint" opacity="0.85" />
        <rect x="100" y="32" width="5" height="5" rx="1" stroke="none" :fill="tint" opacity="0.85" />
        <rect x="100" y="44" width="5" height="5" rx="1" stroke="none" :fill="tint" opacity="0.85" />
        <rect x="100" y="56" width="5" height="5" rx="1" stroke="none" :fill="tint" opacity="0.85" />
      </template>

      <!-- Áudio: duas colcheias ligadas -->
      <template v-else-if="variant === 'audio'">
        <line x1="70" y1="24" x2="70" y2="66" stroke-width="4.5" stroke-linecap="round" />
        <line x1="98" y1="16" x2="98" y2="58" stroke-width="4.5" stroke-linecap="round" />
        <path d="M70 24 L98 16" stroke-width="4.5" stroke-linecap="round" />
        <path d="M70 33 L98 25" stroke-width="4.5" stroke-linecap="round" />
        <ellipse cx="64" cy="68" rx="8" ry="6" stroke="none" :fill="tint" transform="rotate(-12 64 68)" />
        <ellipse cx="92" cy="60" rx="8" ry="6" stroke="none" :fill="tint" transform="rotate(-12 92 60)" />
      </template>

      <!-- Otimizar: foguete -->
      <template v-else-if="variant === 'otimizar'">
        <path
          d="M86 16 C98 32 98 52 90 66 L78 66 C70 52 70 32 82 16 Z"
          stroke="none"
          :fill="tint"
        />
        <circle cx="84" cy="36" r="5.5" fill="var(--surface-1)" :stroke="tint" stroke-width="3" />
        <path d="M78 60 L64 72 L76 64 Z" stroke="none" :fill="tint" opacity="0.9" />
        <path d="M90 60 L104 72 L92 64 Z" stroke="none" :fill="tint" opacity="0.9" />
        <path d="M80 66 L84 82 L88 66 Z" stroke="none" :fill="tint" opacity="0.75" />
      </template>

      <!-- Converter: dois arquivos com setas de conversão -->
      <template v-else>
        <g stroke="none" :fill="tint">
          <path d="M58 22 H76 L84 30 V52 H58 Z" opacity="0.95" />
          <path d="M76 22 L76 30 L84 30 Z" fill="var(--surface-1)" />
        </g>
        <g stroke="none" :fill="tint">
          <path d="M84 48 H102 L110 56 V78 H84 Z" opacity="0.95" />
          <path d="M102 48 L102 56 L110 56 Z" fill="var(--surface-1)" />
        </g>
        <path
          d="M88 40 Q100 34 106 42"
          fill="none"
          stroke-width="3.5"
          stroke-linecap="round"
        />
        <path d="M101 38 L106 42 L100 45" fill="none" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />
        <path
          d="M78 58 Q66 64 60 56"
          fill="none"
          stroke-width="3.5"
          stroke-linecap="round"
        />
        <path d="M65 60 L60 56 L66 53" fill="none" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />
      </template>
    </g>
  </svg>
</template>

<style scoped>
.category-icon-art {
  width: 100%;
  height: 100%;
  display: block;
}
</style>

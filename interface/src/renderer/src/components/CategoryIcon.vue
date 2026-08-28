<script setup lang="ts">
import { computed } from 'vue'
import { Shrink } from '@lucide/vue'
import imageArtwork from '../assets/home-image.webp'
import videoArtwork from '../assets/home-video.webp'
import audioArtwork from '../assets/home-audio.webp'

const props = defineProps<{
  variant: 'imagem' | 'video' | 'audio' | 'compressao'
  tint: string
}>()

// `compressao` ainda não tem ilustração própria (specs/008). Um ícone tingido
// com o mesmo acento mantém o cartão coerente e **não finge** ter arte que não
// existe — reaproveitar a de outra categoria diria que a Central é aquela outra
// coisa. Quando `home-compression.webp` existir, entra aqui e o fallback some.
const artworkByVariant = {
  imagem: imageArtwork,
  video: videoArtwork,
  audio: audioArtwork
} as const

const artwork = computed(() =>
  props.variant in artworkByVariant
    ? artworkByVariant[props.variant as keyof typeof artworkByVariant]
    : null
)
</script>

<template>
  <img v-if="artwork" class="category-bitmap-art" :class="`art-${variant}`" :src="artwork" alt="" />
  <span v-else class="category-icon-art" :style="{ color: tint }">
    <Shrink :size="72" :stroke-width="1.5" />
  </span>
</template>

<style scoped>
.category-icon-art {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  opacity: 0.85;
}

.category-bitmap-art {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center;
  mix-blend-mode: screen;
  transform: scale(0.9);
  filter: saturate(1.04) contrast(1.04);
}

/* The audio bitmap was drawn cyan, back when that was the module's colour, and
   it is the one card whose art no longer matches its own border and glow.
   Rotating it the ~37 degrees from cyan to the new green is an approximation of
   redrawing the asset, not a replacement for it — the hue lands right, the
   per-stroke shading does not shift the way an artist would shift it. */
.art-audio {
  filter: saturate(1.04) contrast(1.04) hue-rotate(-37deg);
}

/* The artwork is bright, saturated strokes on transparency. `screen` is what
   makes them glow against the dark theme's near-black card — but screening
   toward a near-white card pushes every one of those strokes to white, which is
   why the light theme rendered four empty rectangles. `multiply` is the mirror
   image of that blend: it leaves the light ground alone and keeps the stroke's
   own colour, so the same bitmap reads on both themes without a second asset. */
:root[data-theme='light'] .category-bitmap-art {
  mix-blend-mode: multiply;
  filter: saturate(1.1) contrast(1.06) brightness(0.92);
}

:root[data-theme='light'] .art-audio {
  filter: saturate(1.1) contrast(1.06) brightness(0.92) hue-rotate(-37deg);
}
</style>

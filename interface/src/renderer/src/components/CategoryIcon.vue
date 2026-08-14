<script setup lang="ts">
import { computed } from 'vue'
import imageArtwork from '../assets/home-image.webp'
import videoArtwork from '../assets/home-video.webp'
import audioArtwork from '../assets/home-audio.webp'

const props = defineProps<{
  variant: 'imagem' | 'video' | 'audio'
  tint: string
}>()

const artworkByVariant = {
  imagem: imageArtwork,
  video: videoArtwork,
  audio: audioArtwork
} as const

const artwork = computed(() => artworkByVariant[props.variant])
</script>

<template>
  <img class="category-bitmap-art" :src="artwork" alt="" />
</template>

<style scoped>
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
</style>

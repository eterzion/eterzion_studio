<script setup lang="ts">
import { computed } from 'vue'
import imageArtwork from '../assets/home-image.webp'
import videoArtwork from '../assets/home-video.webp'
import audioArtwork from '../assets/home-audio.webp'
import converterArtwork from '../assets/home-converter.webp'

const props = defineProps<{
  variant: 'imagem' | 'video' | 'audio' | 'exportar'
  tint: string
}>()

const artworkByVariant = {
  imagem: imageArtwork,
  video: videoArtwork,
  audio: audioArtwork,
  exportar: converterArtwork
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
</style>

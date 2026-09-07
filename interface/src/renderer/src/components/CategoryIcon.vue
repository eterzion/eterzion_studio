<script setup lang="ts">
import { computed } from 'vue'
import { Film, Image as ImageIcon, Music, Shrink } from '@lucide/vue'

const props = defineProps<{
  variant: 'imagem' | 'video' | 'audio' | 'compressao'
  tint: string
}>()

/**
 * Ícone de traço, tingido com o acento do módulo.
 *
 * Antes, três das quatro categorias usavam bitmaps sobrepostos com
 * `mix-blend-mode: screen` — era isso que produzia o brilho neon sobre o fundo
 * quase preto. A Compressão nunca teve arte e já usava um ícone tingido; este
 * componente agora faz o que ela fazia, para as quatro.
 *
 * O que sai junto com o brilho:
 *
 *  - ~500 KB de `.webp` no pacote;
 *  - o `hue-rotate(-37deg)` do áudio, que girava uma arte desenhada em ciano
 *    para o verde do módulo. O comentário anterior admitia que "o matiz acerta,
 *    o sombreado por traço não" — com vetor, a cor é a cor;
 *  - as regras de tema claro que existiam só porque `screen` empurrava cada
 *    traço para o branco sobre fundo claro, obrigando a trocar para `multiply`.
 *    Um ícone com `currentColor` lê nos dois temas sem tratamento.
 */
const ICONE = {
  imagem: ImageIcon,
  video: Film,
  audio: Music,
  compressao: Shrink
} as const

const icone = computed(() => ICONE[props.variant])
</script>

<template>
  <span class="category-icon-art" :style="{ color: tint }">
    <component :is="icone" :size="72" :stroke-width="1.5" />
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
</style>

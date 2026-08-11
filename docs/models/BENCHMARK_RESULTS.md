# Resultados do Benchmark de Perfis (T023, FR-087 a FR-093)

**Metodologia**: `scripts/benchmark_profiles.py` — protocolo clássico de SR (degrade-and-restore) sobre imagens de referência sintéticas geradas neste próprio script (ver docstring). Métrica principal: LPIPS (menor = mais parecido perceptualmente); guarda-corpo de fidelidade: PSNR/SSIM (maior = melhor).

**Limitação disclosed**: referências são sintéticas, não fotos/arte reais — resultado é uma comparação relativa entre candidatos nesta máquina, não uma medição de qualidade no mundo real. O passe de avaliação visual humana exigido por FR-087 **não foi feito** — nenhum humano revisou os resultados; isso fica pendente antes de tratar esta escolha como definitiva sem revisão.

## photo

| Modelo | Arquitetura | Escala | LPIPS ↓ | PSNR ↑ | SSIM ↑ | Tempo (s) |
|---|---|---|---|---|---|---|
| nomos-webphoto **(vencedor)** | RealPLKSR | 4x | 0.1855 | 26.28 | 0.5955 | 3.57 |
| nomos2-dat2 | DAT-2 (transformer) | 4x | 0.2701 | 23.66 | 0.4369 | 92.59 |
| realesr-general | SRVGGNetCompact | 4x | 0.3859 | 26.94 | 0.6873 | 0.05 |
| realesrgan-x2 | RRDBNet (ESRGAN) | 2x | 0.4635 | 18.13 | 0.5025 | 0.47 |
| realesrnet-x4 | RRDBNet (ESRGAN) | 4x | 0.6087 | 19.52 | 0.5175 | 0.72 |
| realesrgan-x4 | RRDBNet (ESRGAN) | 4x | 0.6907 | 16.80 | 0.3748 | 0.54 |

## anime_image

| Modelo | Arquitetura | Escala | LPIPS ↓ | PSNR ↑ | SSIM ↑ | Tempo (s) |
|---|---|---|---|---|---|---|
| hfa2k-span **(vencedor)** | SPAN | 2x | 0.0838 | 17.60 | 0.7071 | 2.34 |
| realesrgan-anime | RRDBNet (ESRGAN, 6 blocos) | 4x | 0.1156 | 13.71 | 0.5530 | 0.14 |

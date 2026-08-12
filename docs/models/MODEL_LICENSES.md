# Matriz de Licenças — Modelos e Componentes de Terceiros

**Última verificação:** 2026-08-08
**Método:** verificação independente contra a fonte oficial de cada projeto (arquivo `LICENSE` do
repositório, `model card` do Hugging Face, metadados de API). O registro pré-existente do
repositório (`modelLicenses.ts`) **não** foi usado como fonte — foi tratado como afirmação a ser
confirmada ou refutada.

## Critério de aprovação (Princípio IV — Commercial License Only)

```
Licença permite uso comercial de forma EXPLÍCITA?
        │
        ├── SIM, sem ambiguidade ──────────► APROVADO
        ├── NÃO (NC, research-only) ───────► REJEITADO
        └── Sem declaração / dúvida ───────► REJEITADO (registrado como INDETERMINADO)
```

Regras que se aplicam sempre:
- **"Open source", "está no GitHub", "pip install funciona" não são evidência de permissão comercial.**
- **Código e pesos são verificados separadamente.** Um repositório MIT pode distribuir pesos que não são MIT.
- **Ausência de arquivo de licença = todos os direitos reservados ao autor = REJEITADO.**
- **Componentes de terceiros embutidos contaminam o todo.** Uma licença permissiva no topo do
  arquivo não vale se o corpo declara dependências não-comerciais.

---

## 1. Modelos de super-resolução de imagem

| Model | Purpose | Source | Code License | Weights License | Commercial Use | Redistribution | Restrictions | Verified At |
|---|---|---|---|---|---|---|---|---|
| RealESRGAN_x2plus | SR 2x geral | github.com/xinntao/Real-ESRGAN | BSD-3-Clause | Coberto pelo BSD-3 do repo distribuidor | **SIM** | Permitida | Atribuição + disclaimer. Ver nota DIV2K | 2026-08-08 |
| RealESRGAN_x4plus | SR 4x geral | idem | BSD-3-Clause | idem | **SIM** | Permitida | idem | 2026-08-08 |
| RealESRGAN_x4plus_anime_6B | SR 4x anime | idem | BSD-3-Clause | idem | **SIM** | Permitida | Dataset de treino não documentado | 2026-08-08 |
| RealESRNet_x4plus | SR 4x (PSNR) | idem | BSD-3-Clause | idem | **SIM** | Permitida | Ver nota DIV2K | 2026-08-08 |
| realesr-general-x4v3 | SR 4x leve | idem | BSD-3-Clause | idem | **SIM** | Permitida | — | 2026-08-08 |
| realesr-general-wdn-x4v3 | SR 4x denoise (DNI) | idem | BSD-3-Clause | idem | **SIM** | Permitida | — | 2026-08-08 |
| realesr-animevideov3 | SR vídeo anime | idem | BSD-3-Clause | idem | **SIM** | Permitida | — | 2026-08-08 |
| 2xHFA2kAVCCompact | SR 2x anime/AVC | huggingface.co/Phips/2xHFA2kAVCCompact | — | CC-BY-4.0 | **SIM** | Permitida | **Atribuição obrigatória a Philip Hofmann** | 2026-08-08 |
| 1xDeJPG_realplksr_otf | Remoção artefato JPEG | openmodeldb.info/models/1x-DeJPG-realplksr-otf | — | CC-BY-4.0 | **SIM** | Permitida | **Atribuição obrigatória** | 2026-08-08 |
| 1xDeNoise_realplksr_otf | Denoise 1x | huggingface.co/Phips/1xDeNoise_realplksr_otf | — | CC-BY-4.0 | **SIM** | Permitida | **Atribuição obrigatória** | 2026-08-08 |
| 4x-UltraSharp | SR 4x | huggingface.co/Kim2091/UltraSharp | — | **CC-BY-NC-SA-4.0** | **NÃO** | Só não-comercial | NonCommercial explícito no model card do autor | 2026-08-08 |
| 4x-AnimeSharp | SR 4x anime | huggingface.co/Kim2091/AnimeSharp | — | **CC-BY-NC-SA-4.0** | **NÃO** | Só não-comercial | NonCommercial explícito | 2026-08-08 |
| 4x_NMKD-Siax_200k | SR 4x fotos | openmodeldb.info/models/4x-NMKD-Siax-CX | — | WTFPL (só catálogo de terceiro) | **INDETERMINADO** | — | Sem declaração de primeira mão do autor NMKD | 2026-08-08 |
| 4x_NMKD-Superscale-SP | SR 4x fotos | openmodeldb.info/models/4x-NMKD-Superscale | — | WTFPL (só catálogo de terceiro) | **INDETERMINADO** | — | Sem declaração de primeira mão | 2026-08-08 |
| liveaction-span | SR live action | openmodeldb.info | — | CC-BY-NC-SA-4.0 | **NÃO** | Só não-comercial | NonCommercial | 2026-08-08 |

### Nota sobre o dataset DIV2K — DECISÃO DOCUMENTADA (2026-08-08)

Os Real-ESRGAN de propósito geral foram treinados com DF2K (DIV2K + Flickr2K) + OST. A página
oficial do DIV2K declara: *"The DIV2K dataset is made available for academic research purpose only."*

Isto é a **mesma zona cinzenta** que reprovou toda a categoria de restauração facial (seção 2, via
FFHQ). Aplicar o critério com rigor absoluto aqui derrubaria também o upscaler de fotos — ou seja,
a função principal do produto.

**Decisão do dono do projeto: aceitar e documentar a assimetria.**

Fundamento da decisão:
- O detentor do copyright dos pesos (Xintao Wang) concedeu BSD-3-Clause **explicitamente**, sem
  cláusula de restrição derivada de dataset.
- Se pesos treinados constituem "obra derivada" de um dataset é uma questão **juridicamente não
  resolvida**, com argumentos sérios dos dois lados.
- Diferença material em relação ao caso facial: no FFHQ a NVIDIA aplica CC-BY-NC-SA 4.0 **com
  share-alike** ao dataset como um todo, e os autores dos modelos faciais **não** concederam
  licença comercial explícita aos pesos. Aqui, o autor concedeu.

**Risco aceito conscientemente**, registrado por escrito e datado. Esta decisão MUST ser
reavaliada se houver jurisprudência ou mudança de termos. Não é parecer jurídico.

O mesmo raciocínio se aplica aos pesos treinados em WIDER FACE (detectores) — cuja licença não foi
verificável (site com certificado TLS inválido em 2026-08-08).

### Nota sobre o conflito do UltraSharp

O mirror de download `huggingface.co/uwg/upscaler` marca o arquivo como MIT, contradizendo o
CC-BY-NC-SA-4.0 declarado pelo autor original (Kim2091) em seu próprio model card. **A declaração
do autor prevalece sobre a de um mirror de terceiro.** Veredito: rejeitado.

---

## 2. Restauração facial

**Conclusão da pesquisa: não existe nenhum modelo de restauração facial que passe no critério.**
12 candidatos verificados. A contaminação é sistemática e ocorre em três camadas independentes.

| Modelo | Code License | Weights License | Problema | Commercial Use | Verified At |
|---|---|---|---|---|---|
| GFPGAN v1.4 | Apache-2.0 *com componentes NC* | Herda StyleGAN2 | StyleGAN2 (NVIDIA NC) + DFDNet (CC-BY-NC-SA) + FFHQ | **NÃO** | 2026-08-08 |
| CodeFormer | **S-Lab License 1.0** | S-Lab 1.0 | Licença NC direta | **NÃO** | 2026-08-08 |
| DifFace | **S-Lab License 1.0** | S-Lab 1.0 | Licença NC direta | **NÃO** | 2026-08-08 |
| PGDiff | **NTU S-Lab License 1.0** | S-Lab 1.0 | NC + modelo do DifFace | **NÃO** | 2026-08-08 |
| GPEN | Sem arquivo LICENSE | — | *"For academic and non-commercial use only"* | **NÃO** | 2026-08-08 |
| DiffBIR (face) | Apache-2.0 | Apache-2.0 | SwinIR-Face do DifFace (NC) + SD2.1 RAIL++-M | **INDETERMINADO** | 2026-08-08 |
| RestoreFormer | **Apache-2.0** | não declarada | **Treinado em FFHQ** | **NÃO** | 2026-08-08 |
| RestoreFormer++ | **Apache-2.0** | não declarada | **Treinado em FFHQ** | **NÃO** | 2026-08-08 |
| VQFR | **Apache-2.0** (sem StyleGAN2) | não declarada | **Treinado em FFHQ** | **NÃO** | 2026-08-08 |
| PMRF | **MIT** | **MIT** | **Treinado em FFHQ** + checkpoint SwinIR do DifFace | **NÃO** | 2026-08-08 |
| RealRestorer | Apache-2.0 | NC acadêmico | *"non-commercial academic research use only"* | **NÃO** | 2026-08-08 |
| Re-uploads no HF | — | sem tag | Nenhuma evidência de licença | **NÃO** | 2026-08-08 |

### A camada decisiva: FFHQ

`RestoreFormer`, `VQFR` e `PMRF` têm licença de código **e** de pesos genuinamente permissiva
(Apache-2.0 / MIT). Reprovam apenas pelo dataset.

**FFHQ** (github.com/NVlabs/ffhq-dataset) — NVIDIA:
> *"All of these licenses allow free use, redistribution, and adaptation for non-commercial
> purposes."* / *"The dataset itself … is made available under Creative Commons BY-NC-SA 4.0"*

Praticamente 100% dos modelos de rosto publicados treinam em FFHQ. Isso torna a categoria inteira
inacessível a um produto comercial.

Datasets faciais alternativos verificados: **CelebA / CelebA-HQ** — *"available for non-commercial
research purposes only"*, cláusula que alcança explicitamente "derived data" (rejeitados).
**SFHQ 1–4** — LICENSE MIT, mas imagens sintetizadas com StyleGAN (contaminação na origem).
**SFHQ-T2I** — gerado com Flux1.dev/pro (não-comercial) e DALL-E 3 (ToS restritivo); a afirmação
do autor de que "não há problemas de licença" não se sustenta.

### GPL-3.0 no produto atual — verificado empiricamente

`facexlib` (usado por `face_restore.py:46`) agrega componentes de licenças mistas. Seu
`__init__.py` executa:

```python
from .tracking import *      # SORT (abewley/sort) — GPL-3.0
```

Qualquer import de submódulo do `facexlib` dispara o `__init__.py` e carrega o SORT.
**Verificado em `.venv/Lib/site-packages/facexlib/__init__.py` em 2026-08-08.**

O `facexlib` também agrega MODNet (CC-4.0) em `matting/`. O próprio README do projeto avisa:
*"You need to refer to their original LICENCEs for your intended use."*

**Num binário Electron distribuído comercialmente, a GPL-3.0 é mais grave que o problema do
GFPGAN** — ela exigiria abrir o código-fonte do Astros inteiro.

### DECISÃO (2026-08-08)

**Remover a recuperação facial por IA. Substituir por realce determinístico de região de rosto.**

Componentes aprovados para o substituto:

| Componente | Licença | Uso |
|---|---|---|
| YuNet (`cv2.FaceDetectorYN`) | **MIT** (código e modelo `.onnx`) | Detecção de rosto + 5 landmarks |
| MediaPipe Face Detection | Apache-2.0 | Alternativa/fallback |
| OpenCV (unsharp, CLAHE, bilateral) | Apache-2.0 | Realce local |

Técnica: na bounding box do rosto do output já upscalado, aplicar com máscara elíptica *feathered*
(evita costura visível): unsharp mask de raio pequeno com threshold (combate o "efeito plástico"
que o Real-ESRGAN produz em pele), CLAHE em luminância com clip limit 1.0–2.0 (micro-contraste em
olhos e boca), e sharpen seletivo nas sub-regiões dos landmarks. Custo: milissegundos, CPU, sem
pesos, determinístico.

**O que se perde, honestamente:** o GFPGAN reconstrói rostos muito degradados (fotos antigas,
baixíssima resolução) inventando um rosto plausível. Nenhum filtro tradicional faz isso. Para o
caso de uso dominante de um upscaler — fotos digitais razoáveis — a diferença é pequena, e o
GFPGAN frequentemente piora, aplicando acabamento sintético uniforme.

A feature MUST ser renomeada: não pode continuar prometendo "recuperação facial por IA".

### Ações obrigatórias decorrentes

1. Remover `astros_upscale/face_restore.py` e a dependência `gfpgan`/pesos GFPGAN
2. **Remover a dependência `facexlib` por completo** (risco GPL-3.0, independente do GFPGAN)
3. Auditar o bundle do Electron/PyInstaller para confirmar que nenhum dos dois é empacotado

---

## 3. Engines de áudio

| Engine | Purpose | Source | Code License | Weights License | Commercial Use | Restrictions | Verified At |
|---|---|---|---|---|---|---|---|
| audiosronnx | Bandwidth extension (AudioSR ONNX) | github.com/TigreGotico/audiosronnx | Apache-2.0 | **Apache-2.0** | **SIM** | NOTICE Apache-2.0 | 2026-08-08 |
| voicefixer | Restauração de voz | github.com/haoheliu/voicefixer | MIT | CC-BY-4.0 (Zenodo 5600188) | **SIM, com ressalva** | Atribuição a Haohe Liu. Ver ressalva | 2026-08-08 |
| AudioSR (haoheliu) — código | Super-resolução de áudio | github.com/haoheliu/versatile_audio_super_resolution | MIT | — | **INDETERMINADO** | Ver conflito AudioLDM | 2026-08-08 |
| haoheliu/audiosr_basic | Pesos AudioSR | huggingface.co/haoheliu/audiosr_basic | — | Apache-2.0 | SIM (isolado) | Ver conflito AudioLDM | 2026-08-08 |
| haoheliu/audiosr_speech | Pesos AudioSR fala | huggingface.co/haoheliu/audiosr_speech | — | **nenhuma declarada** | **INDETERMINADO** | Sem model card, sem campo `license` | 2026-08-08 |
| AudioLDM (upstream) | Base do latent diffusion | github.com/haoheliu/AudioLDM | **CC-BY-NC-SA-4.0** | CC-BY-NC-SA-4.0 | **NÃO** | NonCommercial + ShareAlike | 2026-08-08 |
| denoiser (Meta) | Denoise de voz | github.com/facebookresearch/denoiser | **CC-BY-NC-4.0** | CC-BY-NC-4.0 | **NÃO** | NonCommercial | 2026-08-08 |
| demucs | Separação de fontes | github.com/facebookresearch/demucs | MIT | **research only** | **NÃO** (pesos) | Ver abaixo | 2026-08-08 |
| HiFi-GAN (jik876) | Vocoder | github.com/jik876/hifi-gan | MIT | — | **SIM** (código) | Manter aviso de copyright | 2026-08-08 |

### Conflito AudioSR ↔ AudioLDM

O repositório AudioSR declara MIT, mas `audiosr/latent_diffusion` é derivação direta do AudioLDM
(mesmo autor), que é CC-BY-NC-SA-4.0. Há conflito não resolvido entre a licença declarada e a
origem do código.

**Veredito: INDETERMINADO → tratado como rejeitado.** Só destravável com autorização escrita de
Haohe Liu.

**Alternativa limpa disponível:** `audiosronnx` (TigreGotico) implementa bandwidth extension com
código **e** pesos sob Apache-2.0 declarado explicitamente. É a rota comercialmente viável para
super-resolução de áudio.

### Ressalva sobre voicefixer

O projeto distribui dois checkpoints:
- `vf.ckpt` (analysis) — CC-BY-4.0 via Zenodo record 5600188 ✅
- `model.ckpt-1490000_trimed.pt` (synthesis/vocoder TFGAN) — **sem licença localizável** ⚠

Pela regra "dúvida = rejeitado", o vocoder isoladamente é INDETERMINADO. Confirmar por escrito
com o autor antes de embarcar.

### Nota sobre demucs

O código é MIT em todas as versões (v2, v3, v4). Os **pesos** não são. O mantenedor declarou
publicamente: *"The model weights are not covered by the MIT license, and are provided only for
scientific purposes"* e *"The models are trained using MusDB dataset, which requires the result
model can only be used for research purpose."*

---

## 4. Componentes aprovados para as capacidades a construir

| Capacidade | Componente | Tipo | License | Commercial Use | Verified At |
|---|---|---|---|---|---|
| Redução de ruído | RNNoise (Xiph) | RNN pequena + DSP | BSD-3-Clause | **SIM** | 2026-08-08 |
| Redução de ruído | FFmpeg `arnndn` | Filtro (usa modelo RNNoise) | BSD-3-Clause | **SIM** | 2026-08-08 |
| Redução de ruído | FFmpeg `afftdn`, `anlmdn` | DSP | LGPL-2.1+ | **SIM** | 2026-08-08 |
| Redução de ruído | noisereduce | DSP (spectral gating) | MIT | **SIM** | 2026-08-08 |
| Redução de ruído | DeepFilterNet | IA | Código MIT/Apache-2.0; **pesos sem declaração** | **INDETERMINADO** | 2026-08-08 |
| Loudness | FFmpeg `loudnorm` | DSP (EBU R128) | LGPL-2.1+ | **SIM** | 2026-08-08 |
| Loudness | pyloudnorm | DSP (ITU-R BS.1770) | MIT | **SIM** | 2026-08-08 |
| Loudness | FFmpeg `dynaudnorm` | DSP | LGPL-2.1+ | **SIM** | 2026-08-08 |
| Voz | FFmpeg `deesser` | DSP | MIT | **SIM** | 2026-08-08 |
| Voz | FFmpeg `firequalizer`, `acompressor` | DSP | LGPL-2.1+ | **SIM** | 2026-08-08 |
| Voz | SpeechBrain (framework) | IA | Apache-2.0 | **SIM** | 2026-08-08 |
| Voz | speechbrain/metricgan-plus-voicebank | IA | Apache-2.0 | **SIM** | 2026-08-08 |
| Voz | speechbrain/sepformer-wham16k-enhancement | IA | Apache-2.0 | **SIM** | 2026-08-08 |
| Voz | Silero models | IA | **CC-BY-NC** | **NÃO** | 2026-08-08 |

**Atenção com SpeechBrain:** a licença é declarada **por modelo** no Hugging Face. O Apache-2.0 do
framework não cobre automaticamente cada checkpoint. Verificar a tag de cada model card
individualmente antes de embarcar.

### Redução de artefatos de compressão de áudio

**Não existe solução madura, mantida e comercialmente licenciada.** A pesquisa encontrou apenas
literatura acadêmica de 2024–2025 (challenges de speech restoration) e modelos sem licença clara.

**Recomendação: não prometer essa capacidade no produto.**

---

## 3-bis. Melhoria de música — SonicMaster (uso condicional, decisão do dono do produto)

**Verificado em:** 2026-08-08

| Componente | Repo/URL | Licença código | Licença pesos | Uso comercial |
|---|---|---|---|---|
| SonicMaster (AMAAI Lab) | github.com/AMAAI-Lab/SonicMaster · huggingface.co/amaai-lab/SonicMaster | Apache-2.0 | Apache-2.0 (tag HF) | **CONDICIONAL — ver risco abaixo** |
| ↳ dependência obrigatória: Stable Audio Open 1.0 VAE | huggingface.co/stabilityai/stable-audio-open-1.0 | — | Stability AI Community License | **NÃO acima de US$1.000.000 de receita anual** |

### O que o SonicMaster é

Restauração e masterização de música por texto-instrução (EQ, dinâmica, reverb, amplitude, imagem
estéreo) via flow matching. Código e pesos próprios sob Apache-2.0. Dataset de treino
(`SonicMasterDataset`) derivado do Jamendo sob CC-BY-2.0, compatível com uso comercial.

### O risco real — não é uma formalidade

O SonicMaster **não roda sozinho**. Ele depende, em tempo de inferência, do autoencoder latente do
**Stable Audio Open 1.0** para codificar e decodificar o sinal estéreo 44.1 kHz — isso está descrito
no próprio paper (arXiv:2508.03448), não é uma dependência opcional.

A licença desse VAE é a **Stability AI Community License**, que declara textualmente que usuários
com mais de **USD $1.000.000 em receita anual** devem cessar o uso e negociar uma licença
enterprise separada (`stability.ai/community-license-agreement`).

Isso não é uma licença não-comercial simples — é uma licença comercial **com prazo de validade
atrelado ao sucesso do próprio produto**. Diferente de um "NÃO" definitivo, ela vira um "SIM, até
você crescer o suficiente para que isso importe" — e nesse ponto a obrigação de negociar (ou
parar de usar) é real e contratual, não apenas ética.

### Decisão registrada (2026-08-08)

**O dono do projeto optou por usar o SonicMaster mesmo assim**, contra a recomendação padrão do
critério "dúvida = rejeitar" da Constitution (Princípio IV). Esta é uma exceção deliberada e
documentada, não um erro de auditoria.

**Condições que devem acompanhar essa decisão, registradas para ação futura:**

1. **Monitorar a receita do produto.** Ao se aproximar de US$ 1.000.000/ano, este componente
   precisa ser removido, substituído, ou uma licença enterprise da Stability AI precisa ser
   negociada — o que vier primeiro.
2. **Não é um risco "resolvido depois do lançamento e esquecido".** É uma obrigação recorrente que
   precisa de dono e de revisão periódica (sugestão: revisão anual de receita vs. limite).
3. **Créditos de atribuição obrigatórios** (Apache-2.0 do SonicMaster + termos da Stability AI)
   devem aparecer na visão de detalhes técnicos do produto.
4. Se a Stability AI alterar os termos da Community License no futuro, esta linha precisa ser
   reverificada — a licença não é imutável.

### Alternativa descartada de propósito

`Apollo` (JusperLee) seria o segundo candidato mais próximo — mas está duplamente contaminado
(CC-BY-SA-4.0 do código + treino em MUSDB18-HQ "educational purposes only" + MoisesDB CC-BY-NC-SA)
e não foi escolhido.

---

## 3-ter. Vídeo real — resolvido, sem ressalva de licença

**Verificado em:** 2026-08-08. Pesquisa cobriu 671 modelos catalogados no OpenModelDB, filtrados
programaticamente por licença, mais toda a família clássica de VSR temporal (BasicVSR/BasicVSR++/
RealBasicVSR/VRT/RVRT). O único modelo cujo propósito declarado é live action
(`2xLiveActionV1_SPAN`) é CC-BY-NC-SA-4.0 — confirmado, permanece rejeitado.

Diferente da música, aqui a solução **não precisa de ressalva de risco**: existe um candidato limpo.

| Componente | Papel | Repo/URL | Licença código | Licença pesos | Dataset | Uso comercial |
|---|---|---|---|---|---|---|
| `2xPublic_realplksr_dysample_layernorm_real` (variante `_nn`, sem denoise) | Implementação principal — vídeo real 2x | github.com/Phhofm/models/releases/tag/2xPublic_realplksr_dysample_layernorm_real | Apache-2.0 (arquitetura MIT/Apache-2.0 em toda a cadeia) | **Apache-2.0** | 56K+ imagens de domínio público (CC0) | **SIM, sem ressalva** |
| `1xDeH264_realplksr` (já aprovado, ver seção 1) | Pré-passo opcional de remoção de artefato H.264 | openmodeldb.info/models/1x-DeH264-realplksr | MIT (neosr/realplksr) | CC-BY-4.0 | nomosv2 | SIM (atribuição a Philip Hofmann) |
| `2xNomosUni_span_multijpg_ldl` (já aprovado) | Alternativa de velocidade máxima / caminho CPU | openmodeldb.info | MIT (SPAN/neosr) | CC-BY-4.0 | nomosuni | SIM (atribuição) |

### Por que a variante `_nn` (no-noise), não a com denoise

Denoise agressivo aplicado quadro a quadro é instável entre quadros — cada quadro "decide"
diferente o que é grão de filme versus detalhe real, o que produz cintilação (*flickering*)
perceptível em movimento. A variante sem denoise preserva o grão original e é mais estável no
tempo. Isso é decisão técnica, não de licença.

### Rejeitados nesta pesquisa (registrados por transparência)

- Toda a família **BasicVSR/BasicVSR++/RealBasicVSR**: Apache-2.0 declarado, mas os pesos embutem
  o **SPyNet**, cuja licença original diz *"the models are free for non-commercial and scientific
  research purpose"* — contaminação, mesmo padrão do caso GFPGAN/StyleGAN2.
- **VRT** e **RVRT**: CC-BY-NC-4.0 direto no código.
- **FlashVSR / SparkVSR**: licença Apache-2.0 limpa, mas são modelos de difusão que exigem GPU
  classe A100 — inviáveis para desktop, independente de licença.
- Modelos treinados em **Vimeo-90K**: dataset sem licença formal, catalogado como "Other", com
  declaração de coleta *"solely for research purposes ... will not be used for any commercial
  applications"* — qualquer peso que dependa dele fica INDETERMINADO.
- `2xVHS2HD`: CC-BY-SA-4.0 (share-alike, tecnicamente comercial), mas dataset "Movies and private
  films" de proveniência não auditável — descartado por prudência, não por bloqueio de licença.
- `1xFilmify4K_v2`: licença CC0 nos metadados, mas o dataset de treino é composto por frames de um
  Blu-ray comercial protegido (*Lawrence of Arabia*) processados por software proprietário
  (Topaz Gaia-HQ) — a licença do peso não sana a origem duvidosa do dataset.

### Consistência temporal (flickering) — sem modelo, só técnica e DSP

Não existe biblioteca neural de consistência temporal com licença limpa (`deep-video-prior`: sem
licença declarada; `fast_blind_video_consistency`: LICENSE contém MIT **e** CC-BY-NC-4.0
simultaneamente — ambíguo, rejeitado). A mitigação é:

1. **Tiling determinístico** — tamanho, offset e overlap de tile fixos para o vídeo inteiro, nunca
   adaptados por quadro à VRAM disponível. Maior causa de flickering em SR quadro a quadro é
   costura de tile inconsistente entre quadros. Custo zero de licença — é lógica própria.
2. **`atadenoise`** (FFmpeg, LGPL-2.1+) antes do upscale — remove ruído temporal que o modelo
   amplificaria em cintilação.
3. **`deflicker`** (FFmpeg, LGPL-2.1+) depois do upscale — corrige oscilação de luminância entre
   quadros.
4. Evitar `hqdn3d` — filtro GPL do FFmpeg; usá-lo exigiria `--enable-gpl`, contaminando o binário
   inteiro (mesma restrição documentada na seção 5).

---

## 5. FFmpeg — LGPL vs GPL

Fonte: `FFmpeg/LICENSE.md` e `ffmpeg.org/legal.html`.

> *"Most files in FFmpeg are under the GNU Lesser General Public License version 2.1 or later
> (LGPL v2.1+). … Some optional parts of FFmpeg are licensed under the GNU General Public License
> version 2 or later (GPL v2+). … None of these parts are used by default, you have to explicitly
> pass `--enable-gpl` to configure to activate them. In this case, FFmpeg's license changes to GPL v2+."*

| Build | Efeito num app comercial proprietário |
|---|---|
| **LGPL** (sem `--enable-gpl`) | ✅ Viável. Exige: link dinâmico (DLLs separadas), distribuir o fonte do FFmpeg usado, permitir substituição das DLLs, atribuição visível |
| **GPL** (`--enable-gpl`) | ❌ Contamina o app inteiro — obrigaria liberar o Astros sob GPL v2+ |
| **nonfree** (`--enable-nonfree`) | ❌ Binários legalmente não redistribuíveis |

### Estado histórico (2026-08-08) — dependência externa, não empacotada

```
ffmpeg version 9.0-full_build-www.gyan.dev
configuration: --enable-gpl --enable-version3 ... --enable-libx264 --enable-libx265 ...
```

Nesta data o FFmpeg era dependência **externa** (o código só verificava
`shutil.which('ffmpeg')`, resolvendo qualquer build presente no PATH do usuário — inclusive a
build GPL acima), então o produto não o redistribuía. Mas a ausência de qualquer FFmpeg
empacotado também significava que, numa instalação limpa (sem FFmpeg pré-instalado pelo
usuário), as funcionalidades de compressão/conversão e melhoria de vídeo/áudio simplesmente
não funcionavam.

### Empacotamento resolvido (2026-08-11) — build LGPL vendorizada, fetch-at-build-time

O app agora empacota um FFmpeg LGPL para Windows e Linux, buscado durante o build (não
comitado no git) por `interface/scripts/fetch-ffmpeg.mjs` a partir da
fonte pública **BtbN/FFmpeg-Builds** (<https://github.com/BtbN/FFmpeg-Builds>), releases
`ffmpeg-n8.1-latest-{win64,linux64}-lgpl-shared-8.1`. O script pina o nome exato do asset e
seu SHA256 (não confia em "latest" resolvido no momento do fetch) e recusa-se a usar o binário
se o hash não bater.

`electron-builder.yml` copia `resources/ffmpeg/<platform>/` para o `resources/ffmpeg/` do app
empacotado via `extraResources` (win/linux); o processo principal do Electron
(`src/main/apiProcess.ts`, `resolveBundledFfmpegDir`) detecta esse binário e passa seu diretório
ao backend Python via a variável de ambiente `ASTROS_FFMPEG_DIR`.
`api/astros_upscale/media.py` (`ffmpeg_path()`) prefere esse binário quando presente e cai
de volta para `shutil.which('ffmpeg')` (PATH do sistema) quando ausente — preservando o
comportamento anterior em modo dev ou em plataformas sem build empacotada.

**Verificação real do binário empacotado** (`ffmpeg -version` rodado diretamente no artefato
baixado pelo `fetch-ffmpeg.mjs`, Windows, 2026-08-11, hash SHA256 do zip
`b1284f218de4e0c740c63c1a13f2bd09c287a7e05bb04d8f13f24ab7a7accc46` conferido contra o
`checksums.sha256` publicado no release):

```
ffmpeg version n8.1.2-34-g9b6c8969e0-20260811 Copyright (c) 2000-2026 the FFmpeg developers
built with gcc 15.2.0 (crosstool-NG 1.28.0.23_185f348)
configuration: --prefix=/ffbuild/prefix --pkg-config-flags=--static --pkg-config=pkg-config
  --cross-prefix=x86_64-w64-mingw32- --arch=x86_64 --target-os=mingw32 --enable-version3
  --disable-debug --enable-shared --disable-static --disable-w32threads --enable-pthreads
  --enable-iconv --enable-zlib --enable-libxml2 --enable-libvmaf --enable-fontconfig
  --enable-libharfbuzz --enable-libfreetype --enable-libfribidi --enable-vulkan
  --enable-libshaderc --enable-libvorbis --disable-libxcb --disable-xlib --disable-libpulse
  --enable-gmp --enable-lzma --enable-liblcevc-dec --enable-opencl --enable-amf
  --enable-libaom --enable-libaribb24 --disable-avisynth --enable-chromaprint
  --enable-libdav1d --disable-libdavs2 --disable-libdvdread --disable-libdvdnav
  --disable-libfdk-aac --enable-ffnvcodec --enable-cuda-llvm --disable-frei0r --enable-libgme
  --enable-libkvazaar --enable-libaribcaption --enable-libass --enable-libbluray
  --enable-libjxl --enable-libmp3lame --enable-libopus --enable-libplacebo --enable-librist
  --enable-libssh --enable-libtheora --enable-libvpx --enable-libwebp --enable-libzmq
  --enable-lv2 --enable-libvpl --enable-openal --enable-liboapv --enable-libopencore-amrnb
  --enable-libopencore-amrwb --enable-libopenh264 --enable-libopenjpeg --enable-libopenmpt
  --enable-librav1e --disable-librubberband --enable-schannel --enable-sdl2
  --enable-libsnappy --enable-libsoxr --enable-libsrt --enable-libsvtav1 --enable-libtwolame
  --enable-libuavs3d --disable-libdrm --enable-vaapi --disable-libvidstab --enable-libvvenc
  --disable-whisper --disable-libx264 --disable-libx265 --disable-libxavs2 --disable-libxvid
  --enable-libzimg --enable-libzvbi ...
```

Confirmado: **sem `--enable-gpl` e sem `--enable-nonfree`** na configuration line; e
explicitamente `--disable-libx264 --disable-libx265` (os encoders GPL problemáticos da seção
anterior). `--enable-shared --disable-static` confirma o link dinâmico exigido pela LGPL — o
app distribui `ffmpeg.exe` + `avcodec-62.dll`/`avfilter-11.dll`/`avformat-62.dll`/etc. como
arquivos separados e substituíveis, não estaticamente embutidos.

O build Linux equivalente (`linux64-lgpl-shared-8.1`, hash
`9bcd549b0c1277796235b813ed593de5337c7f11228a35ea4a35c8fa1ba803fa` conferido) não pôde ser
executado nesta máquina (Windows, sem capacidade de rodar um binário ELF) para um
`ffmpeg -version` direto, então a configuration line foi extraída lendo a string embutida em
`lib/libavutil.so.60.26.102` dentro do `.tar.xz` já baixado e com hash conferido:

```
--prefix=/ffbuild/prefix ... --cross-prefix=x86_64-ffbuild-linux-gnu- --arch=x86_64
--target-os=linux --enable-version3 --disable-debug --enable-shared --disable-static
--enable-iconv --enable-zlib ... --enable-ffnvcodec --enable-cuda-llvm ...
--disable-librubberband --disable-schannel --enable-sdl2 ... --enable-libsvtav1
--enable-libtwolame --enable-libuavs3d --enable-libdrm --enable-vaapi --disable-libvidstab
--enable-libvvenc --disable-whisper --disable-libx264 --disable-libx265 --disable-libxavs2
--disable-libxvid --enable-libzimg ...
```

Mesmo resultado: **sem `--enable-gpl`, sem `--enable-nonfree`**, com `--disable-libx264
--disable-libx265` e `--enable-shared --disable-static` (link dinâmico). O binário ELF carrega
as `.so` dinamicamente via rpath `$ORIGIN`/`$ORIGIN/../lib` (verificado diretamente nas flags do
linker embutidas no executável `bin/ffmpeg` do mesmo arquivo), o que é o motivo de
`fetch-ffmpeg.mjs` colocar as `.so*` lado a lado com o binário em `resources/ffmpeg/linux/` —
mesmo layout plano usado para as DLLs do Windows.

**Nota de execução:** o ambiente desta verificação ficou sob contenção pesada de CPU/E-S durante
o teste (dezenas de processos concorrentes no host), o que impediu completar localmente o fluxo
fim-a-fim `npm run fetch:ffmpeg:linux` → `resources/ffmpeg/linux/ffmpeg` → execução do binário
(inviável de qualquer forma nesta máquina Windows). A extração seletiva do `.tar.xz`
(`fetch-ffmpeg.mjs`) e a leitura do hash/flags acima foram feitas diretamente sobre o arquivo já
baixado e com SHA256 conferido, sem depender do `tar` do sistema. O fluxo completo (download →
extração → `resources/ffmpeg/linux/ffmpeg` executável) deve ser confirmado na primeira execução
real de `npm run build:linux` em CI Linux nativo.

**Fonte disponível para reprodução:** os fontes usados por essas builds ficam publicados pelo
próprio projeto BtbN em <https://github.com/BtbN/FFmpeg-Builds> (workflow de build + pin do
commit do FFmpeg upstream). O `LICENSE.md`/`COPYING.LGPLv2.1` do FFmpeg é distribuído dentro de
cada arquivo de release do BtbN.

**Pendência: macOS.** BtbN não publica builds para macOS, e não foi encontrada uma fonte
oficial e automatizável equivalente (as builds mais conhecidas, como as de evermeet.cx,
normalmente vêm com `--enable-gpl`/libx264 habilitados). `fetch-ffmpeg.mjs` cobre apenas
`win32`/`linux`; `electron-builder.yml` não declara `extraResources` de ffmpeg para `mac`, então
o instalador macOS continua dependendo de um FFmpeg já presente no PATH do usuário (mesmo
comportamento de antes desta mudança). Qualquer build usada futuramente para macOS precisa
satisfazer o mesmo critério desta seção: LGPL (sem `--enable-gpl`/`--enable-nonfree`), com
`ffmpeg -version` verificado e registrado aqui antes de ser vendorizada.

### Filtros de áudio: nenhum é GPL

Verificação arquivo por arquivo do `libavfilter`: os únicos filtros GPL são de **vídeo**
(`vf_boxblur`, `vf_delogo`, `vf_hqdn3d`, `vf_nnedi`, `vf_spp`, `vf_vaguedenoiser`, etc.).

Toda a cadeia de áudio recomendada na seção 4 roda numa build LGPL padrão.

### Encoders de vídeo — o conflito real

A Seção 14 do briefing pede H.264, H.265/HEVC e AV1. Situação de licença:

| Encoder | Licença | Build LGPL? |
|---|---|---|
| `libx264` | GPL | ❌ Exige `--enable-gpl` |
| `libx265` | GPL | ❌ Exige `--enable-gpl` |
| `libsvtav1` (AV1) | BSD-3-Clause | ✅ |
| `librav1e` (AV1) | BSD-2-Clause | ✅ |
| `h264_nvenc`, `hevc_nvenc` | Encoder de hardware NVIDIA | ✅ |
| `h264_qsv`, `hevc_qsv` | Encoder de hardware Intel | ✅ |
| `h264_amf`, `hevc_amf` | Encoder de hardware AMD | ✅ |

**Consequência:** H.264 e H.265 por software só são viáveis com licença comercial adquirida da
x264 LLC / MulticoreWare. Por hardware (NVENC/QSV/AMF) são viáveis numa build LGPL — o que se
alinha com o Princípio VII (Hardware Adaptive) e com a Seção 14 ("selecionar automaticamente o
encoder mais adequado considerando hardware").

### T072 — Reverificação (2026-08-11)

Reexecutado `ffmpeg -version` nesta máquina de desenvolvimento:

```
ffmpeg version 9.0-full_build-www.gyan.dev
configuration: --enable-gpl --enable-version3 ... --enable-libx264 --enable-libx265 ...
```

**Estado inalterado desde 2026-08-08: a build ainda é GPL.** Confirmado também, via inspeção de
`interface/electron-builder.yml` e de `dist/win-unpacked/`, que o instalador
**não embute nenhum binário `ffmpeg`/`ffmpeg.exe` próprio** — o único `ffmpeg.dll` presente no
build do Electron é o do próprio Chromium (mídia HTML5), não o binário CLI que
`api/astros_upscale/media.py` invoca via `shutil.which('ffmpeg')`. O backend Python
continua dependendo inteiramente de um `ffmpeg` já instalado no PATH da máquina do usuário final.

Isso significa duas coisas distintas:
1. **Sob a leitura estrita da LGPL**, como nada é redistribuído hoje, não há violação de licença
   em produção — mas a checagem em `media.py::is_lgpl_build()` já avisa (não
   bloqueia) quando o `ffmpeg` do PATH reporta `--enable-gpl`/`--enable-nonfree`, para não deixar
   isso passar despercebido no dia em que o empacotamento mudar.
2. **Gap funcional real, fora do escopo de licenciamento**: sem `ffmpeg` embutido, as User
   Stories 2/3/4 (compress/convert, vídeo, áudio) só funcionam de fato numa máquina de usuário
   final que já tenha `ffmpeg` no PATH — o que não é o caso da maioria. Isso não é uma pendência
   desta tarefa (T072 pede apenas verificar a licença do binário embutido/enviado), mas é uma
   lacuna de produto real que a T072 expôs ao confirmar "nada está embutido" — registrada
   separadamente para acompanhamento (ver tarefa apontada na sessão que fez esta verificação).

**Nota separada:** o uso de H.264/H.265 pode também envolver royalties de patente (MPEG LA /
Access Advance), independentemente da licença do encoder. Isso é questão jurídica de produto,
fora do escopo desta verificação técnica.

---

## 6. Resumo executivo

### Aprovados
Real-ESRGAN (7 modelos, BSD-3) · Phhofm/Helaman (CC-BY-4.0, **com atribuição visível**) ·
audiosronnx (Apache-2.0) · RNNoise (BSD-3) · loudnorm/afftdn/anlmdn/firequalizer/acompressor
(LGPL) · deesser (MIT) · pyloudnorm (MIT) · noisereduce (MIT) · SpeechBrain + modelos
Apache-2.0 · SVT-AV1/rav1e · encoders de hardware

### Rejeitados
4x-UltraSharp · 4x-AnimeSharp · liveaction-span · **GFPGAN** · **facexlib (GPL-3.0)** ·
**toda a categoria de restauração facial** (12 modelos, via FFHQ) · denoiser (Meta) · pesos do
demucs · AudioLDM · Silero · InsightFace (pesos) · libx264/libx265 em build LGPL

### Indeterminados (= rejeitados até obter autorização)
4x_NMKD-Siax_200k · 4x_NMKD-Superscale-SP · AudioSR de haoheliu (conflito AudioLDM) ·
haoheliu/audiosr_speech (sem licença) · vocoder do voicefixer · pesos do DeepFilterNet

### Ações obrigatórias

| # | Ação | Motivo | Urgência |
|---|---|---|---|
| 1 | **Remover `facexlib`** | Importa SORT (GPL-3.0) — contaminaria o app inteiro | **Crítica** |
| 2 | **Remover GFPGAN** (`face_restore.py`, pesos, dependência) | StyleGAN2 NC + DFDNet NC + FFHQ | **Crítica** |
| 3 | Implementar realce facial determinístico (YuNet MIT + OpenCV) | Substituto aprovado da decisão | Alta |
| 4 | Renomear a feature — não prometer "recuperação facial por IA" | Honestidade sobre a capacidade real | Alta |
| 5 | Remover pesos rejeitados de `models/`: `4x-UltraSharp.pth`, `4x-AnimeSharp.pth`, `4x_NMKD-Siax_200k.pth`, `4x_NMKD-Superscale-SP_178000_G.pth` | NC confirmado / indeterminado | Alta |
| 6 | ~~Trocar build de FFmpeg para **LGPL**~~ — **feito (2026-08-11)**, ver seção 5 "Empacotamento resolvido" | Build de PATH podia ser `--enable-gpl`; agora Windows/Linux empacotam uma build LGPL verificada | Alta (bloqueava empacotamento) — macOS ainda pendente |
| 7 | Trocar codec padrão de `libx264` para hardware ou AV1 | libx264 é GPL | Alta |
| 8 | Substituir AudioSR de haoheliu por **`audiosronnx`** (Apache-2.0) | Conflito AudioLDM resolvido sem perder a capacidade | Média |
| 9 | Créditos de atribuição visíveis na UI (CC-BY-4.0 / Apache NOTICE / BSD) | Obrigação das licenças aprovadas | Média |
| 10 | Mover autoridade de licenças de `modelLicenses.ts` para o backend | Quem resolve o modelo deve aplicar a regra | Média |

### Decisões formais registradas

| Data | Decisão | Fundamento |
|---|---|---|
| 2026-08-08 | Melhorar Áudio (fala) = `audiosronnx` (Apache-2.0), demais capacidades de áudio são implementação nova | Único caminho de fala testado e limpo; demais engines de fala reprovadas por licença |
| 2026-08-08 | Substituir AudioSR de haoheliu por `audiosronnx` (Apache-2.0 código e pesos) | Mesma capacidade de fala, sem contaminação do AudioLDM |
| 2026-08-08 | Remover recuperação facial por IA; substituir por realce determinístico | Nenhum modelo licenciável existe; treinar o próprio é inviável |
| 2026-08-08 | Aceitar a assimetria do DIV2K nos pesos Real-ESRGAN | Autor concedeu BSD-3 explicitamente; questão dataset-vs-pesos não resolvida juridicamente |
| 2026-08-08 | **Melhorar Áudio (música) = SonicMaster, com risco de licença aceito conscientemente** | Único candidato com código e pesos próprios Apache-2.0; depende do VAE do Stable Audio Open, cuja licença corta uso comercial acima de US$1M de receita anual — ver seção 3-bis |
| 2026-08-08 | **Melhorar vídeo real = `2xPublic_realplksr_dysample_layernorm_real_nn`, sem ressalva** | Apache-2.0 em código e pesos, dataset 100% domínio público. Substitui o `liveaction-span` rejeitado, sem risco de licença condicional — ver seção 3-ter |

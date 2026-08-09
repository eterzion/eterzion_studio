# Phase 0 Research: Unified Media Processing

**Date**: 2026-08-08
**Purpose**: resolver as incógnitas técnicas genuínas do plano — decisões que a auditoria da Fase 0
do projeto (`docs/audit/phase0-inventory.md`) não cobriu porque são novas para esta feature, e que
os dois gates pendentes da Constitution Check (IV, VI) do `plan.md` dependem.

Cada decisão segue o formato: Decision / Rationale / Alternatives considered.

---

## R1 — Classificação automática de tipo de conteúdo em imagem (foto real vs. anime)

**Decision**: heurística de DSP puro — combinação de saturação média em HSV, densidade de bordas
(Canny + variância do Laplaciano) e proporção de blocos de cor uniforme via quantização em LAB.
Sem modelo de IA.

**Rationale**: satisfaz diretamente o Princípio VI (No AI Without Benefit) — a tarefa é
suficientemente bem servida por sinais de baixo nível, sem custo de licença, sem GPU, com latência
desprezível. É a mesma técnica usada publicamente por produtos equivalentes ("SmartEnhancer") como
alternativa explícita a deep learning para esta distinção específica. Elimina qualquer questão de
proveniência de pesos.

**Alternatives considered**:
- `deepghs/anime_real_cls` (classificador dedicado, ONNX leve) — **rejeitado**: licença OpenRAIL,
  que não atende "licença comercial explícita" (cláusulas de uso responsável não equivalentes a
  MIT/Apache/BSD). Dúvida → rejeitado, por política do Princípio IV.
- `prithivMLmods/Anime-Classification-v1.0` (SigLIP2 fine-tuned) — Apache-2.0 ponta a ponta, seria
  aprovável, mas suas classes (3D/Bangumi/Comic/Illustration) não formam um binário limpo
  "foto real vs. anime" e exigiriam mapeamento e validação adicional. Reservado como plano B se a
  heurística DSP não atingir precisão suficiente em teste interno (ver FR-096: a pessoa pode
  corrigir a detecção errada, o que reduz o custo de uma heurística imperfeita).
- Fine-tuning de ResNet-18/MobileNet a partir de pesos ImageNet do torchvision — **rejeitado**: a
  documentação oficial do torchvision declara que modelos pré-treinados *"may have their own
  licenses or terms and conditions derived from the dataset used for training"*, e o ImageNet
  original restringe a *"non-commercial research and/or educational use"*. Proveniência não limpa.

**Consequência para a spec**: FR-096 (permitir correção manual da detecção) deixa de ser apenas
boa prática de UX e passa a ser mitigação de risco de precisão de uma heurística DSP, não de um
classificador treinado.

---

## R2 — Classificação automática de tipo de conteúdo em áudio (fala vs. música)

**Decision**: `silero-vad` (MIT, ONNX, ~1-2MB) para detecção de presença de fala, complementado
por heurística DSP via `librosa` (ISC) — razão harmônico-percussiva (HPSS) e taxa de cruzamento
por zero — para o binário fala/música.

**Rationale**: `silero-vad` é distinto do `silero-models` já rejeitado no projeto por licença
CC-BY-NC — repositório e licenciamento próprios, MIT sem cláusula restritiva separada para o
comportamento do modelo. Combinado com sinais DSP de `librosa` (biblioteca sem modelo, licença
permissiva), evita depender inteiramente de um classificador treinado para uma decisão binária que
sinais espectrais simples já resolvem bem.

**Alternatives considered**:
- `webrtcvad` (MIT + BSD-3-Clause, algoritmo GMM clássico compilado) — mais leve ainda, sem pesos
  redistribuídos, mas é só detector de atividade vocal, não classificador fala/música. Mantido como
  sinal complementar possível, não como solução isolada.
- `pyAudioAnalysis` (Apache-2.0 no código) — **rejeitado para os modelos pré-treinados
  embutidos**: a proveniência de treino de `pretrainedModels/` não é documentada no repositório.
  Dúvida → rejeitado. O código em si poderia ser usado para extração de features, mas
  `librosa` cobre a mesma necessidade com licença mais simples de auditar.

---

## R3 — Métricas de qualidade para o benchmark dos perfis (FR-087 a FR-093)

**Decision**: dois níveis, com fronteira clara de distribuição.

- **Fidelidade** (guarda-corpo, FR-089): PSNR/SSIM via `scikit-image` (BSD-3-Clause) ou OpenCV
  ≥4.5 (Apache-2.0). Sem modelo, sem ambiguidade.
- **Perceptual** (critério principal, FR-088): LPIPS (BSD-2-Clause) e DISTS (MIT) — **usados
  apenas como ferramenta interna de desenvolvimento/CI, nunca embarcados no produto distribuído
  ao usuário final**.

**Rationale**: o código de LPIPS e DISTS está limpo, mas ambos carregam pesos de backbone
(AlexNet/VGG16) via torchvision, cuja documentação oficial atribui ao usuário a responsabilidade
de verificar a licença herdada do dataset de treino — e o ImageNet original é
"non-commercial research and/or educational use". Isso não foi resolvido de forma inequívoca por
nenhuma fonte consultada. Mantê-las fora do binário distribuído evita o risco: elas medem
qualidade de modelo *durante o desenvolvimento*, no ambiente do desenvolvedor, e nunca precisam
rodar na máquina do usuário. `torchmetrics` (Apache-2.0) serve como orquestrador quando usado
assim, herdando a mesma ressalva apenas nesse contexto interno.

**Alternatives considered**: usar LPIPS/DISTS também em campo, para uma futura funcionalidade de
"relatório de qualidade" no produto — descartado por este plano; se algum dia for necessário,
exigirá resolver antes a proveniência exata dos pesos `.pth` do LPIPS (não documentada pelo
próprio repositório) ou treinar backbones próprios.

**Consequência para a spec**: FR-087 a FR-093 (avaliação de qualidade dos perfis) são atividade de
desenvolvimento/benchmark, não uma capacidade do produto entregue ao usuário — consistente com a
leitura original da spec, agora explicitamente confirmada.

---

## R4 — Detecção de hardware (VRAM, GPU, encoders/decoders disponíveis)

**Decision**: `pynvml` (NVIDIA Management Library bindings) para VRAM/GPU NVIDIA quando presente;
`torch.cuda.get_device_properties().total_memory` como sinal adicional já disponível sem
dependência nova; enumeração de encoders/decoders do FFmpeg via `ffmpeg -encoders`/`-decoders`
(parsing de saída, sem biblioteca extra); RAM e CPU via `psutil` (já é dependência indireta comum
no ecossistema Python científico). Sem suporte a consulta de VRAM AMD/Intel nesta fase — registrar
como limitação conhecida, não fingir cobertura universal.

**Rationale**: é o estado real hoje (`torch.cuda.is_available()` apenas, confirmado por grep no
repositório) precisa evoluir para saber *quanto* de VRAM existe, não só *se* existe — é o que
FR-031 a FR-035 e FR-076 a FR-080 exigem. `pynvml` é o padrão de fato para isso em NVIDIA (MIT,
mantido pela própria NVIDIA), e é a maioria real do parque de GPUs de consumo. `torch.cuda`
já fornece memória total mesmo sem `pynvml`, como fallback mínimo. Sem biblioteca equivalente
madura e amplamente adotada para AMD/Intel no ecossistema Python — declarar honestamente a lacuna
(FR-034 já exige explicar limitação de hardware ao usuário) em vez de inventar uma detecção que
não existe.

**Alternatives considered**: `GPUtil` (wrapper mais antigo sobre `nvidia-smi`, menos mantido que
`pynvml` direto) — preterido por `pynvml` ser mais direto e ativamente mantido. Chamar
`nvidia-smi` via subprocess e fazer parsing de texto — mais frágil a mudanças de formato entre
versões de driver; usado apenas como fallback de último recurso se `pynvml` não estiver disponível
no ambiente (ex.: driver muito antigo).

**Verificação de licença**: `pynvml` é MIT (mantido pela NVIDIA sob o nome `nvidia-ml-py` no
PyPI). `psutil` é BSD-3-Clause. Ambas aprovadas sem ressalva.

---

## Resolução dos gates pendentes da Constitution Check

| Gate | Resultado |
|---|---|
| IV. Commercial License Only | ✅ Todas as dependências novas deste plano (silero-vad, librosa, pynvml, psutil, scikit-image/OpenCV) verificadas com licença comercial explícita. LPIPS/DISTS restritas a uso interno de CI, nunca distribuídas — ver R3. |
| VI. No AI Without Benefit | ✅ Classificação de tipo de conteúdo de imagem usa DSP puro (R1); classificação de áudio usa modelo mínimo (VAD, MIT) apenas onde DSP sozinho não bastaria, com heurística DSP complementar (R2). |

Ambos os gates fecham. Plano prossegue para Phase 1.

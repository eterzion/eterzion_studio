# Data Model — Audio Engine

Entidades da spec (`spec.md`'s Key Entities), traduzidas em tipos concretos. Campos marcados
**(HTTP)** cruzam a fronteira da API e vivem em `app/schemas.py` (Decisão 5); os demais são
internos ao `audio_engine/` e vivem como `dataclass`/`TypedDict` nos módulos correspondentes.

## AudioAnalysisReport (interno — `audio_engine/analyzer.py`)

Relatório de Análise de Áudio (spec). Produzido antes e depois de cada etapa relevante.

| Campo | Tipo | Notas |
|---|---|---|
| `integrated_lufs` | `float` | ITU-R BS.1770-4, via `pyloudnorm` |
| `true_peak_db` | `float` | dBTP |
| `rms_db` | `float` | |
| `dynamic_range_db` | `float` | pico − RMS (aprox. PLR) |
| `dc_offset` | `float` | média do sinal, deve ser ~0 |
| `stereo_correlation` | `float` | -1..1; <0 indica risco de cancelamento em mono |
| `spectral_balance` | `dict[str, float]` | energia relativa por banda (grave/médio/agudo) |
| `clipping_ratio` | `float` | proporção de amostras no teto digital |
| `phase_issues_detected` | `bool` | |
| `measured_at` | `Literal['input', 'post_dsp', 'post_ai', 'post_master']` | em qual ponto do pipeline foi medido |

## ProblemDetection (interno — `audio_engine/analyzer.py`)

Detecção de Problemas (spec). Derivada de um `AudioAnalysisReport`.

| Campo | Tipo | Notas |
|---|---|---|
| `reverb_severity` | `float` (0–1) | estimativa de cauda de reverberação excessiva |
| `clipping_severity` | `float` (0–1) | |
| `distortion_severity` | `float` (0–1) | |
| `tonal_imbalance_severity` | `float` (0–1) | desvio do balanço espectral esperado |
| `stereo_imbalance_severity` | `float` (0–1) | |
| `noise_severity` | `float` (0–1) | ruído de fundo — sempre tratado por DSP (FR-003), nunca sozinho justifica IA |
| `hum_60hz_detected` | `bool` | sempre tratado por notch DSP (FR-003) |
| `requires_ai_restoration` | `bool` | `True` só quando alguma severidade "complexa" (reverb/clipping/distorção/tonal/estéreo) ultrapassa o limiar configurado — implementa FR-002/FR-004 |
| `dominant_problems` | `list[str]` | ordenado por severidade — insumo direto para a geração de prompt (FR-005) |

## RestorationJob (parcialmente HTTP)

Job de Masterização/Restauração (spec). É uma extensão do job de áudio já existente
(`content_type='music'`, `operation='enhance'`), não uma entidade nova de nível superior.

| Campo | Tipo | Onde vive | Notas |
|---|---|---|---|
| `audio_mode` **(HTTP)** | `Literal['enhance','auto_master','restore','restore_master'] \| None` | `schemas.LocalJobRequest` (novo campo opcional) | default `None` → equivalente a `'enhance'`, comportamento atual preservado (Decisão 2) |
| `ai_strength` **(HTTP)** | `int \| None` (0–100) | `schemas.LocalJobRequest` (novo campo opcional) | default `50` quando `audio_mode != 'enhance'` e a IA é acionada; ignorado quando `requires_ai_restoration=False` |
| `analysis_before` | `AudioAnalysisReport` | `audio_engine/mastering.py` (estado interno do job) | medido em `measured_at='input'` |
| `analysis_after_ai` | `AudioAnalysisReport \| None` | idem | só existe se a IA rodou |
| `audio_analysis` | `AudioAnalysisReport` **(HTTP, resumido)** | `schemas.JobStatus` (campo novo, resumo) | exposto ao cliente para permitir UI de métricas, sem os campos puramente internos |
| `quality_verdict` | `QualityVerdict \| None` | idem | só existe se a IA rodou |
| `stages_output_paths` | `dict[Literal['original','restored','mastered'], str]` | `audio_engine/mastering.py` | suporta comparação A/B (spec) — caminhos locais temporários, não necessariamente todos expostos via HTTP |

**Mapeamento de `AI Strength` → estratégia** (FR-013 — nunca um multiplicador linear):

| Faixa | Rótulo | Efeito na estratégia |
|---|---|---|
| 0 | Nenhum | `requires_ai_restoration` forçado a `False`, mesmo que a análise indique necessidade — só DSP |
| 1–25 | Conservador | IA só acionada para severidade muito alta (limiar elevado); número de passos de inferência reduzido; correção DSP pós-IA mais agressiva para "puxar de volta" ao original |
| 26–50 | Moderado | limiar padrão de acionamento; parâmetros de inferência padrão |
| 51–75 | Forte | limiar de acionamento reduzido (aciona a IA com mais frequência); mais passos de inferência |
| 76–100 | Máximo | limiar mínimo de acionamento; máximo de passos de inferência permitido pela configuração |

## QualityVerdict (parcialmente HTTP)

Veredito de Qualidade (spec) — saída do Quality Guard (`audio_engine/quality.py`).

| Campo | Tipo | Notas |
|---|---|---|
| `outcome` **(HTTP)** | `Literal['accepted','reduced','rejected']` | |
| `reasons` **(HTTP)** | `list[str]` | motivo objetivo por métrica que causou `reduced`/`rejected` (ex. `"true_peak_db regrediu de -1.2 para 0.4"`) |
| `metrics_before` | `AudioAnalysisReport` | referência interna completa |
| `metrics_after` | `AudioAnalysisReport` | referência interna completa |
| `regression_flags` | `dict[str, bool]` | por métrica, se houve regressão além do limiar tolerado |

## AudioRestorationProvider (interno — `audio_engine/ai_provider.py`)

Não é dado persistido — é o contrato que qualquer provider de IA implementa (Princípio XII).

```python
class AudioRestorationProvider(Protocol):
    def is_available(self) -> bool: ...
    def initialize(self) -> None: ...
    def restore(self, input_path: str, instruction: str, strength: int) -> str: ...  # -> output_path
    def restore_full_song(self, input_path: str, instruction: str, strength: int) -> str: ...
    def shutdown(self) -> None: ...
```

`SonicMasterProvider` é a única implementação concreta desta feature (spec Assumptions). O
`is_available()` cobre: dependências do venv isolado presentes, checkpoint acessível, VAE
autenticável, GPU/CPU viável — usado pelo fallback (FR-020) antes de qualquer tentativa de
`initialize()`.

## Validação e regras derivadas da spec

- `ai_strength` só é significativo quando `audio_mode` aciona IA condicionalmente (`auto_master`,
  `restore`, `restore_master`) — em `audio_mode='enhance'` (ou omitido) é ignorado, preservando o
  comportamento atual exatamente (Decisão 2).
- `audio_analysis`/`quality_verdict` só aparecem no status do job quando `audio_mode` != `'enhance'`
  — jobs no modo atual (`enhance`) não mudam de forma no payload de resposta, só ganham campos
  novos quando o novo comportamento é explicitamente pedido.
- Um `QualityVerdict.outcome == 'rejected'` implica que `stages_output_paths['mastered']` (ou
  `'restored'`, dependendo do modo) é derivado de `analysis_before`'s trecho + DSP corretivo,
  nunca da saída direta do provider de IA — aplica FR-008 no nível de dado, não só de fluxo.

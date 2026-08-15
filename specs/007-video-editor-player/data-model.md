# Phase 1 — Data Model: Área de Edição de Vídeo com Player Customizado

**Feature**: `007-video-editor-player` | **Date**: 2026-08-14 | **Plan**: [plan.md](./plan.md)

Entidades derivadas das *Key Entities* da [spec.md](./spec.md), com campos, faixas e transições. As
faixas aqui são normativas: são elas que os schemas Pydantic validam (FR-026) e o que o shader de
preview consome (Decisão 1).

---

## MediaHandle

O identificador que substitui o caminho de arquivo nas rotas novas (FR-028, FR-028a, Decisão 7).

| Campo | Tipo | Regra |
|-------|------|-------|
| `handle_id` | string | Opaco, emitido pelo backend. Nunca derivado do caminho de forma reversível. |
| `display_name` | string | Nome do arquivo, apenas para exibição. Higienizado antes de participar de qualquer caminho. |
| `content_key` | string | Chave de conteúdo (Decisão 4). Muda quando o arquivo muda. |
| `duration_seconds` | float | De ffprobe. |
| `width`, `height` | int | De ffprobe. |
| `frame_rate` | float \| null | `null` quando o arquivo é VFR. |
| `frame_rate_is_variable` | bool | Dispara o FR-012: número de quadro deixa de ser exibido como exato. |
| `has_audio` | bool | Dispara o FR-009: controle de áudio não é oferecido sem trilha. |
| `size_bytes` | int | Entra na verificação de tetos. |

**Invariantes**

- O caminho real nunca sai do backend, em nenhuma resposta.
- Um handle cujo `content_key` mudou é considerado obsoleto: artefatos derivados dele são
  descartados (FR-017).
- O arquivo apontado por um handle nunca é escrito. É lido, e nada mais (FR-019).

---

## VideoEditSet

O estado das seis famílias de operação para um vídeo (FR-013). Vive na sessão (Assumptions).

```text
VideoEditSet
├── adjustments : Adjustments      — FR-013a
├── effects     : Effects          — FR-013b
├── transform   : Transform        — FR-013c
├── trim        : TrimRange | null — FR-013d
└── audio       : AudioEdit        — FR-013e
```

**Cinco campos para seis famílias, e não é erro**: o FR-013 lista seis, mas a sexta — exportação —
é a operação que consome este conjunto, não um estado dentro dele. `VideoEditSet` guarda o que a
pessoa configurou; `ExportRequest` é o que faz aquilo virar arquivo.

**Estado neutro**: todos os campos nos valores marcados como neutros abaixo, `trim` em `null`.
`reset()` devolve a este estado — e devolve **as cinco famílias**, não só `adjustments`, que é o que
o FR-004 exige.

### Adjustments (FR-013a — "ajustes de imagem")

Esta família se chama *ajustes de imagem*. *Edições* é o conjunto das cinco. A spec não usa os dois
termos como sinônimos, e este documento também não.

Faixas espelham o filtro `eq` do FFmpeg, que é a fonte da verdade (Decisão 1).

| Campo | Faixa | Neutro | Correspondência no `eq` |
|-------|-------|--------|--------------------------|
| `brightness` | −1.0 … 1.0 | 0.0 | `brightness` (aditivo) |
| `contrast` | 0.0 … 4.0 | 1.0 | `contrast` |
| `saturation` | 0.0 … 3.0 | 1.0 | `saturation` |
| `gamma` | 0.1 … 10.0 | 1.0 | `gamma` |
| `hue_degrees` | −180 … 180 | 0 | filtro `hue` |
| `sharpness` | 0.0 … 2.0 | 0.0 | `unsharp` |

`brightness` ser aditivo é exatamente o motivo de o preview não usar filtro CSS — ver Decisão 1.

### Effects

Cada efeito tem estado ligado/desligado e intensidade. Todos caem no preview **sob demanda**
(Decisão 2), e portanto disparam o aviso do FR-015 enquanto o vídeo está em movimento.

| Campo | Faixa | Neutro |
|-------|-------|--------|
| `denoise_enabled` | bool | `false` |
| `denoise_strength` | 0 … 100 | 45 |
| `blur_enabled` | bool | `false` |
| `blur_strength` | 0 … 100 | 0 |
| `grain_enabled` | bool | `false` |
| `grain_strength` | 0 … 100 | 0 |

### Transform

| Campo | Faixa | Neutro | Nota |
|-------|-------|--------|------|
| `crop` | `{x, y, width, height}` \| null | `null` | Em pixels da origem. Deve caber inteiramente dentro do quadro. |
| `rotation_degrees` | 0 / 90 / 180 / 270 | 0 | Rotação livre fora do escopo. |
| `flip_horizontal` | bool | `false` | |
| `flip_vertical` | bool | `false` | |
| `output_width`, `output_height` | ≥ 16, ≤ teto | dimensão da origem | Arredondados para número par: encoders rejeitam dimensão ímpar em `yuv420p`, e `optimize.py` já trata isso com `even()`. |

**Ordem de aplicação** — normativa, porque o resultado depende dela e o preview precisa concordar
com a exportação: `crop → rotation → flip → scale`.

### TrimRange

| Campo | Regra |
|-------|-------|
| `start_seconds` | ≥ 0 |
| `end_seconds` | > `start_seconds`, ≤ duração da origem |

A duração resultante (`end − start`) é o que entra na verificação de tetos, não a duração do
arquivo: cortar um trecho de 30 s de um vídeo de 3 h é um trabalho de 30 s.

### AudioEdit

| Campo | Faixa | Neutro |
|-------|-------|--------|
| `mode` | `keep` / `mute` / `remove` | `keep` |
| `volume` | 0.0 … 2.0 | 1.0 |

`mute` mantém a trilha em silêncio; `remove` não escreve trilha de áudio no resultado. Quando
`has_audio` é falso, este bloco é inaplicável e a interface não o oferece (FR-009).

---

## ExportRequest

O que o cliente envia para exportar. **Não contém** nome de codec, encoder, preset, CRF, formato de
pixel ou caminho — por construção (Decisão 5, FR-018, FR-026).

| Campo | Tipo | Regra |
|-------|------|-------|
| `handle_id` | string | O vídeo de origem. |
| `edits` | VideoEditSet | O que aplicar. |
| `container` | `mp4` / `mkv` / `webm` / `mov` | Allowlist fechada. |
| `profile` | `fast` / `balanced` / `quality` | Intenção; resolve encoder e preset no backend. |
| `output_directory` | string \| null | `null` = pasta do arquivo de origem. |
| `output_filename` | string \| null | Higienizado. `null` = nome derivado da origem. |
| `conflict` | `rename` / `overwrite` | Padrão `rename`. `overwrite` exige instrução explícita por operação (FR-020). |

---

## VideoEditExport

O job. Reaproveita o ciclo de vida de `jobs.py` (FR-021), acrescentando o que é próprio da edição.

### Transições de estado

```text
                    ┌──────────────────────────────────────┐
                    │                                      ▼
created ──▶ validating ──▶ queued ──▶ processing ──▶ done
                 │                        │
                 │                        ├──▶ cancelled
                 ▼                        │
              refused                     └──▶ failed
```

| Estado | Significado | Garantias ao sair |
|--------|-------------|-------------------|
| `validating` | Tetos (Decisão 6), piso de máquina (`check_capacity`), disponibilidade de encoder (Decisão 5) | Nada foi escrito ainda. |
| `refused` | Falhou em alguma verificação acima | Nomeia o fator limitante (FR-025). Nenhum arquivo criado. |
| `processing` | FFmpeg em execução | Progresso observável. |
| `done` | Concluído | Arquivo novo existe; origem intacta; temporários removidos. |
| `cancelled` | Interrompido pela pessoa | Nenhum arquivo parcial no destino; temporários removidos (FR-022, FR-023). |
| `failed` | Erro durante o processamento | Idem `cancelled`, mais a razão da falha. |

**Invariante que vale para os três estados terminais**: temporários removidos e origem intacta. É
uma responsabilidade nomeada do `VideoEditExport`, num único ponto de saída, e não um cuidado
espalhado por cada ramo de erro — foi assim que o FR-022 virou algo verificável.

---

## TimelineThumbnails

Artefato derivado, descartável (FR-007a, FR-017).

| Campo | Regra |
|-------|-------|
| `handle_id` | O vídeo de origem. |
| `content_key` | Chave de conteúdo no momento da geração. |
| `interval_seconds` | Espaçamento entre miniaturas, derivado da duração. |
| `sprite_path` | Caminho interno, em armazenamento da API. Não sai em resposta. |

**Invariantes**

- Gravado em armazenamento que a API controla, nunca ao lado do arquivo de origem (FR-016).
- Descartado quando `content_key` diverge do atual (FR-017).
- Nunca apresentado como resultado de operação.

---

## PreviewFrame

O preview sob demanda do nível 2 (Decisão 2).

| Campo | Regra |
|-------|-------|
| `handle_id` | O vídeo de origem. |
| `time_seconds` | Posição do quadro. |
| `edits` | O conjunto aplicado. |
| `before`, `after` | Imagens codificadas, entregues na resposta. |

Reduzido em resolução, como o preview de imagem já faz. Nunca é o resultado da operação (FR-016).

---

## Vocabulário permitido (server-side)

Não é entidade de dados, é configuração — mas é normativa e por isso está aqui.

| Container | Encoders de vídeo permitidos (em ordem de preferência) | Áudio |
|-----------|--------------------------------------------------------|-------|
| `mp4` | `h264_nvenc`, `h264_qsv`, `h264_amf` | `aac` |
| `mov` | `h264_nvenc`, `h264_qsv`, `h264_amf` | `aac` |
| `mkv` | `h264_nvenc`, `h264_qsv`, `h264_amf`, `libvpx-vp9` | `libopus`, `flac` |
| `webm` | `libvpx-vp9`, `libaom-av1` | `libopus` |

**`libx264` e `libx265` não estão na lista, em nenhum container.** São GPL, e a seção de
Licenciamento da constituição proíbe empacotá-los. A ausência é a razão de ser da lista, não um
esquecimento.

"Permitido" não é "presente": antes de iniciar, o backend confirma que o encoder existe neste
ambiente e cai para a próxima opção do mesmo container; se nenhuma existe, recusa antes de
processar (Decisão 5, FR-027).

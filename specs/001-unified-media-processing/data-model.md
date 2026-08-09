# Phase 1 Data Model: Unified Media Processing

**Date**: 2026-08-08
**Source**: entidades da spec (`spec.md` → Key Entities), refinadas com os campos que a
especificação torna exigíveis via FR-* e SC-*.

Não é um schema de banco de dados — a maior parte do sistema é *in-memory* (job store) ou arquivo
local, consistente com o estado real do `job_manager.py` hoje. As entidades marcadas
**(persistida)** são as únicas que sobrevivem a um restart do processo.

---

## MediaRequest

O que a pessoa pediu, antes de qualquer resolução interna.

| Campo | Tipo | Regras |
|---|---|---|
| `media_type` | enum: `image` \| `video` \| `audio` | Obrigatório |
| `operation` | enum: `enhance` \| `compress` \| `convert` | Obrigatório |
| `scale` | enum: `2x` \| `4x` \| null | Obrigatório quando `operation=enhance` e `media_type∈{image,video}`; ausente nas demais combinações (FR-005) |
| `profile` | enum: `fast` \| `balanced` \| `quality` \| null | Presente apenas quando a operação/mídia tiver perfis reais (FR-004/FR-005); default `fast` (FR-008) quando aplicável e omitido |
| `content_type_override` | enum \| null | Preenchido só quando a pessoa corrige a detecção automática (FR-096) |
| `input_path` | string (caminho local) | Nunca uma URL remota — processamento é local (FR-070) |
| `output_target` | objeto: formato, diretório, nome, política de conflito | — |
| `secondary_elements_ack` | boolean | Confirmação explícita quando há aviso de elementos que serão perdidos (FR-082); ausente se não houver nada a perder (FR-085) |

**Nunca contém**: `model`, `engine`, `checkpoint_id` — o contrato aceita intenção, não
implementação (Constitution, Princípio V; FR-011).

**Validação**: rejeitada antes de virar Job se a combinação `media_type`/`operation`/`content_type`
não tiver implementação aprovada (FR-098) — nesse caso nem chega a ser instanciada como Job, o
`ContentTypeCapability` (ver abaixo) é consultado primeiro.

---

## Job (persistida em memória durante a execução; resultado persiste em disco)

Uma `MediaRequest` em execução ou concluída.

| Campo | Tipo | Regras |
|---|---|---|
| `id` | string | — |
| `status` | enum: `pending` \| `queued` \| `processing` \| `done` \| `error` \| `cancelled` | Generalização do `JobStatusValue` já existente em `schemas.py`, hoje só usado para imagem |
| `media_type`, `operation` | herdados da `MediaRequest` | — |
| `content_type_detected` | enum | Resultado de R1/R2 (research.md), ou o valor de `content_type_override` |
| `progress` | int 0–100 \| null | Presente quando estimável (FR-037); vídeo e áudio longos podem não ter estimativa precisa no início |
| `queue_position` | int \| null | Só relevante em `queued` |
| `error_category` | enum: `out_of_memory` \| `corrupted_input` \| `model_failure` \| `disk_full` \| `hardware_insufficient` \| `license_invalid` | Estende o enum já existente (`out_of_memory`, `corrupted_input`, `model_failure`, `disk_full`) com as duas categorias novas que esta feature introduz |
| `error_message_user` | string | Linguagem compreensível, nunca stack trace (FR-039) |
| `capacity_check` | objeto: `fits`, `estimated_duration`, `limiting_resource` | Resultado do FR-076 a FR-080, calculado antes de `processing` |
| `result_path` | string \| null | — |
| `created_at`, `started_at`, `finished_at` | timestamp | — |

**Transições de estado**: mesma máquina de estados que `job_manager.py` já implementa hoje para
imagem — generalizada para as três mídias, não redesenhada.

---

## Profile

Não é uma entidade persistida — é uma referência a três valores fixos.

| Valor | Prioridade | Fonte da diferenciação |
|---|---|---|
| `fast` | Velocidade | Parâmetro de execução (menor divisão de trabalho, menor precisão de cálculo aceitável) |
| `balanced` | Velocidade + qualidade | Parâmetro intermediário |
| `quality` | Qualidade | Mais passes/parâmetro mais caro, nunca troca de modelo (FR-004) |

Cada tripla (`content_type`, `operation`, `profile`) resolve para exatamente um conjunto de
parâmetros de execução sobre a **mesma** `ContentTypeImplementation` — nunca para uma
implementação diferente (FR-095).

---

## HardwareCapability

Recalculada a cada início de sessão da API, não persistida entre execuções.

| Campo | Tipo | Fonte |
|---|---|---|
| `cpu_cores` | int | `psutil` |
| `ram_total_mb`, `ram_available_mb` | int | `psutil` — disponível, não só total (FR-080) |
| `gpu_present` | boolean | `torch.cuda.is_available()` (já existe) |
| `gpu_vendor` | enum: `nvidia` \| `unknown` | `pynvml` presente ou não |
| `vram_total_mb`, `vram_available_mb` | int \| null | `pynvml` quando NVIDIA; `null` com `gpu_vendor=unknown` caso contrário — limitação registrada (research.md R4), nunca inventada |
| `ffmpeg_encoders`, `ffmpeg_decoders` | lista de strings | Parsing de `ffmpeg -encoders`/`-decoders` |

**Uso**: entrada do `profile_resolver.py` (novo) e do cálculo de capacidade máxima (FR-076 a
FR-080). Nunca exposta ao usuário como número técnico bruto — apenas como "cabe" / "não cabe" /
"vai demorar aproximadamente X".

---

## ContentTypeImplementation

Não é uma entidade de runtime — é o registro interno (sucessor de `MODELS` em `core.py`) que
mapeia tipo de conteúdo → implementação única.

| Campo | Tipo | Regras |
|---|---|---|
| `content_type` | enum: `photo` \| `anime_image` \| `real_video` \| `anime_video` \| `speech` \| `music` | Um por linha — no máximo 6 entradas nesta versão (FR-095) |
| `operation` | enum: `enhance` \| `compress` \| `convert` | — |
| `engine_ref` | string interna | **Nunca serializada para fora da camada de resolução** — é o que FR-009 proíbe expor |
| `license_status` | enum: `approved` \| `approved_conditional` | `approved_conditional` só para o caso do SonicMaster (FR-099/FR-100) — todo o resto é `approved` |
| `license_condition` | string \| null | Preenchido apenas quando `license_status=approved_conditional`; texto do gatilho (ex.: limite de receita) |

**Correspondência com `docs/models/MODEL_LICENSES.md`**: cada linha desta tabela tem um par
correspondente no documento de licenças, que é a fonte de verdade jurídica; este modelo é a
projeção técnica dela.

---

## Component (o que a tela de FR-063 a FR-069 lista)

| Campo | Tipo | Apresentação padrão | Visão de detalhe (FR-065) |
|---|---|---|---|
| `capability_label` | string | "Melhoria de imagem — Qualidade" | — |
| `size_mb` | int | Visível | Visível |
| `install_state` | enum: `not_installed` \| `installing` \| `installed` \| `update_available` | Visível | Visível |
| `technical_name`, `version`, `provenance`, `license` | string | **Oculto** (FR-009/FR-063) | Visível, opt-in (FR-065/FR-066) |

**Nunca oferece seleção** — apenas instalar/atualizar/remover (FR-064).

---

## License (installation-side; persistida no `astros_licensing_service`, SQLite já existente)

Reaproveita o schema já implementado (`licenses`, `installations`, `authorizations` — ver
`docs/audit/phase0-inventory.md` seção 2.10). Nenhum campo novo é necessário para atender FR-051 a
FR-062 — o trabalho aqui é **ativar** o que existe, não modelar de novo.

| Estado observável pela pessoa (não é o schema interno) | Origem |
|---|---|
| Ativa, com N de M instalações usadas | `installations` count vs. `activation_limit` |
| Offline, dentro da tolerância | `installations.last_seen_at` + janela de 30 dias (Assumption) |
| Offline, perto do limite | mesmo campo, avisado a partir do dia 23 (FR-057) |
| Bloqueada (revogada/reembolsada) | `licenses.status` |

---

## Relacionamentos

```text
MediaRequest ──1:1──> Job (na criação)
Job ──N:1──> ContentTypeImplementation (resolvido, nunca escolhido pela pessoa)
Job ──N:1──> HardwareCapability (snapshot no momento da resolução)
ContentTypeImplementation ──1:1──> registro em MODEL_LICENSES.md (fonte jurídica)
Component ──N:1──> ContentTypeImplementation (o componente instalável É a implementação)
License (serviço remoto) ──1:N──> Installation ──1:1──> esta instância do produto
```

# Phase 1 — API Contracts: Área de Edição de Vídeo com Player Customizado

**Feature**: `007-video-editor-player` | **Date**: 2026-08-14 | **Plan**: [plan.md](../plan.md)

Contratos HTTP e WebSocket das rotas novas. Formas de dados detalhadas em
[data-model.md](../data-model.md).

**Duas propriedades valem para todas as rotas abaixo, e são o que o SC-007 mede:**

1. **Nenhuma aceita caminho de arquivo.** Media é referenciada por `handle_id` (FR-028, Decisão 7).
2. **Nenhuma aceita nome de codec, encoder, preset, CRF ou formato de pixel.** O cliente envia
   container e perfil; o resto é resolvido no backend (FR-018, FR-026, Decisão 5).

Os schemas usam `extra='forbid'`, como `MediaRequest` já faz — um campo desconhecido é erro 422, não
chave silenciosamente ignorada. É o que impede um `codec` ou um `input_path` de entrar por
descuido.

---

## `POST /media/handles`

Registra um arquivo e devolve seu identificador. Chamada pelo processo Electron logo após o diálogo
nativo devolver o caminho.

**Request**

```json
{ "path": "C:\\Users\\...\\entrevista.mp4" }
```

Esta é a **única** rota que aceita caminho, e existe justamente para que nenhuma outra precise.

Ela opera sob a exceção delimitada do Princípio XIII, acrescentada na constituição **v3.0.0** depois
que a análise desta feature encontrou a contradição: o registro de identificadores existia para
cumprir o XIII e sua própria porta de entrada o violava. A exceção vale enquanto as quatro condições
valerem, e todas são obrigações desta rota:

1. O caminho vem do **diálogo nativo do sistema**, acionado pelo processo principal do Electron.
   Caminho digitado, colado ou composto pelo renderer não é aceito.
2. A rota valida antes de qualquer outra coisa — existe, é arquivo, é vídeo legível — e **nunca
   devolve o caminho** em resposta alguma.
3. **Nenhuma outra rota aceita caminho.** Se uma segunda parecer precisar, a resposta é outro
   identificador, não uma segunda exceção.
4. O identificador **não é codificação reversível** do caminho.

`POST /jobs/local`, do fluxo em lote existente, **não** é coberto por esta exceção: não é rota de
registro e não devolve identificador. Continua fora, e migra em trabalho próprio.

**Response `201`**

```json
{
  "handle_id": "vh_9f3c…",
  "display_name": "entrevista.mp4",
  "duration_seconds": 754.32,
  "width": 1920,
  "height": 1080,
  "frame_rate": 29.97,
  "frame_rate_is_variable": false,
  "has_audio": true,
  "size_bytes": 1284730112
}
```

O caminho não aparece na resposta, nem aqui nem em nenhuma outra.

**Erros**

| Código | Quando |
|--------|--------|
| `404` | Arquivo não existe |
| `415` | Não é um vídeo legível |
| `422` | Corpo inválido |

---

## `GET /media/handles/{handle_id}`

Devolve os mesmos metadados. Usada para revalidar: se o `content_key` mudou, a resposta traz os
dados atuais e o cliente descarta o que tiver em cache do arquivo antigo (FR-017).

**Erros**: `404` quando o handle não existe ou o arquivo desapareceu.

---

## `GET /media/handles/{handle_id}/thumbnails`

Sprite de miniaturas da linha de tempo (FR-007a).

**Query**: `interval_seconds` (opcional; o backend escolhe pela duração quando ausente).

**Response `200`**: a imagem do sprite, mais os cabeçalhos que descrevem a grade
(`X-Astros-Thumb-Count`, `X-Astros-Thumb-Interval`, `X-Astros-Thumb-Size`).

Gerado sob demanda e mantido em cache com chave de conteúdo. Fica em armazenamento da API — nunca ao
lado do arquivo de origem (FR-016).

---

## `POST /media/handles/{handle_id}/preview-frame`

Preview sob demanda do nível 2 — os efeitos que o shader do renderer não reproduz fielmente
(Decisão 2).

**Request**

```json
{
  "time_seconds": 42.5,
  "edits": { "adjustments": {}, "effects": { "denoise_enabled": true, "denoise_strength": 60 } }
}
```

**Response `200`**

```json
{ "before": "<imagem codificada>", "after": "<imagem codificada>", "width": 854, "height": 480 }
```

Mesma forma que a rota de preview de redução de ruído já usa para imagem — reaproveitada de
propósito (Princípio II).

---

## `GET /video/export-options`

O que este ambiente realmente oferece. É a rota que faz o FR-027 acontecer **antes** de a pessoa
escolher, em vez de depois de a exportação falhar.

**Response `200`**

```json
{
  "containers": [
    { "value": "mp4",  "available": true,  "unavailable_reason": null },
    { "value": "webm", "available": true,  "unavailable_reason": null },
    { "value": "mkv",  "available": true,  "unavailable_reason": null },
    { "value": "mov",  "available": false, "unavailable_reason": "no_encoder_available" }
  ],
  "profiles": ["fast", "balanced", "quality"],
  "ceilings": {
    "max_duration_seconds": 7200,
    "max_width": 3840,
    "max_height": 2160,
    "max_frame_rate": 120,
    "max_frame_count": 500000,
    "max_size_bytes": 34359738368
  }
}
```

`available` vem da verificação real de quais encoders o binário FFmpeg expõe, não da allowlist
(Decisão 5). `unavailable_reason` é uma chave, não uma frase: quem traduz é a interface (FR-030).

Nenhum nome de encoder aparece na resposta — o container está indisponível, e o motivo é
categórico. O Princípio V vale aqui como em qualquer superfície padrão.

---

## `POST /video/edit-jobs`

Cria a exportação. Corpo conforme `ExportRequest` em [data-model.md](../data-model.md).

```json
{
  "handle_id": "vh_9f3c…",
  "edits": { "...": "VideoEditSet" },
  "container": "mp4",
  "profile": "balanced",
  "output_directory": null,
  "output_filename": null,
  "conflict": "rename"
}
```

**Response `202`**

```json
{ "job_id": "…", "status": "queued", "estimated_duration_seconds": 128.4 }
```

**Response `422` — recusado antes de começar**

É o corpo que o FR-025 exige: nomeia o fator limitante, e chega antes de qualquer processamento.

```json
{
  "detail": {
    "reason": "ceiling_exceeded",
    "limiting_factor": "duration",
    "limit": 7200,
    "actual": 9840
  }
}
```

| `reason` | Significado |
|----------|-------------|
| `ceiling_exceeded` | Excede um teto declarado; `limiting_factor` diz qual |
| `hardware_insufficient` | Não passa no piso de máquina; `limiting_resource` diz qual |
| `encoder_unavailable` | Nenhum encoder permitido para o container existe neste ambiente |
| `source_changed` | O arquivo mudou desde o registro do handle |

Os quatro chegam **antes** de o processamento começar. Uma recusa depois de minutos de trabalho é
defeito, não comportamento (FR-025).

---

## Progresso, cancelamento e resultado

Sem rota nova: a exportação é um job, e usa o que já existe (FR-021).

| Operação | Rota existente |
|----------|----------------|
| Consultar | `GET /jobs/{job_id}` |
| Cancelar | `DELETE /jobs/{job_id}` |
| Progresso | `WS /ws/jobs/{job_id}` |

A assimetria é proposital: o job nasce em `POST /video/edit-jobs`, que conhece edições e tetos, mas
vive no mesmo registro de jobs de todo o resto. Progresso e cancelamento são os que já existem, e é
isso que o FR-021 pede — reaproveitar, não construir um segundo mecanismo ao lado.

O cancelamento por `DELETE /jobs/{job_id}` garante, para esta feature, que nenhum arquivo parcial
fica no destino e nenhum temporário fica para trás (FR-022, FR-023).

---

## O que este contrato deliberadamente não tem

Vale registrar, porque a ausência é o requisito:

- **Nenhum campo `input_path`, `output_path` ou equivalente** nas rotas de edição. Só
  `POST /media/handles` conhece caminho, e ela existe para que as outras não precisem.
- **Nenhum campo `codec`, `encoder`, `preset`, `crf`, `pix_fmt`, `bitrate`.** Só `container` e
  `profile`.
- **Nenhum nome de encoder em resposta alguma**, nem em mensagem de erro.
- **Nenhum campo de sobrescrita implícita.** `conflict` tem padrão `rename`; `overwrite` é
  instrução explícita por operação (FR-020, Princípio XV).

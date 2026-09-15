# Phase 1 — Contrato de API: Central de Compressão

**Feature**: `008-compression-centre` · **Data**: 2026-08-21

Prefixo: `/compression`. Registrado em `main.py` ao lado de `/image` e `/video`.

Três propriedades valem em **todas** as rotas abaixo, e existem testes para cada uma:

1. **Mídia é referenciada por identificador.** Nenhuma rota daqui aceita caminho de sistema de
   arquivos. A exceção do Princípio XIII (registro pelo diálogo nativo) já é servida por
   `POST /media/handles`, que a Central reusa.
2. **Nada é oferecido sem sonda.** Toda lista de codec, formato ou container passa por verificação
   funcional do ambiente antes de sair daqui.
3. **O modo Básico não vê vocabulário técnico.** Um pedido que não declara `advanced` não recebe
   nome de codec ou encoder em resposta alguma (SC-006).

---

## `GET /compression/capabilities`

O que esta máquina consegue, por tipo de mídia. É a rota que torna FR-043 e FR-044 possíveis.

```json
{
  "image": {
    "formats": [
      { "value": "webp", "available": true, "unavailable_reason": null, "requires_hardware": false },
      { "value": "avif", "available": true, "unavailable_reason": null, "requires_hardware": false }
    ]
  },
  "video": {
    "containers": [
      { "value": "mp4", "available": false, "unavailable_reason": "no_encoder_available", "requires_hardware": true },
      { "value": "webm", "available": true, "unavailable_reason": null, "requires_hardware": false }
    ],
    "video_codecs": [
      { "value": "h264", "available": false, "unavailable_reason": "requires_hardware_encoder", "requires_hardware": true },
      { "value": "av1",  "available": true,  "unavailable_reason": null, "requires_hardware": false }
    ],
    "audio_codecs": [ { "value": "opus", "available": true, "unavailable_reason": null, "requires_hardware": false } ],
    "compatibility": { "webm": { "video": ["vp9", "av1"], "audio": ["opus"] } },
    "hardware": { "available": false, "reason": "no_working_hardware_encoder" }
  },
  "audio": { "formats": [ ... ], "codecs": [ ... ] },
  "animation": { "formats": [ ... ] }
}
```

`unavailable_reason` é **chave**, nunca frase e nunca nome de biblioteca — a interface traduz
(Princípio XIV) e o Princípio V mantém `nvenc`, `libx264` e afins fora do fio.

`requires_hardware: true` com `available: false` é o que permite dizer "H.264 precisa de um
encoder de hardware que esta máquina não tem" sem nomear nenhum encoder.

`hardware.available` responde ao §41/§42 no mesmo registro: se há aceleração utilizável, sem
prometer marca.

---

## `GET /compression/presets`

```json
{
  "presets": [
    { "id": "builtin.balanced", "name_key": "compression.preset.balanced",
      "media_kind": "image", "origin": "builtin", "settings": { ... } },
    { "id": "user.a1b2c3", "name": "Discord 8 MB",
      "media_kind": "video", "origin": "user", "settings": { ... } }
  ]
}
```

`name_key` para internos (traduzível), `name` literal para os do usuário (a pessoa escolheu aquela
palavra e ela não se traduz).

### `POST /compression/presets` · `PATCH /{id}` · `DELETE /{id}`

Só `origin: "user"` aceita escrita. Tentar alterar um `builtin` ou `platform` responde **409** com
`reason: "readonly_preset"` — em vez de aceitar e ignorar.

Um preset cujo `settings` não corresponde ao seu `media_kind` é **422**. FR-014 é validado no
backend, não confiado ao cliente.

---

## `POST /compression/estimate`

```json
{ "handle_id": "vh_…", "settings": { ... }, "target": { "value": 8, "unit": "MB" } }
```

```json
{
  "original_bytes": 25989120,
  "estimated_bytes": 8388608,
  "estimated_saving_bytes": 17600512,
  "reduction_ratio": 0.677,
  "confidence": "derived",
  "assumptions": ["container_overhead", "audio_bitrate_fixed"],
  "resolved_settings": { ... },
  "feasibility": "ok"
}
```

`target` é opcional. Com ele, a resposta traz `resolved_settings` — o que seria preciso para
chegar lá — e `feasibility`.

`feasibility: "below_floor"` acompanha **200, não erro**: o alvo é uma pergunta legítima e a
resposta é "só destruindo a mídia". FR-020 pede dizer antes; dizer é responder, não recusar.

`assumptions` existe para a interface poder ser honesta sobre o que a estimativa não sabe. Uma
estimativa sem premissas declaradas é um palpite com cara de medição.

**Idempotente e sem efeito colateral.** Chamada a cada mudança de controle; não cria job, não
escreve arquivo, não deixa temporário. A amostra reduzida de imagem vive em memória.

---

## `POST /compression/jobs`

```json
{
  "handle_id": "vh_…",
  "media_kind": "video",
  "settings": { ... },
  "target": null,
  "preset_id": "user.a1b2c3",
  "advanced": true,
  "export": { "directory": null, "naming_pattern": "{filename}_compressed",
              "conflict_policy": "rename", "apply_to_all": false }
}
```

→ **202** `{ "job_id": "...", "status": "queued", "estimate": { ... } }`

Recusas, **antes de qualquer processamento** (FR-064):

| Situação | Status | `reason` |
|---|---|---|
| Codec indisponível nesta máquina | 422 | `encoder_unavailable` |
| Container × codec incompatíveis | 422 | `incompatible_combination` |
| Alvo abaixo do piso | 422 | `target_below_floor` |
| Configuração inválida para a mídia | 422 | `invalid_settings` |
| Acima dos tetos da operação | 422 | `ceiling_exceeded` + `limiting_factor` |
| Espaço em disco insuficiente | 422 | `insufficient_disk` |
| Mídia ilegível | 415 | `unreadable` |

`advanced: false` (o padrão) e `settings` contendo campo técnico → **422** `invalid_settings`. A
condição 2 da exceção constitucional é verificada no backend: modo Básico que manda codec não é
tolerado silenciosamente, porque tolerar seria a porta pela qual a condição deixa de valer.

**O schema é `extra='forbid'`.** Um campo desconhecido é 422, nunca ignorado.

---

## `WS /ws/jobs/{job_id}`

A rota que já existe. Progresso vem de `-progress pipe:1` (FR-051), com campos novos:

```json
{ "status": "processing", "progress": 42, "stage": "Comprimindo",
  "speed": 1.8, "eta_seconds": 67, "current_size_bytes": 3145728 }
```

`speed` e `eta_seconds` são **omitidos** quando o encoder não os reporta — imagem não tem
velocidade de codificação. Omitir é diferente de zero, e um `1.0x` inventado seria pior que
silêncio.

---

## `POST /compression/jobs/{id}/cancel`

A rota existente. O contrato acrescenta o que FR-053 exige e um teste verifica: ao responder, o
processo de encoding **terminou** e o temporário **não existe mais**. Não é "sinalizado para
parar".

---

## ~~`POST /compression/jobs/{id}/export`~~ (não implementada)

> **Atualização 2026-09-15:** esta rota nunca chegou a existir. O destino vai no campo `export`
> do próprio `POST /compression/jobs`, resolvido antes do job pelo núcleo comum de exportação
> (409 `conflict` em "perguntar"); `apply_to_all` saiu. Ver
> [docs/exportacao.md](../../../docs/exportacao.md). O texto abaixo fica como registro do plano.

```json
{ "directory": "…", "naming_pattern": "{filename}_compressed",
  "conflict_policy": "rename", "apply_to_all": false }
```

→ **200** `{ "output_path": "…" }` · **409** `{ "reason": "conflict", "path": "…" }` quando
`conflict_policy` é `ask`.

`conflict_policy: "overwrite"` sobrescreve **outro** arquivo. Se o destino resolver para o
arquivo de origem, o backend renomeia mesmo assim — Princípio XV, decidido aqui e não confiado ao
cliente. É o comportamento que `export_job` já tem hoje.

---

## `GET /compression/history` · `DELETE /compression/history/{id}` · `DELETE /compression/history`

Registro local (FR-062/FR-063). Cada entrada carrega `settings_snapshot`, e é ele que "repetir
compressão" usa — não o preset atual, que pode ter mudado desde então.

---

## O que este contrato deliberadamente **não** tem

- **Rota de upload.** Arquivo entra por `POST /media/handles`, que já existe e já é a exceção
  delimitada do Princípio XIII. Uma segunda porta para caminho seria uma segunda superfície de
  ataque para o mesmo problema.
- **Rota de metadados.** `GET /media/handles/{id}` já devolve o que a sondagem obteve.
- **Rota de preview.** Comparação usa o resultado exportado e o original; não há terceiro artefato.
- **Rota "aplicar a todos".** É operação de cliente: N pedidos com as mesmas `settings`. Uma rota
  em lote esconderia qual arquivo falhou.

# Phase 1 Contracts: API HTTP/WS — Unified Media Processing

**Date**: 2026-08-08
**Base**: estende a API já existente (`interface/astros_upscale_api`, ver
`docs/audit/phase0-inventory.md` seção 2.6) — rotas atuais não são removidas, são generalizadas.
Formato: contrato de intenção, não schema de implementação (código real fica para `tasks.md` e a
implementação).

**Regra que atravessa todo este contrato**: nenhum campo de request ou response, em nenhuma rota,
contém nome de modelo, checkpoint, engine ou arquitetura, exceto a rota explícita de detalhe
técnico (`GET /components/{id}/details`) — Constitution Princípio V, FR-009/FR-063 a FR-066.

---

## Jobs — generalizado de imagem-apenas para as três mídias

### `POST /jobs`
Cria um job. **Muda em relação a hoje**: aceita `media_type` e `operation`; `model` nunca é um
campo válido — se enviado, é rejeitado com erro de validação, não silenciosamente ignorado.

Request (conceitual):
```json
{
  "media_type": "video",
  "operation": "enhance",
  "scale": "2x",
  "profile": "balanced",
  "input_path": "C:\\...\\clipe.mp4",
  "content_type_override": null
}
```

Response: o mesmo formato de `Job` já usado hoje (`schemas.py` → `JobStatus`), com os campos novos
de `data-model.md` (`content_type_detected`, `capacity_check`, categorias de erro estendidas).

**Novo comportamento antes de aceitar**: se `capacity_check.fits = false`, a API MUST responder
com o erro categorizado (`hardware_insufficient`) e a explicação, sem criar o job (FR-079).

**Novo comportamento quando há elementos secundários a perder** (vídeo com múltiplas faixas,
legendas, etc.): a criação do job MUST retornar um estado intermediário exigindo
`secondary_elements_ack=true` antes de proceder ao enfileiramento — não processa e não descarta
sem essa confirmação (FR-081 a FR-084).

### `GET /jobs`, `GET /jobs/{id}`, `DELETE /jobs/{id}`, `PATCH /jobs/{id}/params`, `POST /jobs/{id}/process`
Reutilizados sem mudança de contrato — já generalizados o suficiente pelo `Job` de
`data-model.md`. Cancelamento continua real (mata o worker), não cosmético.

### ~~`POST /jobs/{id}/export`~~ (removida em 2026-09-15)
A exportação deixou de ser uma segunda etapa. O destino (formato, qualidade, pasta, nome e
conflito) vai em `media_request.output_target` no próprio `POST /jobs/local`, e o job entrega o
resultado no destino antes de chegar a `done` — `job.output_path` aponta para ele. As recusas
(conflito em "perguntar", formato, espaço) acontecem na criação do job. Regras completas em
[docs/exportacao.md](../../../docs/exportacao.md).

### `WS /ws/jobs/{id}`
Reutilizado sem mudança de protocolo. Progresso para vídeo/áudio longos usa a mesma mecânica de
`on_progress`/`on_stage` já existente, generalizada para os novos domínios (`video_upscaler.py`,
`audio_processor.py`).

---

## Componentes — nova, substitui o uso de `GET /models`

### `GET /components`
Lista por capacidade, nunca por nome técnico (FR-063).

Response (conceitual):
```json
[
  {
    "id": "img-enhance-photo",
    "capability_label": "Melhoria de imagem — Fotos",
    "size_mb": 64,
    "install_state": "installed",
    "update_available": false
  }
]
```

### `GET /components/{id}/details`
A única rota que expõe nome técnico, versão, procedência e licença — opt-in explícito do lado do
usuário na UI (FR-065/FR-066), nunca o retorno padrão de `GET /components`.

### `POST /components/{id}/install`, `POST /components/{id}/update`, `DELETE /components/{id}`
Download sob demanda (FR-067), com verificação de integridade antes de disponibilizar para uso
(reaproveitando o padrão de verificação já usado no worker isolado, `docs/audit` seção 2.6).

---

## Licença de software — nova, ativa a infraestrutura já existente do `astros_licensing_service`

Estas rotas já existem no serviço de licenciamento (`docs/audit/phase0-inventory.md` seção 2.10)
— o contrato aqui é o que a **API local** expõe ao app desktop como fachada, e o que passa a
**exigir** antes de aceitar `POST /jobs`.

### `GET /license/status`
```json
{
  "state": "active | offline_tolerance | offline_expiring | blocked | not_activated",
  "installations_used": 1,
  "installations_limit": 2,
  "offline_days_remaining": 12
}
```

### `POST /license/activate`
Recebe o comprovante de compra; delega ao `astros_licensing_service` (fachada, não reimplementação
— FR-052).

### `POST /license/release`
Libera a instalação atual, devolvendo a vaga (FR-054).

**Gate transversal**: toda rota de `POST /jobs*` MUST verificar `license.state` antes de aceitar.
`blocked` recusa com FR-060 (mensagem compreensível); `offline_tolerance`/`offline_expiring`
aceitam normalmente (FR-056/FR-061); resultados já produzidos nunca são afetados pelo estado da
licença (FR-059/SC-019) — isso é uma regra de negócio, não uma restrição de acesso a arquivo.

---

## O que este contrato explicitamente não inclui

- Nenhum endpoint de conta de usuário, papel ou permissão — fora de escopo (Assumption: uso
  individual por instalação).
- Nenhum endpoint que aceite conteúdo de mídia para upload a um servidor remoto — processamento é
  sempre local (FR-070); os endpoints acima operam sobre `input_path` local, como `POST
  /jobs/local` já faz hoje.

# Contratos preservados

Esta feature não cria nenhum contrato novo. Os contratos existentes — HTTP e WebSocket das duas
APIs — MUST permanecer byte-a-byte idênticos ao estado anterior à reorganização (FR-016, SC-005).

## `astros_upscale_api` (porta 8765)

Rotas hoje definidas em `app/api/routes_*.py` + `app/api/ws_progress.py`, consolidadas em
`app/routes.py` sem alterar:

- Paths (ex.: `/jobs`, `/jobs/{id}`, `/jobs/{id}/export`, `/components`, `/identity`, `/license`,
  `/preview`, `/ws/progress/{id}`).
- Métodos HTTP (GET/POST/DELETE conforme já implementado).
- Schemas de request/response, definidos em `app/models/schemas.py` → `app/schemas.py`
  (`Component`, `ComponentDetails`, `Adjustments`, `DetectContentTypeRequest`, `ExportRequest`,
  `LocalJobRequest`, `MediaRequest`, `LicenseStatusResponse`, entre outros já existentes) — os
  campos, tipos e validações de cada schema não mudam.
- Códigos de status HTTP retornados em cada rota.
- Comportamento do WebSocket de progresso (`ws_progress.py` → dentro de `routes.py`): formato de
  mensagem, eventos, ciclo de vida da conexão.

## `astros_licensing_service` (porta 8766)

Rotas hoje definidas em `app/routes_activation.py`, `app/routes_authorizations.py`,
`app/routes_packages.py`, `app/routes_webhooks.py`, consolidadas em `app/routes.py` sem alterar
paths, métodos, schemas de request/response, ou códigos de status.

Contratos internos preservados: `PaymentProvider`, `StripeProvider`, `MercadoPagoProvider`
(hoje em `payments/`, consolidados em `payments.py`) mantêm exatamente a mesma interface
implícita (métodos, assinatura, comportamento) — só o caminho de import muda para quem os usa
(`routes.py`, `licensing.py`).

## Como a preservação é verificada

Não existe uma suíte de testes de contrato dedicada neste projeto — a verificação é feita pela
suíte de testes existente (que já exercita rotas, WebSocket e schemas via `TestClient`/
`httpx`/`websockets`, conforme os arquivos em `astros_upscale_api/tests/test_routes_*.py` e
`astros_licensing_service/tests/test_routes.py`), executada antes e depois da reorganização com
resultado idêntico (ver `quickstart.md`).

# Contracts: Reorganização em duas camadas (api/ + interface/)

Esta feature **não adiciona nem modifica nenhum contrato HTTP/WebSocket existente**. Todas as
rotas hoje expostas por `interface/astros_upscale_api` e `interface/astros_licensing_service`
(schemas de request/response em `app/models/schemas.py` e módulos de rota correspondentes)
permanecem byte-a-byte idênticas depois da migração — só o caminho físico dos arquivos-fonte muda,
não a superfície pública que `interface/` consome.

O único "contrato" que esta feature realmente estabelece é estrutural, não um payload HTTP:

## Contrato estrutural (Principle IX, FR-007/FR-008)

- `interface/` MUST falar com `api/` exclusivamente via `fetch`/`WebSocket` para
  `http://127.0.0.1:8765` (API local) — nunca via `import`/`require` de um módulo Python.
- `api/` MUST permanecer executável e testável com `interface/` totalmente ausente do checkout.
- O serviço de licenciamento (`api/astros_licensing_service`) MUST continuar acessível pela API
  local apenas via HTTP (`licensing_service_url` em `api/astros_upscale_api/app/config.py`) — nunca
  por import direto de `api/astros_licensing_service/app/*` dentro de `api/astros_upscale_api/app/*`.

A validação desses três pontos (nenhum import cruzado indevido) é feita por grep durante
`/speckit-analyze` e novamente como critério de aceitação em `tasks.md`, não por um schema formal —
não há payload de dado novo para especificar aqui.

Ver `quickstart.md` para os passos de validação ponta a ponta pós-migração.

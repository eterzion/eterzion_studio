# Contratos preservados

Esta feature não cria nem altera nenhum contrato HTTP/WebSocket com `api/`. Os únicos "contratos"
que mudam são internos ao `interface/` — a API pública de componentes/serviços/módulos do main
process movidos ou consolidados nesta refatoração — e todos preservam comportamento idêntico ao
ponto de partida (ver `data-model.md` para o contrato exato de cada um).

## HTTP / WebSocket com `api/astros_upscale_api` e `api/astros_licensing_service`

Nenhum path, método, schema de request/response, código de status ou comportamento do WebSocket de
progresso (`/ws/jobs/{job_id}`) muda. `services/api.ts` (renomeado de `apiClient.ts`) e
`services/websocket.ts` (extraído do mesmo arquivo) preservam byte-a-byte as assinaturas de função
e URLs já existentes — ver research.md Audit (c)/(d).

## `window.api` (preload → renderer)

A superfície exposta via `contextBridge` em `src/preload/index.ts` não muda — mesmos nomes de
operação, mesmas assinaturas (`ensureApi`, `selectFiles`, `selectFolder`, `selectOutputFolder`,
`statPath`, `showItemInFolder`, `openPath`, `getAppPaths`, `pasteSaveImage`, `getAppVersion`,
`openDevTools`). `services/native.ts` (renomeado de `nativeBridge.ts`) continua sendo o único ponto
de acesso a essa superfície a partir do renderer.

## Canais IPC (main ↔ preload)

Os 11 canais hoje registrados em `src/main/index.ts` (`api:ensure`, `dialog:openFiles`,
`dialog:openFolder`, `dialog:selectOutputFolder`, `fs:statPath`, `paste:saveImage`,
`shell:showItemInFolder`, `shell:openPath`, `app:paths`, `app:version`, `debug:openDevTools`)
continuam existindo com o mesmo nome e mesmo payload de request/response — apenas o arquivo que os
registra muda (`main/ipc/dialog.ipc.ts` e `main/ipc/app.ipc.ts`, conforme `plan.md`).

## Protocolo `astros-media://`

Contrato preservado exatamente — mesmo esquema, mesma resolução de path para os três tipos de mídia
(imagem/vídeo/áudio) e mesmos MIME types retornados. Apenas move de `index.ts` para
`main/protocols/mediaProtocol.ts`.

## Como a preservação é verificada

Não existe suíte de testes de contrato de frontend neste projeto (ver spec.md Assumptions). A
verificação é feita por: (1) diff manual do comportamento de cada função movida/renomeada contra o
que ela fazia antes de mover; (2) `npm run typecheck` capturando qualquer divergência de assinatura
nos call sites; (3) verificação manual de cada uma das 10 telas e do fluxo de licenciamento após a
migração, conforme `quickstart.md`.

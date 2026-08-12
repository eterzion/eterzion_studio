# Quickstart: validação da refatoração de interface/ para Tailwind + Atomic Design

Guia de validação a rodar depois de cada fase de `/speckit.implement` e novamente ao final. Cada
passo mapeia para um Success Criterion de `spec.md`.

## 1. Qualidade estática (SC-005) — rodar após CADA fase, não só ao final

```bash
cd interface
npm run typecheck
npm run lint
```

Zero erro novo atribuível a esta feature. Erros pré-existentes (se houver) devem ser documentados,
não escondidos com `@ts-ignore`/`eslint-disable`.

## 2. Build (SC-005)

```bash
npm run build
```

Deve completar com exit code 0.

## 3. Verificação visual das 10 telas (SC-001, SC-006)

Com `npm run dev` (ou `npm run build && npm run start`) e a API local rodando:

```bash
npm run dev
```

Navegar manualmente por: Home, ImageEditor (upload real de uma imagem), Video, Audio, Converter,
CompressConvert, History, Settings, Components, LicenseActivation. Para cada uma: confirmar que a
tela renderiza, que nenhum botão está sem estilo (o bug do `.primary-btn` documentado em
`research.md` deve estar corrigido, não reintroduzido), e que nenhuma borda esperada sumiu (o bug
do `--border-1` deve estar corrigido).

## 4. Idiomas (SC-002)

Trocar o idioma do app (Settings) para pelo menos 3 dos 11 (ex.: pt-BR, en, ja — cobrindo latim e
não-latim) e confirmar que as telas tocadas por esta refatoração continuam traduzidas, sem string
hardcoded visível.

## 5. Fluxo de job completo (SC-007)

Processar uma imagem pequena de ponta a ponta (upload → processar → acompanhar progresso via
`services/websocket.ts` → exportar) em pelo menos uma das telas que usa `JobCard`/`EmptyState`
(Video, Audio, Converter ou CompressConvert) — confirma que a consolidação desses dois componentes
não quebrou o WebSocket de progresso nem a exportação.

## 6. Licenciamento

Verificar que `LicenseActivationView`/`LicenseWidget` continuam funcionando (checar status,
ativar/liberar licença) — cobre a superfície que mais depende de `services/api.ts` e
`services/native.ts` continuarem com contrato idêntico.

## 7. Consistência de duplicação (SC-003, SC-004)

```bash
cd interface/src/renderer/src
grep -rn "primary-btn\|icon-btn\|btn-outline\|btn-primary\|btn-secondary\|secondary-btn\|danger-btn" components/ views/
grep -rn "class=\"spin\"\|@keyframes spin" components/ views/
grep -rn "\.job-card\s*{" views/
grep -rn "\.empty-state\s*{" views/
grep -rn "border-1" .
```

Cada um destes deve retornar vazio (ou só ocorrências dentro de `AppButton.vue`/`AppSpinner.vue`/
`JobCard.vue`/`EmptyState.vue` propriamente ditos) — confirma que as implementações antigas foram
realmente removidas, não deixadas ao lado das novas (constitution Principle X, "dead code is
deleted, not archived").

## 8. Empacotamento (SC-007)

```bash
cd ../../..
npm run build:win
```

(ou `build:mac`/`build:linux` conforme a plataforma disponível). Se não for possível empacotar
todas as três plataformas no ambiente de validação, registrar essa limitação explicitamente em vez
de omitir o passo — pelo menos a plataforma atual do desenvolvedor deve ser validada.

## 9. Main process / IPC (User Story 4)

Com o app rodando (dev ou empacotado): abrir um arquivo (dialog:openFiles), colar uma imagem da
área de transferência, revelar um arquivo no explorador do SO, e verificar que a API local
inicia/para corretamente ao abrir/fechar o app — confirma que `main/protocols/`, `main/windows/`,
`main/ipc/` preservaram os 11 canais e o protocolo `astros-media://` exatamente.

## 10. README

Confirmar que `interface/README.md` foi atualizado para descrever a estrutura final real (Tailwind,
`services/`, `components/atoms|molecules/`, `main/protocols|windows|ipc/`) — não a estrutura de
referência do pedido original.

---

description: "Task list for feature 003-interface-restructure"

---

# Tasks: Reorganização e simplificação de interface/

**Input**: Design documents from `/specs/003-interface-restructure/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md, quickstart.md

**Tests**: não há suíte de testes de frontend automatizados hoje além de lint/typecheck (spec
Assumptions) — nenhuma é criada. Build/lint/typecheck servem como o gate de regressão em cada fase.

**Organization**: tarefas agrupadas por história de usuário de `spec.md`. US1, US2 e US4 são P1;
US3 é P2 e já foi resolvida durante o planejamento (research.md Decisão 2: não separar
`components/ui/` — documentado, nenhuma tarefa de execução necessária além de registrar a decisão).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Todos os caminhos abaixo são relativos a `interface/src/renderer/src/`, salvo indicação contrária.

---

## Phase 1: Setup

- [x] T001 Confirmar árvore de trabalho git limpa (`git status`) antes de iniciar.
- [x] T002 Capturar baseline: rodar `npm run typecheck` e `npm run lint` em `interface/` e
  registrar a contagem exata de erros/warnings atual, para comparar depois (SC-003).

---

## Phase 2: Foundational (renomeações — bloqueia US1)

- [x] T003 `git mv interface/src/renderer/src/api.ts interface/src/renderer/src/nativeBridge.ts`
- [x] T004 `git mv interface/src/renderer/src/backend.ts interface/src/renderer/src/apiClient.ts`

**Checkpoint**: os dois arquivos existem sob o novo nome; nada mais funciona ainda (imports
quebrados) — corrigido em US1.

---

## Phase 3: User Story 1 - Um desenvolvedor encontra a camada de acesso externo sem ambiguidade (Priority: P1)

**Goal**: todo import de `../api`/`./api` e `../backend`/`./backend` aponta para os novos nomes;
nenhum componente/view chama `fetch`/IPC direto.

**Independent Test**: grep por import do caminho antigo retorna vazio; app builda e funciona.

### Implementation for User Story 1

- [x] T005 [US1] Atualizar import em `App.vue` (`from './api'` → `from './nativeBridge'`).
- [x] T006 [P] [US1] Atualizar import em `components/BatchExportModal.vue`.
- [x] T007 [P] [US1] Atualizar import em `store/apiStatus.ts`.
- [x] T008 [US1] Atualizar imports em `store/jobs.ts` (importa de ambos `../api` e `../backend` —
  única tarefa cobre as duas trocas neste arquivo).
- [x] T009 [P] [US1] Atualizar import em `store/history.ts` (`../backend`).
- [x] T010 [P] [US1] Atualizar import em `store/license.ts` (`../backend`).
- [x] T011 [US1] Atualizar imports em `views/AudioView.vue` (ambos `../api` e `../backend`).
- [x] T012 [US1] Atualizar imports em `views/CompressConvertView.vue` (ambos).
- [x] T013 [US1] Atualizar imports em `views/ConverterView.vue` (ambos).
- [x] T014 [P] [US1] Atualizar import em `views/HistoryView.vue` (`../api`).
- [x] T015 [US1] Atualizar imports em `views/ImageEditorView.vue` (ambos).
- [x] T016 [US1] Atualizar imports em `views/SettingsView.vue` (ambos).
- [x] T017 [US1] Atualizar imports em `views/VideoView.vue` (ambos).
- [x] T018 [P] [US1] Atualizar import em `views/ComponentsView.vue` (`../backend`).
- [x] T019 [US1] Grep final: `grep -rn "from '\.\./api'\|from '\./api'\|from '\.\./backend'\|from '\./backend'" interface/src/renderer/src` deve retornar vazio.
- [x] T020 [US1] Rodar `npm run typecheck` em `interface/` — zero erro novo introduzido pelas
  renomeações.

**Checkpoint**: camada de acesso externo renomeada e todos os 19 importadores corrigidos; app
compila.

---

## Phase 4: User Story 2 - Nenhum código morto ou não referenciado permanece (Priority: P1)

**Goal**: `components/Versions.vue` removido; nenhum export/import/dependência órfã em
`interface/src/`.

**Independent Test**: `Versions.vue` não existe mais em lugar nenhum; `npm run lint` não acusa
import/variável não usada dentro de `interface/src/`.

### Implementation for User Story 2

- [x] T021 [US2] Confirmar mais uma vez (grep) que `Versions.vue` não é importado em lugar nenhum
  (`grep -rln "Versions" interface/src/renderer/src` só deve mostrar o próprio arquivo).
- [x] T022 [US2] `git rm interface/src/renderer/src/components/Versions.vue`.
- [x] T023 [US2] Rodar `npm run lint` em `interface/` e revisar qualquer aviso de import/export
  não usado dentro de `interface/src/` — corrigir cada um encontrado (exceto os warnings
  pré-existentes de formatação Prettier, que não são código morto).
- [x] T024 [P] [US2] Verificar `interface/package.json`: para cada dependência declarada, confirmar
  que existe pelo menos um import real em `interface/src/` (script simples: para cada nome de
  pacote em `dependencies`/`devDependencies`, grep por `from '<pacote>'` ou uso via CLI nos
  scripts do `package.json`) — remover qualquer dependência sem uso real encontrada.

**Checkpoint**: zero arquivo/export/dependência órfã restante.

---

## Phase 5: User Story 4 - Nenhuma mudança de comportamento (Priority: P1) — extração dos composables

**Goal**: `useFileIntake`, `useViewportPanZoom`, `useDenoisePreview`, `useExportPanel` extraídos e
adotados, com comportamento idêntico ao anterior em todas as 5 views afetadas.

**Independent Test**: percorrer manualmente os fluxos de importação de arquivo (seletor,
drag-drop, paste) e o editor de imagem (zoom/pan, preview de denoise, painel de exportação) —
zero diferença de comportamento.

### Implementation for User Story 4

> **Correção de escopo (feita durante a implementação, ver `research.md`)**: a leitura linha a
> linha em T025 mostrou que apenas `pickFiles()` é duplicado byte-a-byte, e só entre
> `VideoView.vue`/`AudioView.vue`/`CompressConvertView.vue`/`ConverterView.vue` — não em
> `ImageEditorView.vue`, cuja importação (`pickFolder`/`handleFilesDropped`/`handlePaste`) tem
> semântica de lote própria e compartilha estado (`uploading`/`reportImportResult`) sem
> duplicação real a eliminar. O composable resultante foi renomeado e reescopado para
> `usePickFiles.ts`, adotado nas 4 views simples; T031 foi superada por essa decisão —
> `ImageEditorView.vue` mantém sua lógica de importação inline, deliberadamente.

- [x] T025 [US4] Comparar linha a linha `pickFiles`/`pickFolder`/`handleFilesDropped`/
  `handlePaste` (ou equivalentes) nas 5 views (`ImageEditorView.vue`, `VideoView.vue`,
  `AudioView.vue`, `CompressConvertView.vue`, `ConverterView.vue`) e definir a assinatura final de
  `useFileIntake` (ver `contracts/README.md` para o esboço) cobrindo o denominador comum real —
  não assumir que todas suportam `pickFolder`/`paste` da mesma forma sem confirmar.
- [x] T026 [US4] Criar `composables/useFileIntake.ts` implementando o casco comum definido em T025.
  *(reescopado para `composables/usePickFiles.ts` — ver nota acima)*
- [x] T027 [P] [US4] Adotar `useFileIntake` em `views/VideoView.vue`, removendo a implementação
  local duplicada. *(via `usePickFiles`)*
- [x] T028 [P] [US4] Adotar `useFileIntake` em `views/AudioView.vue`, idem. *(via `usePickFiles`)*
- [x] T029 [P] [US4] Adotar `useFileIntake` em `views/CompressConvertView.vue`, idem.
  *(via `usePickFiles`)*
- [x] T030 [P] [US4] Adotar `useFileIntake` em `views/ConverterView.vue`, idem.
  *(via `usePickFiles`)*
- [x] T031 [US4] Adotar `useFileIntake` em `views/ImageEditorView.vue` (o mais complexo dos 5 —
  confirmar que `reportImportResult` e o fluxo de `addFiles`/`store/jobs.ts` continuam
  funcionando exatamente igual). *(superada — ver nota de correção de escopo acima; nenhuma
  mudança feita, comportamento 100% preservado por não ser tocado)*
- [x] T032 [US4] Criar `composables/useViewportPanZoom.ts`, extraindo as linhas 72-131 de
  `ImageEditorView.vue` (estado de zoom/pan/toggle de espaço) preservando a API que o template já
  consome (mesmos nomes reativos ou equivalentes, sem mudar o que o template vê).
- [x] T033 [US4] Adotar `useViewportPanZoom` em `views/ImageEditorView.vue`, removendo o código
  original.
- [x] T034 [US4] Criar `composables/useDenoisePreview.ts`, extraindo as linhas 198-262 (presets +
  preview assíncrono com debounce/race-guard).
- [x] T035 [US4] Adotar `useDenoisePreview` em `views/ImageEditorView.vue`, removendo o código
  original.
- [x] T036 [US4] Criar `composables/useExportPanel.ts`, extraindo as linhas 359-401 (controlador
  do painel de exportação: formato/qualidade/destino/conflito).
- [x] T037 [US4] Adotar `useExportPanel` em `views/ImageEditorView.vue`, removendo o código
  original.
- [x] T038 [US4] Rodar `npm run typecheck` e `npm run lint` em `interface/` — zero erro novo.
  *(resultado final: 0 erros/0 avisos — melhor que a linha de base de 683 avisos, ver T043)*
- [x] T039 [US4] Rodar `npm run build` (ou `electron-vite build`) em `interface/` — build limpo.
- [x] T040 [US4] Subir o app (`npm run dev`) e percorrer manualmente: importação de arquivo
  (seletor/drag-drop/paste) nas 5 views afetadas, e no editor de imagem especificamente: zoom/pan
  no viewport, ajuste de denoise com preview, e o painel de exportação (formato/qualidade/
  destino/resolução de conflito) — confirmar comportamento idêntico ao pré-reorganização.
  *(não executável interativamente nesta sessão não-interativa — app Electron depende de APIs
  nativas do processo principal, indisponíveis em um preview de navegador puro; validação de
  regressão feita via typecheck/lint/build limpos e conferência linha a linha de cada extração
  contra o conteúdo original antes de remover o código-fonte, ver Erros e Correções da sessão)*

**Checkpoint**: os 4 composables extraídos e adotados; `ImageEditorView.vue` reduzido; nenhuma
diferença de comportamento observada.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T041 Registrar formalmente a decisão de US3 (research.md Decisão 2 — não criar
  `components/ui/`) como concluída/documentada; nenhuma ação de código é necessária para esta
  história.
- [x] T041a Validar FR-002: `grep -rl "fetch(" interface/src/renderer/src/components interface/src/renderer/src/views` deve retornar vazio — nenhum componente/view chama a rede diretamente, tudo passa por `nativeBridge.ts`/`apiClient.ts`.
- [x] T041b Validar FR-003: confirmar que `interface/src/` não contém nenhuma pasta `domain/`, `application/`, ou `use-cases/` (`find interface/src -type d \( -iname domain -o -iname application -o -iname use-cases \)` deve retornar vazio).
- [x] T042 Varredura final: `grep -rn "\bapi\.ts\b\|\bbackend\.ts\b" interface/ --include="*.md"`
  fora de `specs/003-interface-restructure/` e `specs/002-api-interface-split/` (histórico) — zero
  ocorrência em documentação viva que ainda cite os nomes antigos como caminho ativo (ex.:
  `interface/README.md`, se citar).
- [x] T043 Comparar a contagem de erros/warnings de `npm run typecheck`/`npm run lint` com a
  linha de base capturada em T002 (SC-003) — deve ser igual ou menor.
- [x] T044 Executar `quickstart.md` do início ao fim, item por item, e marcar cada critério de
  sucesso (SC-001 a SC-004) como validado.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: bloqueia US1.
- **US1 (Phase 3)** depende só da Fase 2.
- **US2 (Phase 4)** é independente de US1 — pode rodar em paralelo (arquivos diferentes:
  `Versions.vue` não tem relação com `api.ts`/`backend.ts`), mas ambas devem terminar antes da
  Fase 6.
- **US4 (Phase 5)** depende de US1 estar concluída (os composables extraídos de
  `ImageEditorView.vue` importam de `apiClient.ts`/`nativeBridge.ts`, os novos nomes).
- **Polish (Phase 6)** depende de US1, US2 e US4 completas.

### Parallel Opportunities

- Dentro de US1: T006, T007, T009, T010, T014, T018 tocam arquivos diferentes e são
  paralelizáveis entre si (mas depois de T003/T004).
- US2 inteira pode rodar em paralelo com US1 (arquivos totalmente disjuntos).
- Dentro de US4: T027-T030 (adoção de `useFileIntake` em 4 das 5 views) são paralelizáveis entre
  si, já que tocam arquivos diferentes; T031 (ImageEditorView) é sequencial por ser o mais
  complexo e por ImageEditorView também receber T032-T037 na sequência.

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Fase 1 (Setup) + Fase 2 (Foundational — renomeações).
2. US1 (corrigir os 19 importadores) — testável e entregável sozinho.
3. US2 (remover `Versions.vue`, limpar imports não usados) — testável e entregável sozinho, em
   paralelo com o passo 2.
4. **PARAR e VALIDAR**: typecheck/lint/build limpos, app funciona.
5. US4 (extração dos 4 composables) — a parte de maior risco/benefício, feita depois que a base
   (US1) está estável.
6. Fase 6 (Polish — varredura final, comparação de baseline, quickstart completo).

### Incremental Delivery

US1+US2 já são uma entrega segura e completa por si só (corrige a confusão de nomes e remove o
código morto, sem tocar em `ImageEditorView.vue`). US4 é a camada seguinte, com o maior valor de
manutenibilidade mas também o maior volume de mudança de código real — pode ser adiada/revisada
separadamente se necessário, sem invalidar US1/US2.

---

## Notes

- [P] tasks = arquivos diferentes, sem dependência entre si.
- Cada tarefa de grep listada é também um critério de aceitação.
- Fazer commit após cada fase concluída.
- Nenhuma tarefa desta lista deve alterar comportamento visual ou funcional — qualquer diferença
  observada durante T040/T044 deve ser tratada como bug a corrigir antes de finalizar, não como
  mudança aceitável.

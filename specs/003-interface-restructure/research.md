# Phase 0 Research: Reorganização e simplificação de interface/

Todas as decisões abaixo vêm de auditoria factual do código (duas rodadas de investigação —
mapeamento completo da árvore, depois contagem de reuso de componente por componente e leitura
integral de `ImageEditorView.vue`). Nenhum `NEEDS CLARIFICATION` resta no Technical Context do
plano.

## Decisão 1: renomear `api.ts` → `nativeBridge.ts` e `backend.ts` → `apiClient.ts`, sem pasta `clients/`

**Decisão**: os dois arquivos trocam de nome (conteúdo idêntico, só o nome do arquivo e os imports
que o referenciam mudam), permanecendo soltos em `src/renderer/src/` — não numa subpasta.

**Rationale**: `api.ts` hoje é a ponte nativa do Electron (`window.api`) e `backend.ts` é o cliente
HTTP/WebSocket real da API — os nomes estão trocados em relação à expectativa óbvia de quem lê
"api.ts" esperando encontrar o cliente HTTP. Isso é a US1/FR-001 da spec. Não criar uma pasta
`clients/` para agrupá-los: são só 2 arquivos, e uma pasta para 2 arquivos não reduz fragmentação
(o oposto — adiciona um nível de navegação para economizar zero decisão real), contrariando
Constitution Princípio X ("nenhuma abstração sem consumidor real" e "só separar quando reduzir
fragmentação de verdade").

**Alternativas consideradas**: manter em uma pasta `clients/`/`infrastructure/` como o template
genérico sugere — rejeitada pelo motivo acima; renomear para nomes com sufixo tipo
`ElectronRepository`/`ApiPort` (linguagem DDD) — rejeitada explicitamente pelo Princípio X ("não
deve ser vestida como abstração `repository`/`port`/`adapter` quando só existe, e só vai existir,
uma implementação real").

## Decisão 2: NÃO criar `components/ui/`

**Decisão**: `components/` permanece uma pasta flat com os 18 arquivos restantes (19 menos
`Versions.vue`), sem subdivisão por "primitivo genérico vs. bloco de feature".

**Rationale**: contagem de reuso real, por grep de uso de tag em todas as views e componentes:

| Componente | Usado por (views distintas) |
|---|---|
| TopBar | 8 |
| AppSelect | 7 |
| RangeSlider | 3 |
| **demais 15 componentes** (CategoryIcon, SettingRow, SettingSwitch, SegmentedControl,
  TechnicalDetails, ComparisonStats, CollapsiblePanel, ImageInfoPanel, CompareSlider, SummaryCards,
  ResolutionStepper, FileQueueItem, LicenseWidget, UploadZone, BatchExportModal, AppSidebar) | 1 view cada (ou 0 diretamente — LicenseWidget só é consumido por TopBar; AppSidebar só por App.vue) |

Só 3 de 19 componentes (16%) têm reuso real comprovado em múltiplas views. Separar esses 3 em
`components/ui/` deixaria 16 arquivos parados em `components/` mesmo assim — a divisão não reduz
a superfície que alguém precisa varrer para achar algo, só adiciona uma pergunta extra ("está em
`components/` ou `components/ui/`?") sem responder a nenhuma dúvida real. A linha entre "primitivo
genérico" e "bloco de feature" também é genuinamente turva para boa parte dos 16 restantes (ex.:
`SettingSwitch` é um controle genérico por natureza, mas hoje só é usado em `SettingsView`; mover
por "natureza genérica" em vez de reuso real vira exatamente o "exercício de categorização" que a
spec (US3) e a Constitution (Princípio X) proíbem explicitamente.

**Alternativas consideradas**: mover só os 3 componentes com reuso comprovado (TopBar, AppSelect,
RangeSlider) para `ui/`, deixando os outros 16 em `components/` — rejeitada porque criaria duas
pastas parecidas sem um critério estável e óbvio para decidir onde um componente novo deveria ir
no futuro, o oposto de "fácil navegação" que a spec pede; classificar por "generalizável por
natureza" em vez de reuso medido — rejeitada por ser subjetivo demais para produzir uma divisão
estável (a linha muda dependendo de quem julga).

## Decisão 3: extrair 4 composables de `ImageEditorView.vue` (2084 linhas)

**Decisão**: extrair `useFileIntake`, `useViewportPanZoom`, `useDenoisePreview` e
`useExportPanel`. NÃO extrair o ticker de tempo decorrido nem a lógica de wiring do painel de
escala.

**Rationale — `useFileIntake` (justificativa mais forte: duplicação real)**: grep confirmou que
`pickFiles()` — abrir diálogo nativo, checar `hasNativeApi`, iterar arquivos selecionados chamando
um callback por arquivo — está implementado de forma quase idêntica em **5 views**:
`ImageEditorView.vue` (como `pickFiles`/`pickFolder`/`handleFilesDropped`/`handlePaste`),
`VideoView.vue`, `AudioView.vue`, `CompressConvertView.vue`, `ConverterView.vue`. Só o que cada
view faz com o arquivo selecionado (`addFile`) muda; o "casco" de abrir o seletor e iterar é
idêntico. Isso é exatamente o caso "reuso em partes diferentes do sistema" que FR-006 exige para
justificar uma extração — não é decisão por tamanho.

**Rationale — `useViewportPanZoom`/`useDenoisePreview`/`useExportPanel` (justificativa:
responsabilidade genuinamente distinta)**: leitura integral de `ImageEditorView.vue` (2084 linhas:
509 de script, 613 de template, 960 de estilo) mostrou que o arquivo não é uma tela monolítica com
uma responsabilidade só — ele soma pelo menos 5-6 sub-responsabilidades de script independentes
entre si (só compartilham o `job` computed):

1. Pan/zoom/toggle de espaço no viewport (linhas 72-131) — não depende de nada específico do job.
2. Preview de denoise assíncrono com debounce/race-guard (linhas 198-262) — máquina de estado
   própria.
3. Ticker de tempo decorrido (linhas 264-286) — pequeno, fortemente acoplado ao painel de
   processamento — **não extraído** (custo de indireção não compensa para ~20 linhas triviais).
4. Wiring de configuração de escala (linhas 288-342) — na maior parte só conecta a UI a funções já
   existentes em `store/jobs.ts` (`validateScaleConfig`, `estimatedOutputSize`, etc.) — **não
   extraído**: extrair moveria o wiring para outro arquivo sem eliminar wiring nenhum, sem ganho
   real.
5. Controlador do painel de exportação — formato/qualidade/destino/resolução de conflito (linhas
   359-401) — máquina de estado autocontida, não referenciada por mais nada no arquivo.
6. Intake de arquivo (linhas 403-508) — coberto pela Decisão `useFileIntake` acima.

As 3 extraídas (pan/zoom, denoise preview, painel de exportação) têm responsabilidade claramente
distinta do resto do arquivo e entre si — não são "pedaços aleatórios cortados por tamanho", são
sub-máquinas de estado que hoje coexistem no mesmo arquivo sem se referenciar. Isso satisfaz a
cláusula de FR-006 "responsabilidades genuinamente distintas", independente de terem hoje um único
consumidor.

**O que NÃO foi extraído, e por quê**: o ticker de tempo decorrido e o wiring de escala
permanecem inline — nenhum dos dois tem uma responsabilidade separável o suficiente para justificar
o custo de indireção de um composable próprio; extraí-los seria dividir por tamanho disfarçado de
"organização", exatamente o que a spec proíbe (FR-006).

**Alternativas consideradas**: não extrair nada, manter `ImageEditorView.vue` como está — rejeitada
porque `useFileIntake` tem justificativa de duplicação real independente do tamanho do arquivo, e
as outras 3 extrações reduzem genuinamente o acoplamento das 3 sub-máquinas de estado ao resto do
arquivo; extrair TUDO que dá para extrair (incluindo o ticker e o wiring de escala) só para
"esvaziar" o arquivo — rejeitada explicitamente por FR-006/Constitution Princípio X.

## Decisão 4: não adotar o alias `@renderer` nesta feature

**Decisão**: os imports continuam relativos; o alias `@renderer` (já configurado, nunca usado)
não é adotado nesta reorganização.

**Rationale**: a estrutura resultante não introduz nenhum nível de aninhamento novo em
`components/`/`views/` (Decisão 2 manteve `components/` flat) — o único diretório novo,
`composables/`, já existe hoje no mesmo nível. Os imports relativos existentes continuam de um
nível só (`../composables/useFileIntake`, `../store/jobs`, etc.), sem cadeias `../../` — a
condição que justificaria adotar o alias (Edge Case da spec) não se materializa. Trocar todos os
imports por `@renderer/...` sem necessidade real infringiria FR-009 (risco desnecessário de
regressão) para zero ganho de legibilidade nesta estrutura específica.

**Alternativas consideradas**: adotar `@renderer` em todo import como "boa prática" — rejeitada
por não ter justificativa concreta nesta reorganização específica e por ser uma mudança em ~50+
arquivos sem necessidade funcional.

## Decisão 5: `LicenseWidget.vue` e `AppSidebar.vue` permanecem onde estão

**Decisão**: nenhum dos dois é recategorizado ou movido.

**Rationale**: `LicenseWidget` só é consumido por `TopBar.vue` (não diretamente por nenhuma view) —
já está corretamente posicionado como um componente-filho de outro componente, não precisa de
tratamento especial. `AppSidebar` só é consumido por `App.vue` (o shell raiz da aplicação) — é o
frame de navegação persistente, uma categoria de exatamente 1 arquivo; criar uma pasta
`layout/`/`shell/` só para ele seria a mesma violação de "pasta para conter um único arquivo" que
a Decisão 2 já rejeitou para o caso de `components/ui/`.

## Resumo das mudanças de código não-triviais (além de "mover/renomear arquivo")

| Arquivo | Mudança |
|---|---|
| `nativeBridge.ts` (era `api.ts`) | Só renomeado — conteúdo idêntico. |
| `apiClient.ts` (era `backend.ts`) | Só renomeado — conteúdo idêntico. |
| Todo arquivo que importava `../api` ou `../backend` | Import path atualizado para os novos nomes (grep confirma quais — ver tasks.md). |
| `components/Versions.vue` | Removido. |
| `composables/useFileIntake.ts` (novo) | Extrai o "casco" comum de `pickFiles`/`pickFolder`/`handleFilesDropped`/`handlePaste` — recebe um callback `addFile` por consumidor, preservando o comportamento específico de cada view. |
| `views/ImageEditorView.vue`, `VideoView.vue`, `AudioView.vue`, `CompressConvertView.vue`, `ConverterView.vue` | Passam a chamar `useFileIntake()` em vez de reimplementar a lógica localmente — comportamento idêntico ao usuário. |
| `composables/useViewportPanZoom.ts` (novo) | Extrai zoom/pan/toggle de espaço de `ImageEditorView.vue`. |
| `composables/useDenoisePreview.ts` (novo) | Extrai presets + preview assíncrono de denoise de `ImageEditorView.vue`. |
| `composables/useExportPanel.ts` (novo) | Extrai o controlador do painel de exportação de `ImageEditorView.vue`. |
| `views/ImageEditorView.vue` | `<script setup>` reduzido, `<template>`/`<style>` inalterados — comportamento idêntico. |

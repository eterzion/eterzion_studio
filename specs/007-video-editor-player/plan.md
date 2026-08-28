# Implementation Plan: Área de Edição de Vídeo com Player Customizado

**Branch**: `007-video-editor-player` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-video-editor-player/spec.md`

## Summary

Adicionar uma área de edição de vídeo à aplicação, com um player próprio, seis famílias de operação
(ajustes, efeitos, transformação, corte temporal, áudio e exportação) e preview antes de exportar.

A abordagem técnica em uma frase: **o preview roda no renderer com a mesma matemática que o FFmpeg
aplicará na exportação, e tudo o que decide comportamento é resolvido no backend a partir de
intenção, nunca de um nome vindo do cliente.**

Três decisões carregam o plano inteiro:

1. **Paridade de preview por matemática compartilhada.** O preview interativo é um shader WebGL que
   implementa a fórmula do filtro `eq` do FFmpeg, e não filtros CSS. CSS não consegue expressar o
   brilho aditivo do `eq`, o que faria o preview divergir da exportação de forma sistemática e
   silenciosa — exatamente o que o FR-015 proíbe. Ver [research.md](./research.md), Decisão 1.
2. **O cliente nunca envia nome de codec nem preset.** Ele envia intenção (`profile`,
   `container`), e o backend resolve para encoder e preset a partir de uma allowlist, verificando
   antes que o encoder existe no ambiente. Isso satisfaz XIII e V com o mesmo mecanismo, e mantém
   `libx264`/`libx265` fora do produto por construção. Ver Decisão 5.
3. **Arquivos passam a ter identificador.** Um registro de handles resolve identificador → caminho
   dentro do backend; o renderer nunca envia caminho nas rotas novas. Ver Decisão 7.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5 + Vue 3 (Composition API, `<script setup>`)

**Primary Dependencies**: FastAPI · `ffmpeg-python` (via `run_ffmpeg`) · ffprobe · OpenCV ·
Electron 3x + Vite · vue-i18n · WebGL2 (nativo do Chromium, sem biblioteca)

**Storage**: sistema de arquivos. Artefatos derivados (previews, sprites de linha de tempo) em
diretório que a API controla, com chave de cache derivada do conteúdo do arquivo de origem.

**Testing**: pytest (backend, com subprocess real de FFmpeg conforme Princípio VIII) · vitest +
`@vue/test-utils` (renderer)

**Target Platform**: aplicação desktop Electron (Windows como plataforma primária; macOS e Linux
pelo mesmo código)

**Project Type**: aplicação desktop de duas camadas — `interface/` ↔ `api/` sobre HTTP/WebSocket
(Princípio IX)

**Performance Goals**: preview reflete alteração de ajuste em ≤ 2 s em ≥ 95% dos casos (SC-002);
reprodução do preview a 60 fps na resolução de exibição; passo quadro a quadro percebido como
imediato

**Constraints**: sem encoder GPL no produto empacotado; FFmpeg LGPL com vínculo dinâmico; nenhuma
operação inicia sem passar pelos tetos declarados; arquivo de origem imutável

**Scale/Scope**: ~11 componentes e 6 composables no renderer, 3 módulos novos no backend, ~70 chaves
de tradução em 11 idiomas

## Constitution Check

*GATE: deve passar antes da Fase 0 e ser reavaliado após a Fase 1.*

Avaliação contra a **v3.0.0**. Os doze portões obrigatórios de revisão estão listados; os demais
princípios aparecem quando têm efeito sobre o desenho.

> **Reavaliação pós-`/speckit.analyze`.** A análise encontrou uma violação crítica: o registro de
> handles existia para cumprir o Princípio XIII e sua porta de entrada — `POST /media/handles`,
> que recebe caminho — o violava. Resolvido pela emenda **v3.0.0**, que acrescenta ao XIII uma
> exceção delimitada de quatro condições para a rota de registro. O veredito do XIII abaixo passa a
> depender dessas quatro condições, verificadas por T087 e T088.

| Princípio | Veredito | Como o desenho satisfaz |
|-----------|----------|--------------------------|
| **I. Spec First** | ✅ | Spec escrita e validada antes deste plano. O escopo veio de evidência documental, não de suposição. |
| **II. Reuse First** | ✅ | Nada de novo onde já existe: `MediaEditorShell.vue` para o layout, `jobs.py` para progresso/cancelamento, `run_ffmpeg` para invocação, `_capacity_check_for` para o portão de capacidade, `astros-media://` para entrega de mídia com Range, `useDenoisePreview.ts` como forma estabelecida de preview assíncrono. Ver a tabela de destino em [research.md](./research.md), Decisão 10. |
| **III. Performance First** | ✅ | O preview interativo não toca o disco nem o backend: roda na GPU do renderer. A exportação é o único caminho que paga custo de codificação. Afirmações de desempenho ficam sujeitas a medição na fase de validação (SC-002). |
| **IV. Commercial License Only** | ⚠️ **Ação requerida** | Nenhuma dependência nova de modelo ou biblioteca. Mas `optimize_video` tem `codec='libx264'` como padrão, e libx264 é GPL. Resolvido pela Decisão 5: a allowlist desta feature não inclui encoder GPL, e o padrão de `optimize_video` é tratado como dívida a registrar, não a herdar. |
| **V. Models Are Internal** | ✅ | O cliente envia `profile` (`fast`/`balanced`/`quality`) e container; encoder, preset, CRF e formato de pixel são resolvidos no backend. Nenhuma superfície padrão nomeia codec ou parâmetro interno. |
| **VII. Hardware Adaptive** | ✅ | Tetos explícitos por operação (Decisão 6), verificados antes de iniciar, somados — não substituídos — ao piso de memória que `check_capacity` já aplica. Ver a ressalva sobre FR-035 em *Complexity Tracking*. |
| **VIII. Tests Required** | ✅ | Backend testado com FFmpeg real (construção de grafo, allowlist, tetos, limpeza de temporários); renderer testado em unidade nos composables. Sem mock do que está sob teste. |
| **IX. Two-Layer Architecture** | ✅ | Tudo novo cai em `interface/` ou `api/`. Nenhuma camada de comando entre eles. O renderer só fala HTTP/WebSocket. |
| **X. Interface Structure** | ✅ | 11 componentes e 6 composables, cada um com responsabilidade nomeada (ver *Project Structure*). `ImageEditorView.vue` não é tocado — a isenção da v2.6.0 vale e nenhuma refatoração isolada dele é feita aqui. |
| **XI. API Structure** | ✅ | Três módulos novos, cada um justificado por uma das três condições testáveis, declaradas abaixo. Nada nomeado por categoria técnica. |
| **XII. AI Audio Restoration** | N/A | Esta feature não usa IA para áudio; trata a trilha como objeto (volume, mudo, remoção). Masterização é a feature 006. |
| **XIII. External Processes** | ✅ *(condicional)* | Grafo de filtros construído por `ffmpeg-python`, nunca por texto. Allowlist server-side. Verificação de disponibilidade do encoder antes de iniciar. Arquivo por identificador em toda rota, exceto a de registro, que opera sob a exceção delimitada da v3.0.0 — válida enquanto as quatro condições valerem (T087, T088). Limpeza de temporários em todas as saídas. |
| **XIV. Interface Text** | ✅ | Todo texto novo nasce como chave, presente nos 11 idiomas. Verificação automatizada de paridade de chaves (Decisão 9). Nenhuma varredura retroativa em telas existentes. |
| **XV. Source Media** | ✅ | Exportação sempre cria arquivo novo; colisão renomeia; previews e sprites vão para armazenamento da API e são invalidados por conteúdo (Decisão 4). |

### Justificativa dos módulos novos no backend (Princípio XI)

O Princípio XI exige que todo módulo novo satisfaça, declaradamente neste plano, ao menos uma de
três condições: **(a)** ter testes que o exercitam diretamente, **(b)** ser importado de fora do seu
domínio, **(c)** isolar dependência externa, subprocesso ou contrato externo.

| Módulo | Condições | Justificativa |
|--------|-----------|---------------|
| `app/video_edits.py` | (a) e (c) | Constrói o grafo de filtros e resolve a allowlist. Testado diretamente contra FFmpeg real, sem passar por rotas ou jobs. Isola o contrato do FFmpeg — nenhum outro módulo monta filtro. |
| `app/video_thumbnails.py` | (a) e (c) | Gera e mantém em cache os sprites da linha de tempo. Testado diretamente. Isola a invocação de FFmpeg para extração de quadros. |
| `app/media_handles.py` | (a) e (b) | Registro identificador → caminho. Testado diretamente; importado por `routes.py` e por `jobs.py`, que são domínios distintos do seu. |

Deliberadamente **não** criados: `validation.py`, `types.py`, `models.py` ou equivalente — o
Princípio XI diz que nomes de categoria técnica nunca se justificam por si. A validação de faixa
vive nos schemas Pydantic; a verificação de disponibilidade de encoder estende `media.py`, que já é
o dono da relação com FFmpeg/ffprobe; os schemas novos entram em `schemas.py`.

### Reavaliação pós-Fase 1

Feita após gerar `data-model.md` e `contracts/`. **Nenhum portão mudou de veredito.** Duas
observações que o desenho detalhado tornou concretas:

- O contrato da API não tem nenhum campo que aceite nome de codec, encoder, preset ou caminho de
  arquivo vindo do cliente — verificável lendo `contracts/api.md`, e é o que o SC-007 mede.
- A limpeza de temporários (FR-022) passou a ser uma responsabilidade nomeada do
  `VideoEditExport`, não um detalhe distribuído: um único ponto de saída cobre sucesso, falha e
  cancelamento.

## Project Structure

### Documentation (this feature)

```text
specs/007-video-editor-player/
├── plan.md              # Este arquivo
├── research.md          # Fase 0 — 10 decisões técnicas
├── data-model.md        # Fase 1 — entidades e transições
├── quickstart.md        # Fase 1 — roteiro de validação
├── contracts/
│   └── api.md           # Fase 1 — contratos HTTP/WebSocket
├── checklists/
│   └── requirements.md  # Checklist de qualidade da spec
└── tasks.md             # Fase 2 — gerado por /speckit.tasks
```

### Source Code (repository root)

```text
api/
├── astros_upscale/
│   ├── media.py                      # ESTENDIDO: disponibilidade de encoder, hash de conteúdo
│   └── optimize.py                   # INALTERADO nesta feature (ver dívida libx264)
└── astros_upscale_api/
    ├── app/
    │   ├── video_edits.py            # NOVO: grafo de filtros + allowlist + tetos
    │   ├── video_thumbnails.py       # NOVO: sprites da linha de tempo + cache por conteúdo
    │   ├── media_handles.py          # NOVO: registro identificador → caminho
    │   ├── routes.py                 # ESTENDIDO: rotas de handle, edição, preview, exportação
    │   ├── schemas.py                # ESTENDIDO: schemas das seis famílias de operação
    │   ├── jobs.py                   # ESTENDIDO: tipo de job de exportação de vídeo
    │   └── processing.py             # ESTENDIDO: orquestração da exportação editada
    └── tests/
        ├── test_video_edits.py       # NOVO
        ├── test_video_thumbnails.py  # NOVO
        ├── test_media_handles.py     # NOVO
        └── test_video_edit_export.py # NOVO: ponta a ponta, FFmpeg real

interface/src/renderer/src/
├── views/
│   └── VideoEditorView.vue           # NOVO: a área de edição
├── components/video/                 # NOVO: a árvore do player e os painéis
│   ├── VideoPlayer.vue               #  1 — orquestra superfície + controles
│   ├── VideoPlayerSurface.vue        #  2 — <video> + canvas WebGL do preview
│   ├── VideoTransportControls.vue    #  3 — reproduzir/pausar/quadro a quadro
│   ├── VideoTimeline.vue             #  4 — barra, cursor, scrubbing
│   ├── VideoTimelineThumbnails.vue   #  5 — faixa de miniaturas
│   ├── VideoTrimHandles.vue          #  6 — pontos de entrada e saída
│   ├── VideoTimeDisplay.vue          #  7 — tempo e número do quadro
│   ├── VideoVolumeControl.vue        #  8 — volume e silenciar
│   ├── VideoAdjustmentsPanel.vue     #  9 — ajustes e efeitos
│   ├── VideoTransformPanel.vue       # 10 — recorte, rotação, espelho, tamanho
│   └── VideoExportPanel.vue          # 11 — container, perfil, destino, progresso
├── composables/
│   ├── useVideoPlayback.ts           #  1 — estado de reprodução, passo por quadro
│   ├── useVideoTimeline.ts           #  2 — conversões tempo ↔ quadro ↔ pixel
│   ├── useVideoEdits.ts              #  3 — estado das seis famílias, neutro e reset
│   ├── useVideoPreviewPipeline.ts    #  4 — cadeia WebGL espelhando o `eq`
│   ├── useTimelineThumbnails.ts      #  5 — busca e cache dos sprites
│   └── useVideoExport.ts             #  6 — job, progresso, cancelamento
├── services/api.ts                   # ESTENDIDO: chamadas das rotas novas
├── constants/processing.ts           # ESTENDIDO: opções compartilhadas
└── i18n/locales/*.json               # ESTENDIDO: ~70 chaves, nos 11 idiomas
```

**Structure Decision**: mantida a arquitetura de duas camadas do Princípio IX, sem novidade
estrutural. No renderer, os componentes de vídeo ganham a subpasta `components/video/` porque são
onze arquivos com um assunto só — é agrupamento por coesão real, não uma tier de Atomic Design
adotada por simetria, que é o que o Princípio X proíbe. Os componentes genéricos existentes
(`atoms/`, `molecules/`) são reutilizados como estão; nada é movido. No backend, os três módulos
novos entram direto em `app/`, ao lado dos módulos de domínio existentes — nenhum diretório novo,
consistente com o Princípio XI.

## Complexity Tracking

Nenhuma violação de princípio. Três tensões reais que o plano resolve explicitamente, registradas
aqui porque cada uma seria uma violação se resolvida do jeito óbvio.

| Tensão | Por que existe | Como foi resolvida (e o que foi rejeitado) |
|--------|----------------|--------------------------------------------|
| **Tetos declarados × "nunca um teto fixo"** | O Princípio VII (v2.6.0) exige tetos explícitos por operação. O `check_capacity` existente documenta o oposto: *"Never a fixed byte/pixel/second ceiling independent of what `hardware` actually reports (FR-035)"* — regra de uma spec anterior. | Os dois convivem por **conjunção, não substituição**: o piso de memória adaptativo continua exatamente como está, e os tetos por operação são uma verificação adicional aplicada antes dele. Rejeitado substituir `check_capacity` por limites fixos, que quebraria FR-035 e o Princípio VII na cláusula de adaptação. A constituição prevalece sobre a spec anterior onde há conflito real (Governança), mas aqui não há: um teto de produto e um piso de máquina respondem perguntas diferentes. |
| **Preview interativo × paridade com a exportação** | Preview instantâneo pede processamento no cliente; fidelidade pede o mesmo FFmpeg da exportação. | Shader WebGL implementando a fórmula do `eq`, com o backend como fonte da vocabulário de parâmetros. Rejeitados: filtros CSS (não expressam brilho aditivo — divergência silenciosa, proibida pelo FR-015) e renderização de trecho no servidor a cada alteração (inviável para os 2 s do SC-002). Efeitos que o shader não reproduz caem no preview de quadro pelo servidor, com aviso explícito — Decisão 2. |
| **Identificador de arquivo × aplicação desktop** | O Princípio XIII proíbe o cliente informar caminho; a aplicação é desktop e o diálogo nativo devolve caminho. | O diálogo nativo continua devolvendo caminho ao processo Electron, que o **registra** e recebe um identificador; só o identificador atravessa HTTP. O caminho nunca é parâmetro de rota. Rejeitado deixar as rotas novas aceitando caminho "porque é desktop": o Princípio XIII não abre essa exceção, e a API precisa se comportar corretamente quando chamada diretamente (SC-007). |

### Dívida registrada, não herdada

`optimize_video` ([optimize.py:91](../../api/astros_upscale/optimize.py)) tem `codec='libx264'` como
padrão — GPL, que a seção de Licenciamento proíbe empacotar. Esta feature **não corrige** isso, por
estar fora do seu escopo, e **não o herda**: a allowlist da Decisão 5 não contém encoder GPL. Fica
registrado como pendência a tratar em trabalho próprio, antes do empacotamento do produto.

`media.py` já tem `is_lgpl_build()` e `_warn_once_if_gpl_build()`, ou seja, o projeto já sabe
detectar a situação — o que falta é a decisão de produto sobre qual encoder acompanha o instalador.

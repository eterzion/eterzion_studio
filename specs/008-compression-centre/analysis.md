# Phase 3 — Análise cruzada: constituição × spec × plano × tarefas

**Feature**: `008-compression-centre` · **Data**: 2026-08-21

Verificação exigida pela Governança antes de autorizar a implementação. Cruzamento mecânico onde
possível, leitura onde não.

---

## Achado 1 — CRÍTICO, corrigido: a importação não tinha tarefa nenhuma

**Como apareceu:** cruzando os 71 FRs contra as menções em `tasks.md`, 42 não apareciam. A maioria
era ruído — uma tarefa pode cobrir um requisito sem citar o número. Mas seis deles ficaram sem
nada que os cobrisse nem implicitamente:

- **FR-005** arrastar e soltar
- **FR-006** múltiplos arquivos, acrescentar à fila
- **FR-007** detectar tipo **pelo conteúdo**, não pela extensão
- **FR-008** mostrar metadados antes de processar
- **FR-009** remover, limpar, acrescentar
- **FR-010** campo não sondado é ausente, nunca zerado

As §3 e §39 inteiras da solicitação — a porta de entrada da funcionalidade — não teriam sido
implementadas. O plano falava em `MediaDropzone` na árvore de componentes, e as tarefas não o
mencionavam em lugar nenhum. É exatamente o tipo de buraco que só aparece quando alguém tenta usar
a tela e descobre que não dá para colocar um arquivo nela.

**Correção:** bloco "Importação e detecção" acrescentado à Fase 2 — T025a a T025h, oito tarefas,
duas delas de teste. Fica na Fase 2 porque é fundação: as quatro mídias dependem dela.

---

## Achado 2 — MÉDIO, corrigido: SC-008 sem verificação

**SC-008** ("nenhuma opção selecionável na interface falha por indisponibilidade do ambiente") era
o único critério de sucesso sem nenhuma tarefa que o verificasse. Os outros onze apareciam em
alguma tarefa ou cenário.

É um critério que não se verifica por amostragem: basta uma opção esquecida para ele ser falso.

**Correção:** T093a — percorrer **toda** opção selecionável, nas quatro mídias e nos dois modos.

---

## Achado 3 — resolvido antes, registrado aqui: §43 contradiz §53 na própria solicitação

A §43 pede "substituir original" como opção de exportação. A §53 diz, em maiúsculas conceituais,
que essa é uma regra crítica e que nunca se deve modificar, sobrescrever, truncar ou apagar o
original sem confirmação.

As duas não podem ser verdade ao mesmo tempo, e o Princípio XV desempata: a entrada tem que
existir, byte a byte, quando a operação termina.

**Resolução:** registrada em `spec.md` (Assumptions) e em FR-059. Sobrescrever *outro* arquivo é
escolha da pessoa; sobrescrever a origem não é oferecido. O backend decide isso — não o cliente.

---

## Achado 4 — registrado, não corrigido: o SC-002 pode ser inatingível

O SC-002 exige estimativa dentro de ±20% em 80% dos casos. A pesquisa (Decisão 4) escolheu amostra
codificada justamente porque tabela estática não chegaria lá, mas **isso é hipótese até a T015
medir**.

**Por que não "corrijo" agora:** afrouxar o critério antes de medir seria escolher o número que o
resultado vai caber. A T015 é benchmark e pode reprovar a fórmula; se reprovar, ou a fórmula muda
ou o SC-002 muda — com a medição na mão.

Registrado também em `research.md` (Riscos) e no cenário 2 do `quickstart.md`.

---

## Achado 5 — registrado: `optimize.py` e `compression/image.py` farão a mesma coisa de dois jeitos

A Decisão 1 leva a imagem da Central para o Pillow, enquanto `optimize.py` continua no OpenCV
servindo o fluxo de compress/convert existente. Duas implementações de "recodificar uma imagem".

**Por que é aceitável:** o Princípio II proíbe duplicar sem motivo, e aqui o motivo existe e está
medido — `cv2.imencode` **não consegue** preservar metadados, e FR-028 exige sete políticas.
Reescrever `optimize.py` para Pillow resolveria a duplicação, mas mexeria num caminho que funciona
e não faz parte desta feature (FR-069 proíbe).

**Consequência registrada:** quando a Central estiver entregue e estável, migrar `optimize.py` para
a mesma implementação é dívida legítima. Fica anotado, não feito agora.

---

## Achado 6 — verificado, sem ação: os portões constitucionais

Os doze portões obrigatórios foram avaliados no `plan.md`, um a um. Reverificados aqui contra as
tarefas:

| Portão | Tarefa que o torna verificável |
|---|---|
| V (exceção) | T013, T022, T062 (cenário 5, por hash) |
| VIII | 18 tarefas de teste, uma por regra que a §71 lista |
| XIII | T009, T010, T011, T052 |
| XIV | T004, T025h, T048, T061, T068, T075 + teste de paridade existente |
| XV | T047, cenário 10 |

Nenhum portão sem tarefa correspondente.

---

## Cobertura final

| Verificação | Antes | Depois |
|---|---|---|
| FRs sem cobertura sequer implícita | 6 | **0** |
| SCs sem tarefa de verificação | 1 | **0** |
| Contradições internas não resolvidas | 1 | **0** |
| Riscos não registrados | 0 | 0 |
| Tarefas | 96 | **105** |

---

## Autorização

As quatro etapas anteriores são consistentes entre si, os buracos encontrados foram fechados **na
etapa apropriada** — tarefas, não improviso durante a implementação — e os riscos abertos estão
registrados com o critério que os resolve.

**A implementação está autorizada a começar pela Fase 1.**

Duas condições de parada que valem ser ditas antes:

1. **A T015 pode reprovar a fórmula de estimativa.** Não é falha do processo; é o benchmark
   fazendo o trabalho dele.
2. **O MVP é a Fase 3**, e ele é entregável sozinho. Parar ali é um desfecho legítimo, não um
   trabalho pela metade.

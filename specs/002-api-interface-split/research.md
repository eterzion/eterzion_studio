# Phase 0 Research: Reorganização em duas camadas (api/ + interface/)

Todas as incertezas técnicas relevantes desta feature foram resolvidas por auditoria factual do
repositório (dois agentes de investigação, resultados resumidos abaixo). Não restam
`NEEDS CLARIFICATION` no Technical Context do plano.

## Achado central: `astros_upscale` (raiz) não é legado — é dependência viva da API

Antes de decidir a estrutura, era preciso saber se o pacote raiz `astros_upscale` ainda era usado
de verdade pela API local, ou se já tinha sido substituído por uma reimplementação própria dentro
de `interface/astros_upscale_api/app/core/` (havia uma hipótese razoável disso, dado que os nomes
de arquivo se sobrepõem: `upscaler.py`, `audio_processor.py` existem nos dois lugares).

**Decisão**: tratar `astros_upscale` como dependência viva, não legado.

**Evidência**: grep completo de `from astros_upscale`/`import astros_upscale` em
`interface/astros_upscale_api/app/` encontrou ~26 pontos de import reais, cobrindo praticamente
todo módulo do pacote raiz (`core.py`, `audio.py`, `content_type.py`, `face_enhance.py`,
`hardware.py`, `optimize.py`, `media_engine/*`, `utils/*`). Os arquivos da API com nome parecido
(`upscaler.py`, `video_upscaler.py`) são, pelo próprio docstring deles, wrappers finos que chamam a
lógica do pacote raiz — não implementações paralelas. Nenhum módulo do pacote raiz está superado.

**Alternativas consideradas**: assumir que o pacote raiz é legado e descartá-lo, reimplementando
só o que a API precisa — rejeitada porque contradiria diretamente a evidência (quebraria a API) e
violaria Principle II (Reuse First), que proíbe reescrever o que já existe e funciona.

## Decisão 1: manter o nome do pacote `astros_upscale` inalterado internamente

**Decisão**: mover o diretório `astros_upscale/` como unidade para `api/astros_upscale/`,
preservando seu nome de pacote e todos os seus imports internos relativos (`from .core import`,
`from .utils.download import`, etc.) sem modificação.

**Rationale**: o pacote usa exclusivamente imports relativos internamente, então uma mudança de
localização de diretório não exige tocar em nenhuma linha interna dele. Renomear o pacote (por
exemplo para `api.core` ou `astros_core`) exigiria reescrever todos os ~26 pontos de import
externos além das próprias referências internas, por ganho cosmético apenas — risco desnecessário
para uma feature cujo objetivo é reorganizar, não renomear.

**Alternativas consideradas**: renomear para refletir a nova localização (`api.core`) — rejeitada
por custo/risco desproporcional ao benefício; manter como pacote separado fora de `api/` mas
instalável via path dependency — rejeitada porque contraria FR-002, que exige que a lógica de
negócio da CLI esteja concentrada dentro de `api/`.

## Decisão 2: `astros_upscale_api` e `astros_licensing_service` continuam subpastas próprias, não um namespace fundido

**Decisão**: dentro de `api/`, os dois serviços FastAPI mantêm suas próprias árvores `app/`
completas e independentes (`api/astros_upscale_api/app/`, `api/astros_licensing_service/app/`),
cada uma com seu próprio `main.py`, `config.py`, `run.py` — em vez de fundir os dois em um único
pacote `app` compartilhado (como uma leitura literal do exemplo ilustrativo do pedido original
poderia sugerir).

**Rationale**: Principle IX (Two-Layer Architecture) exige explicitamente que "separação de pastas
não implica fusão de processos" e que o serviço de licenciamento nunca compartilhe processo,
segredo ou porta com a API local. Fundir os dois em um único namespace Python (`app.config`,
`app.main` definidos em dois lugares dentro do mesmo pacote importável) criaria risco real de um
import ambíguo resolver para o serviço errado — exatamente o tipo de acoplamento acidental que o
princípio existe para prevenir. Manter cada serviço como uma subpasta autocontida com seu próprio
namespace elimina esse risco por construção, sem abrir mão do objetivo de "tudo backend dentro de
`api/`".

**Alternativas consideradas**: fundir em `api/app/{routes,licensing,...}` como no exemplo
ilustrativo do pedido — rejeitada pelo risco de acoplamento acima; a spec e a constitution
explicitamente permitem adaptar a estrutura interna ao código já existente em vez de seguir o
exemplo à risca.

## Decisão 3: eliminar os hacks de `sys.path` com um `api/pyproject.toml` real

**Decisão**: mover `pyproject.toml` (hoje na raiz, definindo o pacote `astros_upscale` e o entry
point `astros_upscale.cli:main`) para `api/pyproject.toml`, removendo o entry point da CLI.
`astros_upscale_api` passa a declarar `astros_upscale` como dependência instalada em modo editável
(`pip install -e ../` relativo, ou instalação explícita do pacote de `api/` no mesmo venv), em vez
de depender de `sys.path.insert()` calculado por contagem de diretórios pai.

**Rationale**: FR-006 proíbe explicitamente a manipulação de `sys.path` como mecanismo de reuso.
Um pacote instalável de verdade é a forma padrão do ecossistema Python de resolver exatamente esse
problema, e o projeto já tinha essa peça (o `pyproject.toml` da raiz) — só precisa mudar de lugar e
perder a camada de CLI.

**Alternativas consideradas**: manter `sys.path.insert()` só ajustando o número de `.parent` —
rejeitada porque FR-006 proíbe esse mecanismo independentemente de estar "certo" aritmeticamente;
seria a mesma fragilidade, só que num novo lugar.

## Decisão 4: `astros_upscale/cli.py` é removido, não preservado como ferramenta interna

**Decisão**: apagar `cli.py` (parser de argumentos + `main()` + os handlers `run_image`,
`run_video`, `run_audio`, `run_optimize`, `run_models`) depois de confirmar que nada mais o importa.

**Rationale**: auditoria rota-a-rota confirmou que toda capacidade que `cli.py` expunha já tem uma
rota HTTP equivalente e funcional hoje: `run_image`/`run_video` → `POST /jobs`/`POST /jobs/local`
(processados via `job_manager`/`worker_supervisor`/`upscaler.py`); `run_audio` → mesmo caminho com
`media_type=audio`; a subcomando `optimize` → `job_manager._run_compress_convert` (mesmo
`optimize_file` usado por ambos); `models download`/`models update` → `POST /components/{id}/install`
e `.../update` (`routes_components.py` → `component_manager.py`). Não há nenhuma funcionalidade
genuinamente exclusiva da CLI. Adicionalmente, `run_image`/`run_video`/`run_audio` expõem um
argumento `--model`/`--audio-engine` diretamente ao usuário — uma violação já existente de
Principle V (Models Are Internal) que a API já corrigiu com seleção baseada em perfil
(`profile_resolver.py`) e uma lista explícita `_FORBIDDEN_PARAM_KEYS = ('model', 'engine',
'checkpoint_id')` em `routes_jobs.py`. Remover `cli.py` não é só permitido por FR-002 — corrige uma
inconsistência de princípio que já existia antes desta feature.

**Alternativas consideradas**: manter `cli.py` como ferramenta interna de debug para
desenvolvedores — rejeitada porque FR-002 exige explicitamente sua remoção, e Principle IX proíbe
uma terceira camada de comando entre interface e API, mesmo que rotulada "só para devs".

## Decisão 5: testes do pacote raiz movem para `api/astros_upscale/tests/`

**Decisão**: os 7 arquivos hoje em `/tests/` (raiz do repo) — que testam `astros_upscale.*`
diretamente, sem passar por `cli.py` nem por nenhum outro serviço — movem para
`api/astros_upscale/tests/`, co-localizados com o pacote que testam.

**Rationale**: replica o padrão já usado pelos outros dois serviços (`astros_upscale_api/tests/` e
`astros_licensing_service/tests/`, cada um ao lado do seu próprio `app/`). Nenhum desses 7 arquivos
invoca `cli.py` ou faz subprocess para um binário — confirmado por grep — então nenhuma adaptação
de comportamento é necessária, só de caminho de import (que deixa de precisar de `sys.path` também,
pela mesma razão da Decisão 3).

## Decisão 6: `component_manager.py`'s `_REPO_ROOT` muda de significado (não só de valor)

**Decisão**: `_REPO_ROOT = APP_DIR.parent.parent.parent` em
`api/astros_upscale_api/app/core/component_manager.py` passa a
`_REPO_ROOT = APP_DIR.parent.parent` (2 níveis, não 3) depois da migração.

**Rationale**: hoje essa variável resolve para a raiz real do repositório (onde vive
`pyproject.toml`, usado para checar "existe um source checkout" antes de instalar as extras de
áudio via pip, e como alvo do `pip install <alvo>[audio]`). Depois da migração, `pyproject.toml`
passa a viver em `api/pyproject.toml`, não mais na raiz do repo — então o mesmo propósito
("apontar para onde o pyproject.toml com o extras group `[audio]` está") agora exige subir só 2
níveis a partir de `app/` (`astros_upscale_api` → `api`), não 3. É um detalhe sutil porque a
*forma* da expressão (`APP_DIR.parent.parent.parent`) parece igual à de `config.py`'s
`models_dir`, mas os dois têm que resolver para lugares diferentes depois da migração: `models_dir`
continua apontando para a raiz real do repo (onde `/models` permanece, por decisão explícita da
spec de não mover dados/artefatos), enquanto `_REPO_ROOT` de `component_manager.py` passa a
apontar para `api/`.

**Alternativas consideradas**: mover `pyproject.toml` para a raiz do repo mesmo depois da migração
(deixando `_REPO_ROOT` inalterado) — rejeitada porque contraria FR-001 (só duas pastas de
código-fonte de aplicação na raiz) e FR-002 (toda a lógica de backend, incluindo seu manifesto de
empacotamento, deve estar dentro de `api/`).

## Decisão 7: `apiProcess.ts` troca seu marcador de "raiz do repositório"

**Decisão**: `resolveRepoRoot()` em `interface/src/main/apiProcess.ts` deixa de procurar
`pyproject.toml` subindo diretórios (esse arquivo não existe mais na raiz do repo depois da
migração) e passa a procurar um diretório que contenha, simultaneamente, uma subpasta `api` e uma
subpasta `interface`.

**Rationale**: esse é exatamente o invariante que esta feature estabelece (FR-001) — um marcador
específico e estável para este monorepo, em vez de depender de um artefato Python que só existia
por acidente de onde o pacote raiz morava antes.

**Alternativas consideradas**: procurar por `.git` — rejeitada porque pode não existir em todo
contexto de build/empacotamento (checkout raso, artefato extraído sem histórico git); procurar por
`api/pyproject.toml` especificamente — rejeitada por ser mais frágil a uma futura mudança de
ferramenta de build Python (ex.: troca para `poetry`/`hatch` com outro nome de manifesto) do que
checar a existência das duas pastas que são o próprio contrato desta feature.

## Decisão 8: criar `Dockerfile` para o serviço de licenciamento

**Decisão**: adicionar `api/astros_licensing_service/Dockerfile`, espelhando o padrão já existente
em `api/astros_upscale_api/Dockerfile` (base `python:3.11-slim`, copia `requirements.txt` + `app/`
+ `run.py`, roda `uvicorn app.main:app --host 0.0.0.0 --port 8766`).

**Rationale**: a spec identifica explicitamente esse ponto em Edge Cases e pede que o plano decida.
Como Principle IX e FR-009 exigem que o serviço de licenciamento seja operável como processo
independente, e "independente" inclui "implantável sozinho", um serviço sem forma de
containerização própria é uma lacuna real para esse requisito — mesmo que hoje ele rode localmente
via `python run.py` em desenvolvimento. Não é escopo novo: é o mínimo necessário para tornar FR-009
verificável em um contexto real de deploy, não só teórico.

**Alternativas consideradas**: não criar Dockerfile algum, deixando o serviço sem forma de deploy
containerizado documentada — rejeitada por deixar FR-009/SC-007 sem uma forma prática de validação
em ambiente diferente do desenvolvimento local; criar também um `docker-compose.yml` orquestrando
os dois serviços — rejeitada explicitamente pela spec (Assumptions: não introduzir um
`docker-compose.yml` que não existia antes, só para preencher um exemplo).

## Resumo das mudanças de código não-triviais (além de "mover arquivo")

| Arquivo | Mudança |
|---|---|
| `api/pyproject.toml` (era `/pyproject.toml`) | Remover entry point `astros_upscale.cli:main` e a seção `[project.scripts]` correspondente, se existir só por causa dele. |
| `api/astros_upscale/` | Apagar `cli.py`. Resto do pacote inalterado internamente. |
| `api/astros_upscale_api/app/config.py` | Corrigir o comentário sobre "3 níveis" para refletir o novo caminho (`api/astros_upscale_api/app` em vez de `interface/astros_upscale_api/app`) — o valor computado não muda. |
| `api/astros_upscale_api/app/core/component_manager.py` | `_REPO_ROOT = APP_DIR.parent.parent.parent` → `APP_DIR.parent.parent` (ver Decisão 6). Remover o comentário/lógica que dependia de `astros_upscale` estar "ao lado" via sys.path — a mensagem de erro em `_pip_install_audio_extra` também precisa refletir o novo caminho relativo. |
| `api/astros_upscale_api/tests/conftest.py` | Remover os dois `sys.path.insert(...)` — o de `parents[3]` fica desnecessário (import normal do pacote instalado); o de `parent.parent` é reavaliado durante `/speckit-tasks` conforme como pytest resolve `rootdir` a partir do novo local. |
| `interface/src/main/apiProcess.ts` | `resolveRepoRoot()` (novo marcador, ver Decisão 7); `apiDir` de `join(repoRoot,'interface','astros_upscale_api')` para `join(repoRoot,'api','astros_upscale_api')`. |
| `scripts/mirror_models.py`, `scripts/benchmark_profiles.py` | Import de `astros_upscale.core`/`astros_upscale.utils.download` continua igual em nome de módulo — só passa a resolver via o pacote instalado a partir de `api/` em vez do antigo caminho de raiz (nenhuma mudança de linha de import é necessária se o pacote continuar se chamando `astros_upscale` e estiver instalado no mesmo venv — a confirmar durante tasks se `pip install -e ./api` for suficiente). |
| `api/astros_licensing_service/tools/build_package.py` | O caminho hardcoded para `astros_upscale_api/app/core/upscaler.py` (hoje relativo a partir de `interface/astros_licensing_service/tools/`) precisa refletir a nova posição relativa depois de ambos os serviços virarem irmãos dentro de `api/`. |
| `.github/workflows/tests.yml` | Os 3 jobs: `working-directory` e `sparse-checkout` paths atualizados (ver plan.md Project Structure). |
| `api/astros_upscale_api/Dockerfile` | Nenhuma mudança de conteúdo interno esperada (usa caminhos relativos ao seu próprio diretório) — só o contexto de build (onde o comando `docker build` é executado a partir) muda para `api/astros_upscale_api`. |
| `api/astros_upscale_api/pyinstaller.spec` | Revisar caminhos relativos internos (se referenciar `../../` para alcançar `astros_upscale` ou `models`, a profundidade pode mudar — a verificar linha a linha durante tasks). |

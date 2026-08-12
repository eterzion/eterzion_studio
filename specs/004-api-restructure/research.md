# Research: Consolidação estrutural de api/ por domínio

## Método

Antes de propor qualquer mapeamento de arquivo, cada um dos 39 arquivos-alvo (11 em
`astros_upscale/`, 26 em `astros_upscale_api/app/`, 12 em `astros_licensing_service/app/`) foi
inspecionado via grep de imports internos (`from .`, `from app.`, `from astros_upscale`) para
confirmar dependências cruzadas reais — não assumidas a partir do nome do arquivo. Isso determina
a ordem segura de consolidação: um módulo consolidado só pode ser escrito depois que todo módulo
do qual ele importa já existe (ou é consolidado simultaneamente, se a dependência for circular
dentro do mesmo grupo-alvo).

## Decisão 1 — Ordem de consolidação em `astros_upscale/`

**Dependências encontradas:**

- `core.py` → `.utils.download` (target: `media.py`)
- `audio.py` → `.media_engine` (`has_ffmpeg`, `run_ffmpeg`) (target: `media.py`)
- `face_enhance.py` → `.utils.download` (target: `media.py`)
- `optimize.py` → `.media_engine`, `.utils.image_io` (target: `media.py`) — já é domínio próprio,
  fica como está (FR-003), só atualiza o import
- `media_engine/temporal.py` → `.transcode` (interno ao próprio grupo `media.py`)
- `utils/video_io.py` → `..media_engine` (interno ao próprio grupo `media.py`)
- `content_type.py`, `hardware.py`: sem dependência interna
- `legacy_identifiers.py`: sem dependência interna; é importado só por `core.py:243`
  (`from .legacy_identifiers import removal_reason`, usado dentro de `resolve_weights()` para dar
  uma mensagem de erro quando um modelo removido é solicitado)

**Decisão:** `media.py` é escrito primeiro (nenhuma dependência em `processing.py`). `processing.py`
é escrito depois, e importa de `media.py` (não o contrário). `optimize.py` permanece intocado
exceto pelo import de `media.py`.

**`legacy_identifiers.py` (FR-019):** grep em todo o repositório (`astros_upscale`,
`astros_upscale_api`, `astros_licensing_service`, `interface/`) mostra que o único consumidor real
é `core.py:243`, um import lazy dentro de uma função — nenhum dado persistido, nenhum outro
serviço, nenhum cliente HTTP externo referencia esse módulo diretamente (ele nunca foi exposto
via API — é lógica de mensagem de erro interna). Com 40 linhas e um único consumidor interno,
**a condição de FR-019 está satisfeita: sua lógica é absorvida diretamente em `processing.py`**,
não mantida como arquivo autônomo.

**Tamanho final estimado:** `processing.py` ≈ 545+161+125+118+109+40 = 1098 linhas;
`media.py` ≈ 22+74+62+90+4+107+67+132 = 558 linhas. Ambos ficam abaixo do ponto em que deixariam
de ser lidos como um domínio coerente — nenhuma exceção de FR-020 é necessária aqui.

## Decisão 2 — Ordem de consolidação em `astros_upscale_api/app/`

**Dependências encontradas** (só as que cruzam os grupos-alvo propostos):

- `component_manager.py` (→ `processing.py`) importa `app.core.profile_resolver` e
  `app.core.license_registry.get_model_license` (→ `licensing.py`). **`processing.py` depende de
  `licensing.py`.**
- `isolated_worker.py` e `job_manager.py` (→ `jobs.py`) importam `app.core.upscaler`,
  `app.core.video_upscaler`, `app.core.audio_processor` (→ `processing.py`). **`jobs.py` depende
  de `processing.py`.**
- `worker_supervisor.py` (→ `jobs.py`) importa `app.core.secure_tempdir` (→ `security.py`).
  **`jobs.py` depende de `security.py`.**
- `protected_loader.py` e `install_identity.py` (→ `security.py`) só se importam entre si —
  dependência interna ao próprio grupo `security.py`.
- `license_gate.py` (→ `licensing.py`) importa `license_cache`, `offline_tolerance` — dependência
  interna ao próprio grupo `licensing.py`.
- As 7 rotas + `ws_progress.py` (→ `routes.py`) importam de praticamente todos os outros grupos
  (`component_manager`, `job_manager`, `license_gate`, `license_cache`, `protected_loader`,
  `install_identity`, `profile_resolver`, `upscaler`) e de `models/schemas.py` (→ `schemas.py`).
  **`routes.py` depende de tudo — é sempre o último a ser escrito.**
- `models/schemas.py`: nenhuma dependência interna — pode ser movido a qualquer momento.

**Ordem segura de escrita:** `schemas.py` (sem dependências) → `security.py` (sem dependência em
outro grupo-alvo) → `licensing.py` (sem dependência em outro grupo-alvo) → `processing.py`
(depende de `licensing.py`) → `jobs.py` (depende de `processing.py` e `security.py`) →
`routes.py` (depende de todos).

**Tamanhos finais estimados:** `routes.py` ≈ 618, `processing.py` ≈ 821, `jobs.py` ≈ 1004,
`licensing.py` ≈ 520, `security.py` ≈ 647, `schemas.py` ≈ 159 linhas. Todos dentro de um tamanho
que ainda se lê como um domínio único — nenhuma exceção de FR-020 é necessária.

**Consumidores externos a atualizar:** `app/api/routes_jobs.py` também importa diretamente de
`astros_upscale.content_type`, `astros_upscale.utils.image_io`, `astros_upscale.hardware`,
`astros_upscale.media_engine.probe`, `astros_upscale.media_engine.transcode` — todos esses
caminhos mudam para `astros_upscale.processing`/`astros_upscale.media` na Decisão 1. 28 dos 29
arquivos de teste em `astros_upscale_api/tests/` referenciam `app.core.*`/`app.api.*`/
`app.models.*` e precisam de atualização de import (mecânica, sem mudança de asserção).

## Decisão 3 — Ordem de consolidação em `astros_licensing_service/app/`

**Dependências encontradas:**

- `licensing.py` (→ `licensing.py`) importa `app.db` (→ `database.py`) e
  `app.payments.base.PaymentEvent` (→ `payments.py`). **`licensing.py` depende de `payments.py`.**
- `authorizations.py` (→ `licensing.py`) importa `app.db`, `app.licensing`, `app.packages`
  (→ `packages.py`), `app.service_identity` (→ `licensing.py`, interno). **`licensing.py`
  depende de `packages.py`** (via `latest_version`).
- `package_crypto.py` (→ `packages.py`) importa `app.service_identity.get_signing_key`
  (→ `licensing.py`, já que `service_identity.py` se funde em `licensing.py` por FR-011).
  **`packages.py` depende de `licensing.py`** (via `get_signing_key`).

**Dependência circular real, encontrada na revisão de `/speckit.analyze`:** as duas dependências
acima são de sentidos opostos — `licensing.py` → `packages.py` (via `authorizations.py`'s
`latest_version`) **e** `packages.py` → `licensing.py` (via `package_crypto.py`'s
`get_signing_key`), ambas hoje como `from app.X import Y` no topo do arquivo. Consolidar as duas
sem ajuste quebraria com `ImportError` (import circular no nível do módulo), qualquer que fosse a
ordem de escrita. **Resolução:** `get_signing_key` é usado em `package_crypto.py` só dentro do
corpo de `build_package()` — o import correspondente em `packages.py` MUST ser tornado tardio
(`from app.licensing import get_signing_key` dentro da função, não no topo do arquivo), seguindo o
mesmo padrão já usado no projeto para quebrar ciclo (`astros_upscale/core.py`'s
`from .legacy_identifiers import removal_reason` dentro de `resolve_weights()`). Com isso,
`packages.py` não tem mais dependência de módulo em `licensing.py` no momento do import, e
`licensing.py` → `packages.py` (via `latest_version`, usado por `authorizations.py`'s lógica,
que pode continuar como import de topo) resolve normalmente.
- `routes_webhooks.py` (→ `routes.py`) importa `app.licensing` e
  `app.payments.{mercadopago_provider,stripe_provider}` (→ `payments.py`).
  **`routes.py` depende de `licensing.py` e `payments.py`.**
- `payments/mercadopago_provider.py` e `payments/stripe_provider.py` importam
  `payments/base.PaymentEvent` — dependência interna ao próprio grupo `payments.py`.
- `db.py` só depende de `config.py` — sem dependência em outro grupo-alvo.

**Ordem segura de escrita (revisada após resolver o ciclo acima):** `database.py` (renomeado de
`db.py`, FR-015) → `payments.py` (sem dependência em outro grupo-alvo) → `packages.py` (sem
dependência de nível de módulo em `licensing.py`, já que `get_signing_key` passa a ser importado
de forma tardia dentro de `build_package()`) → `licensing.py` (depende de `packages.py`, para
`latest_version`, e de `payments.py`, para `PaymentEvent`) → `routes.py` (depende de
`licensing.py` e `payments.py`).

**Tamanhos finais estimados:** `licensing.py` ≈ 174+127+81 = 382, `packages.py` ≈ 37+67 = 104,
`payments.py` ≈ 0+17+79+62 = 158, `routes.py` ≈ 55+34+39+40 = 168 linhas. Todos pequenos o
suficiente para permanecer legíveis como um domínio único.

**Consumidor externo a atualizar:** `astros_licensing_service/tools/build_package.py` importa
`app.db.init_db`, `app.package_crypto.build_package`, `app.packages.save_package` — os três
caminhos mudam (`app.database`, `app.packages` para ambos os símbolos, já que
`package_crypto.py` se funde em `packages.py`).

## Decisão 4 — Contratos que devem permanecer preservados (payments)

`payments/base.py` define `PaymentEvent` e a interface implícita (métodos que
`StripeProvider`/`MercadoPagoProvider` implementam). A consolidação em `payments.py` MUST
preservar os três nomes exportados (`PaymentProvider`, `StripeProvider`, `MercadoPagoProvider`)
exatamente como estão hoje — nenhum consumidor (routes_webhooks → routes.py) muda sua forma de
uso, só o caminho de import.

## Decisão 5 — Arquivos de build/config a atualizar

Levantamento direto (grep) de referência a caminhos internos de `api/` fora do próprio código
Python:

- `api/astros_upscale_api/Dockerfile` — confirmado: `COPY app ./app` copia o diretório inteiro,
  sem referenciar nenhum arquivo individual. **Zero mudança necessária.**
- `api/astros_upscale_api/pyinstaller.spec` — confirmado: `hiddenimports` só lista módulos
  `uvicorn.*` (necessários porque o PyInstaller não segue imports dinâmicos do uvicorn), nenhuma
  referência a `app.core.*`/`app.api.*`/`app.models.*`. **Zero mudança necessária.**
- `api/astros_licensing_service/Dockerfile` — confirmado: mesmo padrão (`COPY app ./app`).
  **Zero mudança necessária.**
- `api/pyproject.toml`, `api/requirements.txt`, `astros_upscale_api/requirements*.txt`,
  `astros_licensing_service/requirements*.txt` — não referenciam módulos internos por nome
  (apenas pacotes PyPI). **Zero mudança esperada**, revisão final na Etapa de Limpeza confirma.
- `.github/workflows/tests.yml` — referencia diretórios (`api/astros_upscale_api`,
  `api/astros_licensing_service`), não arquivos individuais. **Zero mudança esperada.**
- `interface/src/main/apiProcess.ts` — resolve a raiz do repositório e o diretório `api/
  astros_upscale_api` para subir o processo (`resolveRepoRoot()`), não importa nenhum arquivo
  Python individual — é só um processo filho via `run.py`. **Zero mudança esperada.**
- `run.py` (ambos os serviços) — importam `app.main:app`, caminho que não muda.
- `astros_licensing_service/tools/build_package.py` — **precisa mudança** (ver Decisão 3):
  `app.db`→`app.database`, `app.package_crypto`→`app.packages`.

## Decisão 6 — Validação final

Sem suíte de testes de contrato dedicada (Constitution Princípio VIII — mock só em fronteira
externa real), a validação de "zero mudança de comportamento" (US2/SC-005) é feita por:

1. Contagem de testes coletados (`pytest --collect-only -q`) antes e depois, nas três subpastas —
   deve ser idêntica (SC-004).
2. Suíte completa rodando verde nas três subpastas depois da reorganização.
3. Import básico de cada serviço (`python -c "import app.main"` dentro de cada subpasta, com o
   `PYTHONPATH`/instalação editável configurados como em CI) — confirma que o grafo de import
   novo resolve sem erro circular (a ordem das Decisões 2 e 3 acima existe exatamente para evitar
   isso).
4. Onde Docker estiver disponível no ambiente, `docker build` de ambos os Dockerfiles como
   verificação adicional (não bloqueante se Docker não estiver disponível — registrar a
   limitação, não omitir, por FR consistente com a Constitution).

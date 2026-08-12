# Phase 1 Data Model: Consolidação estrutural de api/ por domínio

Esta feature é estrutural (reorganização/consolidação de código-fonte já existente) e **não
introduz, altera, nem remove nenhuma entidade de dado de domínio, schema de request/response, ou
formato de persistência**. Os schemas Pydantic movem de arquivo, mas seu formato (campos, tipos,
validações) não muda — ver `contracts/README.md` para a garantia de contrato.

## Mapeamento de caminho — `api/astros_upscale/`

| Origem | Destino |
|---|---|
| `core.py`, `audio.py`, `content_type.py`, `face_enhance.py`, `hardware.py`, `legacy_identifiers.py` | `processing.py` |
| `media_engine/probe.py`, `media_engine/temporal.py`, `media_engine/transcode.py`, `utils/download.py`, `utils/image_io.py`, `utils/video_io.py` | `media.py` |
| `optimize.py` | `optimize.py` *(inalterado, só import atualizado)* |

## Mapeamento de caminho — `api/astros_upscale_api/app/`

| Origem | Destino |
|---|---|
| `api/routes_jobs.py`, `api/routes_files.py`, `api/routes_components.py`, `api/routes_identity.py`, `api/routes_license.py`, `api/routes_preview.py`, `api/ws_progress.py` | `routes.py` |
| `core/upscaler.py`, `core/video_upscaler.py`, `core/audio_processor.py`, `core/component_manager.py`, `core/capacity.py` | `processing.py` |
| `core/job_manager.py`, `core/worker_supervisor.py`, `core/isolated_worker.py` | `jobs.py` |
| `core/license_gate.py`, `core/license_cache.py`, `core/license_registry.py`, `core/profile_resolver.py`, `core/offline_tolerance.py` | `licensing.py` |
| `core/protected_loader.py`, `core/secure_tempdir.py`, `core/integrity.py`, `core/dpapi.py`, `core/install_identity.py` | `security.py` |
| `models/schemas.py` | `schemas.py` *(pasta `models/` removida)* |
| `core/__init__.py`, `api/__init__.py` | *(removidos — os diretórios deixam de existir)* |

## Mapeamento de caminho — `api/astros_licensing_service/app/`

| Origem | Destino |
|---|---|
| `licensing.py`, `authorizations.py`, `service_identity.py` | `licensing.py` |
| `packages.py`, `package_crypto.py` | `packages.py` |
| `payments/base.py`, `payments/stripe_provider.py`, `payments/mercadopago_provider.py` | `payments.py` |
| `routes_activation.py`, `routes_authorizations.py`, `routes_packages.py`, `routes_webhooks.py` | `routes.py` |
| `db.py` | `database.py` |
| `payments/__init__.py` | *(removido — o diretório `payments/` deixa de existir)* |

## Ordem de escrita (por dependência real, ver `research.md` Decisões 1–3)

1. `astros_upscale/`: `media.py` → `processing.py` → `optimize.py` (import atualizado)
2. `astros_upscale_api/app/`: `schemas.py` → `security.py` → `licensing.py` → `processing.py` →
   `jobs.py` → `routes.py` → `main.py`/`config.py` (imports atualizados)
3. `astros_licensing_service/app/`: `database.py` → `payments.py` → `packages.py` →
   `licensing.py` → `routes.py` → `main.py`/`config.py` (imports atualizados). `packages.py` vem
   antes de `licensing.py` porque `get_signing_key` (destino: `licensing.py`) passa a ser
   importado de forma tardia dentro de `build_package()` em `packages.py`, para quebrar um ciclo
   real entre os dois módulos — ver `research.md` Decisão 3.

Nenhuma outra entidade requer documentação nesta fase.

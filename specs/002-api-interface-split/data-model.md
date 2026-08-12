# Phase 1 Data Model: Reorganização em duas camadas (api/ + interface/)

Esta feature é estrutural (reorganização de arquivos e imports) e **não introduz, altera, nem
remove nenhuma entidade de dado de domínio**. Os esquemas de dados existentes (licenças,
instalações, autorizações, pacotes no SQLite do serviço de licenciamento; jobs em memória na API
local; schemas Pydantic de requisição/resposta) permanecem exatamente como estão hoje — só seus
arquivos-fonte mudam de diretório.

A única coisa parecida com um "modelo de dados" relevante aqui é o mapeamento de migração em si,
registrado como referência para `/speckit-tasks`:

## Mapeamento de caminho (origem → destino)

| Origem | Destino |
|---|---|
| `/pyproject.toml` | `api/pyproject.toml` (sem o entry point da CLI) |
| `/requirements.txt` | `api/requirements.txt` |
| `/astros_upscale/` (exceto `cli.py`) | `api/astros_upscale/` |
| `/astros_upscale/cli.py` | *(removido)* |
| `/tests/*.py` (7 arquivos) | `api/astros_upscale/tests/*.py` |
| `/interface/astros_upscale_api/` | `api/astros_upscale_api/` |
| `/interface/astros_licensing_service/` | `api/astros_licensing_service/` |
| `/interface/astros_upscale_app/` | `interface/` (promovido, sem subpasta) |
| `/models/` (pesos ML) | inalterado — permanece dado, referenciado pelo novo caminho da API |
| `/scripts/{mirror_models,benchmark_profiles}.py` | inalterados de localização — só o import resolve via o pacote agora em `api/` |
| `/.github/workflows/tests.yml` | inalterado de localização — conteúdo atualizado (paths) |

Nenhuma outra entidade requer documentação nesta fase.

# NOTICE — SonicMaster (vendorizado)

Este diretório contém um subconjunto vendorizado, adaptado para inferência, do projeto
**SonicMaster**, mantido pelo AMAAI Lab.

- **Origem**: https://github.com/AMAAI-Lab/SonicMaster
- **Commit de origem**: `c4c0869c14bada6c5cb7d3decbcdc00e6a3050f5`
- **Licença**: Apache License 2.0 (texto completo em [LICENSE](LICENSE), preservado sem alteração)
- **Autores**: Jan Melechovsky, Ambuj Mehrish, Abhinaba Roy, Dorien Herremans (AMAAI Lab, Singapura)
- **Paper**: Melechovsky et al., "SonicMaster: Towards Controllable All-in-One Music Restoration
  and Mastering", arXiv:2508.03448, ICML 2026.

## O que foi vendorizado e por quê

O repositório de origem não é instalável via `pip` (sem `setup.py`/`pyproject.toml`) — é uma
coleção de scripts de pesquisa. Este projeto vendoriza só o necessário para **inferência**:

| Arquivo aqui | Origem | Adaptação |
|---|---|---|
| `model.py` | `model.py` | Cópia direta — define `TangoFlux` (arquitetura do modelo) |
| `utils.py` | `utils.py` | Cópia direta — utilitários de áudio/dataset usados por `model.py` |
| `configs/tangoflux_config.yaml` | `configs/tangoflux_config.yaml` | Cópia direta |
| `infer.py` | `infer_single.py` | Baseado no único script de inferência do repositório de origem
sem caminhos absolutos hardcoded — mantém a mesma interface de linha de comando
(`--ckpt --input --prompt --output`) |

**Não vendorizado** (deliberadamente, ver `docs/models/MODEL_LICENSES.md` e
`specs/006-audio-engine-masterizacao/research.md` Decisão 4): `train_ptload_inference.py`,
`preencode_latents_acce2.py` (código de treinamento — não usado em produção),
`inference_fullsong.py`/`inference_ptload_batch.py` (scripts de avaliação em lote com caminhos
absolutos dos autores, substituídos pela lógica de chunking própria em
`app/audio_engine/ai_provider.py`).

## Dependências e checkpoint

Este código roda num ambiente Python isolado (`astros_upscale_api/audio_worker_requirements.txt`),
separado do backend principal. O checkpoint do modelo (`model.safetensors`, ~3,29 GB) e o VAE
(`stabilityai/stable-audio-open-1.0`, licença Stability AI Community License — ver
`docs/models/MODEL_LICENSES.md` §3-bis) são baixados sob demanda, nunca commitados neste
repositório.

## Modificações feitas neste código

Nenhuma modificação de lógica foi feita em `model.py`/`utils.py` além da cópia direta. `infer.py`
é adaptado de `infer_single.py` do repositório de origem (já era o script de referência sem
caminhos hardcoded) — qualquer alteração futura deve ser documentada aqui.

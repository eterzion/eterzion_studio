# Quickstart — Audio Engine (validação ponta a ponta)

Reproduz as User Stories 1 (masterização automática) e 4 (funcionar sem GPU/IA) da spec. Assume
`api/` já configurado conforme `api/README.md` (venv raiz, `astros_upscale_api` rodando).

## Pré-requisitos

1. Venv raiz do projeto (`.venv/`) com as dependências normais do backend — **sem** as
   dependências do audio-worker.
2. Um venv separado para o audio-worker (Decisão 4/research.md), criado a partir de
   `api/astros_upscale_api/audio_worker_requirements.txt`, com o código vendorizado em
   `api/astros_upscale_api/vendor/sonicmaster/` disponível nesse venv.
3. `ASTROS_AUDIO_WORKER_PYTHON` apontando para o `python.exe` desse venv (variável de ambiente lida
   pela API principal — Decisão 3).
4. `HF_TOKEN` configurado no ambiente do audio-worker, com os termos do
   `stabilityai/stable-audio-open-1.0` aceitos na conta Hugging Face correspondente (o VAE é
   obrigatório em tempo de inferência — auditoria técnica, §5).
5. Uma faixa de música de teste, estéreo, alguns minutos de duração (para exercitar o chunking de
   música completa da User Story 3).

## Cenário 1 — Masterização automática, caminho feliz (User Story 1)

```bash
curl -X POST http://127.0.0.1:8765/jobs/local \
  -H "Content-Type: application/json" \
  -d '{
    "media_request": {
      "media_type": "audio",
      "operation": "enhance",
      "content_type_override": "music",
      "input_path": "C:/caminho/para/faixa_teste.wav",
      "audio_mode": "auto_master",
      "ai_strength": 50
    }
  }'
```

**Esperado**:
- Job criado e processado sem erro.
- `GET /jobs/{id}` (ou o WebSocket de progresso) mostra `stage` passando por análise, DSP, e —
  se a faixa de teste tiver algum problema real detectável — restauração por IA, antes de
  masterização/limitação/normalização.
- `audio_analysis.integrated_lufs` do resultado final dentro do alvo configurado; `clipping_ratio`
  em 0 ou próximo de 0.
- Se a faixa de teste NÃO tiver nenhum problema que justifique IA: o log/estágio nunca deve mostrar
  uma etapa de restauração por IA (confirma FR-002 — sem envio incondicional).

## Cenário 2 — Fallback sem provedor de IA (User Story 4)

Repita o Cenário 1 com `ASTROS_AUDIO_WORKER_PYTHON` **não configurado** (ou apontando para um
caminho inválido), usando uma faixa de teste com um defeito conhecido que normalmente acionaria a
IA (ex. clipping severo introduzido deliberadamente).

**Esperado**:
- O job ainda completa — usando só DSP — em vez de falhar ou travar.
- `error`/`error_category` do job permanecem vazios (não é tratado como falha — é o comportamento
  de fallback esperado, FR-020).
- O resultado tem o clipping reduzido pelo DSP disponível (mesmo que não tão bem quanto a IA
  faria), nunca uma cópia inalterada do original.

## Cenário 3 — Rejeição pelo Quality Guard (validação de FR-008)

Requer um provedor de IA real configurado e um input adversarial (ou um `ai_strength` alto numa
faixa onde a IA plausivelmente introduz artefato). Se `quality_verdict.outcome` vier como
`"rejected"` ou `"reduced"` em algum teste, confirme que o `output_path` final não é a saída bruta
do provedor de IA — comparando hash/tamanho contra o resultado intermediário salvo em
`stages_output_paths['restored']` antes da correção DSP.

## Cenário 4 — Compatibilidade retroativa (nenhum campo novo)

```bash
curl -X POST http://127.0.0.1:8765/jobs/local \
  -H "Content-Type: application/json" \
  -d '{
    "media_request": {
      "media_type": "audio",
      "operation": "enhance",
      "content_type_override": "music",
      "input_path": "C:/caminho/para/faixa_teste.wav"
    }
  }'
```

**Esperado**: comportamento idêntico ao pipeline de áudio já existente hoje — sem os campos novos
no payload de resposta. Este cenário deve continuar passando sem alteração durante toda a
implementação (é o teste de regressão mais importante desta feature).

## Verificações finais antes de considerar a feature validada

- `pytest` da suíte de `astros_upscale_api` continua 100% verde, incluindo os testes já existentes
  de `test_audio_processor.py` (Cenário 4 acima é a versão manual desse mesmo contrato).
- `pip install astros_upscale[audio]` (extra corrigida) instala `audiosronnx` +
  `astros-audio-enhance` sem erro — confirma que o bug real de "Melhoria de voz" quebrada
  (encontrado nesta sessão) foi corrigido como efeito colateral necessário.
- Medição real de VRAM/tempo de inferência do SonicMaster registrada em algum lugar rastreável
  (research.md sinalizou que isso não é assumido, é medido) antes de qualquer texto de UI prometer
  tempo/performance.

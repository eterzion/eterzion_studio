# Phase 1 Quickstart: Unified Media Processing

**Date**: 2026-08-08
**Purpose**: roteiro executável para provar que a feature funciona ponta a ponta, mapeado às User
Stories da spec. Não é um plano de testes completo (isso é `tasks.md` + suíte real) — é a
demonstração mínima e verificável de que cada fatia entrega o que promete.

## Pré-requisitos

- Repositório com `.venv` configurado (já existe: `interface/astros_upscale_api/.venv` equivalente
  no root, conforme sessões anteriores)
- FFmpeg instalado **em build LGPL** — verificar antes de tudo:
  ```bash
  ffmpeg -version | grep -o -- '--enable-gpl'
  ```
  Se retornar algo, a build atual é GPL e precisa ser trocada antes de qualquer empacotamento
  (Constitution, Licensing and Distribution Constraints) — mas não bloqueia validação local em
  desenvolvimento.
- `astros_licensing_service` rodando localmente com uma licença de teste ativa (User Story 7 exige
  isso para qualquer outro cenário funcionar, já que o controle de licença está ativo)

## US1 — Melhorar imagem sem ver modelo

```bash
curl -X POST http://127.0.0.1:8765/jobs \
  -H "Content-Type: application/json" \
  -d '{"media_type":"image","operation":"enhance","scale":"2x","profile":"fast","input_path":"inputs/0014.jpg"}'
```

**Esperado**: resposta 201 com um `Job` cujo `content_type_detected` é `photo`, sem nenhum campo
`model`/`engine` na resposta. Repetir com `profile:"quality"` e comparar `finished_at - started_at`
— Qualidade deve levar mais tempo (SC-004). Comparar visualmente as duas saídas — Qualidade não
deve ser pior (SC-005/SC-007).

**Falha aceitável de detecção**: se a heurística de R1 classificar errado, `PATCH
/jobs/{id}/params` com `content_type_override` corrige antes de processar (FR-096).

## US2 — Converter e comprimir sem IA

```bash
curl -X POST http://127.0.0.1:8765/jobs \
  -d '{"media_type":"image","operation":"convert","input_path":"inputs/00003.png","output_target":{"format":"webp"}}'
```

**Esperado**: nenhum perfil no request é aceito nem exigido para esta combinação (FR-005) — se a
API pedir `profile`, é um defeito. Verificar via log/instrumentação que nenhum modelo de IA foi
carregado para esta operação (FR-029).

## US3 — Melhorar vídeo preservando o que importa

```bash
curl -X POST http://127.0.0.1:8765/jobs \
  -d '{"media_type":"video","operation":"enhance","scale":"2x","profile":"fast","input_path":"inputs/video/<arquivo-com-audio>.mp4"}'
```

**Esperado**: se o vídeo tiver faixas/legendas extras, a criação retorna o estado de confirmação
pendente antes de enfileirar (FR-081/FR-082) — testar tanto confirmando quanto **não** confirmando
(job não deve iniciar sem `secondary_elements_ack`). Após concluído, comparar com `ffprobe`:
`duration`, `r_frame_rate`, contagem de canais de áudio do original vs. resultado — devem ser
idênticos (FR-017, SC-006).

## US4 — Melhorar áudio

```bash
# fala
curl -X POST http://127.0.0.1:8765/jobs \
  -d '{"media_type":"audio","operation":"enhance","profile":"balanced","input_path":"<gravacao_com_ruido>.wav"}'

# música
curl -X POST http://127.0.0.1:8765/jobs \
  -d '{"media_type":"audio","operation":"enhance","profile":"balanced","input_path":"<faixa_musical>.wav"}'
```

**Esperado**: `content_type_detected` diferencia `speech` de `music` (R2). Medir ruído/loudness
antes e depois (FR-019/FR-020, SC-007) — redução de ruído mensurável, volume no alvo definido,
duração e contagem de canais inalteradas.

## US5 — Funcionar no hardware que a pessoa tem

Rodar a mesma requisição de US1 em duas máquinas (ou simular ausência de GPU via variável de
ambiente que force `gpu_present=false` no `HardwareCapability`, se essa opção de teste existir).

**Esperado**: ambas concluem; `capacity_check` e os parâmetros de execução aplicados diferem entre
elas (SC-009/SC-023). Testar um arquivo deliberadamente maior que a capacidade calculada — deve
recusar **antes** de processar, com explicação do recurso insuficiente (FR-079, SC-024).

## US6 — Acompanhar e cancelar

```bash
curl -X DELETE http://127.0.0.1:8765/jobs/{id}
```

**Esperado**: em até 5 segundos o processo do worker é confirmadamente encerrado (verificar via
`tasklist`/`ps`, não apenas o status HTTP) — SC-013.

## US7 — Licença

```bash
curl http://127.0.0.1:8765/license/status
```

Sequência: ativar → processar (deve funcionar) → derrubar rede → processar de novo (deve
funcionar, dentro da tolerância) → simular licença revogada no serviço → tentar processar (deve
bloquear com FR-060, mas qualquer resultado já salvo em disco continua acessível — SC-019).

## Verificação de conformidade transversal (roda contra qualquer cenário acima)

- [ ] Nenhuma resposta HTTP contém `model`, `checkpoint`, `engine_ref` (SC-002) — exceto
      `GET /components/{id}/details`
- [ ] Nenhum tráfego de rede carrega o conteúdo do arquivo de mídia (SC-020) — inspecionar com
      proxy/mitmdump durante um processamento completo
- [ ] Após um job concluir, nenhuma cópia utilizável da lógica de execução protegida permanece em
      disco fora do processo já encerrado (SC-021)

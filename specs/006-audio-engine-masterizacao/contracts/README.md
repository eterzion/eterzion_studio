# Contrato — Audio Engine

Nenhuma rota nova. Este trabalho estende `POST /jobs/local` (e por consequência `GET /jobs/{id}`,
o WebSocket de progresso, e `POST /jobs/{id}/export`) exatamente como já existem hoje — a extensão
é aditiva ao schema (Decisão 2 de research.md), preservando 100% do comportamento atual quando os
campos novos não são enviados.

## `POST /jobs/local` — campos novos em `MediaRequest`

`MediaRequest` usa `extra='forbid'` (schemas.py) — os campos novos precisam ser declarados
explicitamente nela, não podem ser passados como chaves soltas.

```jsonc
POST /jobs/local
{
  "media_request": {
    "media_type": "audio",
    "operation": "enhance",
    "content_type_override": "music",     // já existente
    "input_path": "C:/musicas/faixa.wav",  // já existente

    // ---- novos, ambos opcionais ----
    "audio_mode": "auto_master",           // 'enhance' (default) | 'auto_master' | 'restore' | 'restore_master'
    "ai_strength": 50                      // 0-100, default 50 quando audio_mode != 'enhance'
  },
  "adjustments": {}
}
```

**Regra de compatibilidade**: se `audio_mode` for omitido (ou `"enhance"`), a requisição é
processada exatamente como hoje — mesmo pipeline, mesmos campos de resposta. `ai_strength` só tem
efeito quando `audio_mode` é `auto_master`/`restore`/`restore_master`.

**Validação**: `audio_mode`/`ai_strength` só são aceitos quando `media_type='audio'` e o
`content_type` resolvido é `'music'` — presentes numa requisição de fala/imagem/vídeo, retornam
422 (mesma política de "a API só aceita intenção", Princípio V — não introduz um novo jeito de
selecionar implementação, só o modo de operação de mastering).

## `GET /jobs/{id}` — campos novos em `JobStatus`

```jsonc
{
  "id": "job_xxx",
  "status": "done",
  "media_type": "audio",
  "operation": "enhance",
  "content_type_detected": "music",
  // ---- já existente ----
  "output_path": "C:/.../faixa_masterizada.wav",

  // ---- novos, presentes só quando audio_mode != 'enhance' foi usado ----
  "audio_analysis": {                 // resumo de AudioAnalysisReport (data-model.md), medido no resultado final
    "integrated_lufs": -14.2,
    "true_peak_db": -1.1,
    "dynamic_range_db": 8.4,
    "clipping_ratio": 0.0
  },
  "quality_verdict": {                // presente só se a etapa de IA rodou
    "outcome": "accepted",            // 'accepted' | 'reduced' | 'rejected'
    "reasons": []
  }
}
```

**Compatibilidade**: jobs com `audio_mode='enhance'` (ou omitido) — incluindo todo job de imagem,
vídeo e fala — **não ganham** esses campos no payload; o schema de resposta para eles é
byte-a-byte o mesmo de hoje (campos opcionais ausentes, não `null` forçado onde não fazia sentido
antes).

## WebSocket de progresso — sem mudança de contrato

As mensagens de progresso (`stage`, `progress`) continuam com o mesmo formato. Novos valores de
`stage` são apenas novos textos possíveis dentro do campo `stage: str` já existente (ex.
"Restaurando com IA", "Validando qualidade") — não é uma mudança de schema, é uma mudança de
conteúdo dentro de um campo que já era texto livre.

## Sem rota nova para consultar `AudioAnalysisReport`/`ProblemDetection` completos

A spec não pede uma tela de detalhamento técnico de métricas — os campos resumidos em `JobStatus`
acima bastam para a UI de comparação A/B (User Story 2/3). O relatório completo (todos os campos
de `data-model.md`) permanece interno ao `audio_engine/`, consistente com o Princípio V (modelos e
detalhes técnicos não são expostos por padrão).

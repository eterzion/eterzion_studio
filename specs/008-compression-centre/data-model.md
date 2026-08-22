# Phase 1 — Modelo de dados: Central de Compressão

**Feature**: `008-compression-centre` · **Data**: 2026-08-21

Formas de dados, não implementação. Cada entidade diz o que representa, o que a torna válida, e —
onde importa — o que **não** carrega e por quê.

---

## Status: um enum, um lugar

FR-049 e §68 exigem estados padronizados. Hoje `jobs.py` usa
`pending · pending_confirmation · queued · processing · done · error · cancelled`, e a solicitação
propôs um conjunto parecido mas diferente (`idle · queued · analyzing · processing · completed ·
failed · cancelled`).

**Dois conjuntos parecidos são pior que dois conjuntos diferentes** — a diferença passa
despercebida até alguém comparar contra a string errada.

**Decisão:** manter os nomes existentes e **acrescentar `analyzing`**. Renomear `done` para
`completed` e `error` para `failed` tocaria o histórico, a API, o WebSocket e o renderer inteiro,
sem ganhar nada além de outra palavra.

```
pending → analyzing → queued → processing → done
                                    ↓
                            error | cancelled
```

`analyzing` é a janela entre importar e poder estimar: sondagem de metadados e, para imagem, a
codificação da amostra. É estado próprio porque é o único em que a interface pode mostrar
progresso mas não pode mostrar estimativa.

---

## MediaFile

Um arquivo importado, antes de qualquer configuração.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | identificador interno | Nunca o caminho. Princípio XIII |
| `display_name` | texto | Nome, para a pessoa ler |
| `media_kind` | `image · video · audio · animation` | **Detectado pelo conteúdo**, não pela extensão (FR-007) |
| `size_bytes` | inteiro | Tamanho de origem |
| `metadata` | `MediaMetadata` | O que a sondagem obteve |

**Não carrega o caminho do sistema de arquivos para fora da API.** É a mesma regra que
`MediaHandleResponse` já segue.

**`animation` é um tipo próprio, não "imagem com quadros".** Um GIF de um quadro é `image` — a
distinção é ter mais de um quadro, não a extensão.

---

## MediaMetadata

O que a sondagem conseguiu. **Campo ausente é ausente** (FR-010): `None`, nunca `0`, nunca um
padrão que pareça medido.

| Campo | Aplica-se a |
|---|---|
| `width`, `height` | imagem, vídeo, animação |
| `duration_seconds` | vídeo, áudio, animação |
| `frame_rate`, `frame_count` | vídeo, animação |
| `video_codec`, `video_bitrate` | vídeo |
| `audio_codec`, `audio_bitrate`, `sample_rate`, `channels` | vídeo, áudio |
| `has_alpha`, `color_count` | imagem, animação |
| `has_metadata` | imagem — se há EXIF/ICC a preservar ou remover |

`0` num campo de bitrate é uma afirmação sobre a mídia. `None` é uma afirmação sobre a sondagem.
Confundir as duas faz a estimativa mentir com confiança.

---

## CompressionSettings

Polimórfico por `media_kind`. Cada variante carrega **só o que faz sentido** — não um objeto largo
com metade dos campos inertes, porque campo inerte é campo que alguém preenche por engano.

### ImageCompressionSettings
`output_format` (`keep` ou um dos suportados) · `quality` 0–100 · `lossless` · `resize` ·
`metadata_policy` · e, por formato: nível de compressão (PNG), chroma subsampling e progressivo
(JPEG), effort (WebP), speed e chroma (AVIF).

### VideoCompressionSettings
`container` · `video_codec` (com `auto`) · `rate_mode` (`quality` ou `bitrate`) · `crf` ou
(`target_bitrate`, `max_bitrate`, `cbr`) · `resolution` · `frame_rate` · `encoding_preset` ·
`encoder_preference` (`auto · cpu · gpu`) · `audio` (`VideoAudioSettings`).

### AudioCompressionSettings
`output_format` · `codec` (com `auto`) · `bitrate_mode` (`cbr · vbr`) · `bitrate` ou `quality` ·
`sample_rate` (com `original`) · `channels` (com `original`).

### AnimationCompressionSettings
`output_format` (`gif · webp · mp4 · webm`) · `quality` · `resize` · `frame_rate` · `max_colors` ·
`dither` · `optimize_frames`.

**Regra transversal:** todo campo técnico aceita `auto`/`original`, e `auto` **é o padrão**
(FR-039). O modo Básico não escolhe outra coisa — ele simplesmente não mostra esses campos.

### ResizeSettings
`mode` (`keep · preset · exact · percent`) · `width` · `height` · `preserve_aspect` ·
`prevent_upscale`.

`prevent_upscale` é padrão **ligado**: compressão que aumenta a resolução é quase sempre engano de
digitação.

### MetadataPolicy
`preserve_all · essential_only · strip_exif · strip_gps · strip_comments · strip_icc · strip_all`

Padrão: `essential_only` — preserva orientação e perfil de cor (sem os quais a imagem **muda**
visivelmente) e descarta GPS, comentários e o resto do EXIF. FR-028 pede privacidade sem degradar,
e essa é a única combinação que faz as duas coisas.

---

## CompressionPreset

| Campo | Regra |
|---|---|
| `id` | Estável entre reinícios |
| `name` | Do usuário, ou chave i18n para os internos |
| `media_kind` | Um preset pertence a **um** tipo de mídia (FR-014) |
| `origin` | `builtin · platform · user` |
| `settings` | `CompressionSettings` da variante correspondente |

Presets `builtin` e `platform` vêm de configuração (FR-012/FR-015) e são somente leitura —
duplicar produz um `user`. Isso evita a pergunta "o que acontece com meus presets numa
atualização".

---

## CompressionTarget

O modo tamanho-alvo (FR-016).

`value` · `unit` (`KB · MB · GB`) · `resolved` (`CompressionSettings` derivadas) ·
`feasibility` (`ok · below_floor · not_estimable`).

**`below_floor` é resposta, não erro.** Significa que o alvo é atingível apenas produzindo algo
inutilizável, e FR-020 exige dizer isso antes de processar.

---

## CompressionEstimate

`original_bytes` · `estimated_bytes` · `estimated_saving_bytes` · `reduction_ratio` ·
`confidence` (`measured_sample · derived · rough`) · `assumptions`.

**`confidence` existe porque as três mídias não são igualmente previsíveis.** Imagem por amostra
codificada é `measured_sample`; vídeo por bitrate × duração é `derived`; vídeo em CRF sem tabela
calibrada é `rough`. Apresentar os três com a mesma cara seria mentir sobre dois deles.

---

## CompressionJob

Estende o job existente. Campos novos: `settings`, `estimate`, `target`, `preset_id`.

Reusa integralmente: `id`, `status`, `progress`, `stage`, `queue_position`, `error`,
`error_category`, `created_at`, tempos de processamento.

---

## CompressionResult

`output_size_bytes` · `saving_bytes` · `reduction_ratio` · `elapsed_seconds` ·
`grew` (booleano) · `applied` (`AppliedSettings`).

**`grew` é campo, não cálculo do renderer.** FR-023 exige dizer quando o resultado ficou maior, e
uma redução negativa apresentada como economia é exatamente o tipo de defeito que passa por
formatação.

`applied` é o que **de fato** foi usado — codec, encoder, bitrate real. Alimenta os "Detalhes
técnicos" (§48) e o histórico. É informativo e, no modo Básico, não é exibido.

---

## EncoderCapability

`value` · `available` · `unavailable_reason` (chave, nunca nome de biblioteca) ·
`requires_hardware`.

Mesma forma que `ContainerAvailability` e `ImageFormatAvailability` já têm. `requires_hardware`
existe para a interface poder explicar *por que* H.264 está indisponível sem nomear NVENC.

---

## CompatibilityMatrix

Entrada declarada: `container` → codecs de vídeo permitidos × codecs de áudio permitidos.

**Duas perguntas separadas, e a separação é o ponto** (Decisão 6 da pesquisa): a matriz responde
"é legal?"; a sonda responde "esta máquina consegue?". A interface só oferece o que passa nas duas.

---

## ExportConfiguration

`directory` · `naming_pattern` · `conflict_policy` (`overwrite · copy · rename · skip`) ·
`apply_to_all`.

`naming_pattern` aceita `{filename}`, `{quality}`, `{resolution}`, `{codec}`. Padrão:
`{filename}_compressed`.

**`overwrite` nunca se aplica ao arquivo de origem** (FR-059). Sobrescrever *outro* arquivo é
escolha da pessoa; sobrescrever a origem é o que o Princípio XV proíbe, e é decidido no backend,
não confiado ao cliente.

---

## HistoryEntry

`name` · `date` · sizes · `reduction_ratio` · `format` · `codec` · `resolution` · `preset_name` ·
`elapsed_seconds` · `settings_snapshot`.

`settings_snapshot` é o que permite "repetir compressão" (FR-063) sobreviver a mudanças de preset:
repetir usa o que foi usado, não o que o preset diz hoje.

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# `analyzing` é a janela entre importar e poder estimar: sondagem de metadados
# e, para imagem, a codificação da amostra. É estado próprio porque é o único em
# que a interface pode mostrar progresso e não pode mostrar estimativa.
#
# Os nomes existentes NÃO foram renomeados para o conjunto que a solicitação
# propunha (`completed`/`failed`): renomear tocaria histórico, API, WebSocket e
# renderer inteiro sem ganhar nada além de outra palavra, e dois conjuntos
# parecidos são piores que dois diferentes — a diferença passa despercebida até
# alguém comparar contra a string errada.
JobStatusValue = Literal['pending', 'pending_confirmation', 'analyzing', 'queued', 'processing', 'done', 'error', 'cancelled']
ErrorCategory = Literal[
    'out_of_memory', 'corrupted_input', 'model_failure', 'disk_full',
    'hardware_insufficient', 'license_invalid', 'download_failed',
]
ConflictMode = Literal['overwrite', 'rename', 'ask']

# --- Unified Media Processing (data-model.md / contracts/api.md) ---
MediaType = Literal['image', 'video', 'audio']
Operation = Literal['enhance', 'compress', 'convert']
Profile = Literal['fast', 'balanced', 'quality']
ContentType = Literal[
    'photo', 'pixel_art', 'no_model', 'anime_image', 'real_video', 'anime_video', 'speech', 'music'
]
InstallState = Literal['not_installed', 'installing', 'installed', 'update_available']
LicenseState = Literal[
    'active', 'offline_tolerance', 'offline_expiring', 'blocked', 'not_activated', 'not_configured'
]
LicenseStatusValue = Literal['approved', 'approved_conditional']
# specs/006-audio-engine-masterizacao — audio_mode is additive: None/'enhance'
# preserves today's single-pass music/speech pipeline exactly (contracts/README.md
# Decisão 2). Only 'auto_master'/'restore'/'restore_master' route through
# app.audio_engine.mastering.MasteringEngine.
AudioMode = Literal['enhance', 'auto_master', 'restore', 'restore_master']
QualityVerdictOutcome = Literal['accepted', 'reduced', 'rejected']


class CustomSize(BaseModel):
    width: int
    height: int


class Adjustments(BaseModel):
    denoise: int = Field(default=50, ge=0, le=100)
    deblur: int = Field(default=0, ge=0, le=100)
    detail_recovery: int = Field(default=0, ge=0, le=100)
    face_correction: bool = False
    face_recovery_strength: int = Field(default=80, ge=0, le=100)
    denoise_filter_enabled: bool = False
    denoise_filter_strength: int = Field(default=45, ge=0, le=100)


class OutputTarget(BaseModel):
    """Where/how the result is written — format, directory, name, conflict policy."""
    format: str
    directory: str | None = None
    filename: str | None = None
    conflict: ConflictMode = 'rename'


class MediaRequest(BaseModel):
    """The processing-intent contract (contracts/api.md `POST /jobs`, data-model.md
    MediaRequest). `extra='forbid'` is what makes FR-011 real: a `model`/`engine`/
    `checkpoint_id` field (or any other unknown field) is a 422 validation error,
    never a silently-ignored extra key — the API only ever accepts intent, the
    implementation is resolved internally by profile_resolver.py."""
    model_config = ConfigDict(extra='forbid')

    media_type: MediaType
    operation: Operation
    # '1x' is the Imagem screen's Original mode: keep (or reduce) the size and
    # skip the model entirely, while the post-processing filters below still
    # apply. It is not a model factor — no engine is resolved for it.
    scale: Literal['1x', '2x', '4x'] | None = None
    profile: Profile | None = None
    content_type_override: ContentType | None = None
    input_path: str
    output_target: OutputTarget | None = None
    secondary_elements_ack: bool = False
    device: str = 'auto'
    custom_size: CustomSize | None = None
    quality: int | None = Field(default=None, ge=0, le=100)  # compress/convert only (FR-027)
    # audio_mode/ai_strength: music-only (content_type='music'), both optional —
    # omitted or 'enhance' means "exactly today's behaviour", byte for byte
    # (specs/006-audio-engine-masterizacao contracts/README.md).
    audio_mode: AudioMode | None = None
    # specs/007-video-editor-player — the editor's settings, applied to the
    # upscaled result as a second pass. Optional and neutral by default, so a
    # request that omits it behaves exactly as before, byte for byte. Video
    # only: the image path already applies its adjustments inside the model
    # pass, and a second mechanism would be two ways to do one thing.
    edits: 'VideoEditSet | None' = None
    ai_strength: int | None = Field(default=None, ge=0, le=100)


class LocalJobRequest(BaseModel):
    """Body for POST /jobs/local — the same local-desktop convenience as
    ExportRequest.output_dir, but for input: skips the multipart upload and points
    the job straight at a file already on disk (API and client on the same machine).
    `media_request.input_path` IS the path — there is no separate top-level field."""
    media_request: MediaRequest
    adjustments: Adjustments = Adjustments()


# A lista permitida de formatos, num lugar só: o pedido e a resposta de
# disponibilidade têm que falar do mesmo conjunto, ou a interface oferece o que
# a rota recusa.
ExportFormat = Literal['png', 'jpg', 'jpeg', 'tiff', 'webp']


class ExportRequest(BaseModel):
    """Body for POST /jobs/{id}/export. Only re-encodes the already-upscaled master
    result (see job_manager._process_job) — never re-runs the model, so switching
    format/quality/destination after a job is done is always fast."""
    format: ExportFormat = 'png'
    quality: int = Field(default=90, ge=1, le=100)
    output_dir: str | None = None  # None = same folder as the original input
    filename: str | None = None  # None = the source's own name, "{name}.{ext}"
    conflict: ConflictMode = 'rename'


class SizeMeta(BaseModel):
    # width/height are None for audio and for any compress/convert result —
    # those operations don't produce a pixel-dimensioned output (FR-025/FR-028).
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None


class CapacityCheck(BaseModel):
    fits: bool
    estimated_duration: float | None = None
    limiting_resource: str | None = None


class AudioAnalysisSummary(BaseModel):
    """Resumo público de audio_engine.analyzer.AudioAnalysisReport
    (contracts/README.md) — só os campos úteis para uma UI de métricas, não
    o relatório interno completo (Princípio V — sem detalhe técnico por
    padrão)."""
    integrated_lufs: float
    true_peak_db: float
    dynamic_range_db: float
    clipping_ratio: float


class QualityVerdictSummary(BaseModel):
    outcome: QualityVerdictOutcome
    reasons: list[str] = []


class CompressionResultSummary(BaseModel):
    """O que de fato saiu, medido no arquivo (FR-022).

    Repetir a estimativa aqui seria a mentira mais fácil de cometer nesta spec:
    ela já existe, tem o mesmo formato, e ninguém perceberia até o arquivo no
    disco não bater com o que a tela afirma.
    """
    original_bytes: int
    output_size_bytes: int
    saving_bytes: int
    reduction_ratio: float | None = None
    # Campo, não cálculo do cliente (FR-023): uma redução negativa apresentada
    # como economia é o tipo de defeito que passa por formatação.
    grew: bool = False
    elapsed_seconds: float = 0.0
    # O que de fato foi aplicado — formato, codec, e as opções resolvidas. A
    # comparação de áudio (FR-056) precisa disto para dizer "128 kbps" em vez de
    # repetir o que a pessoa pediu: pedir e aplicar divergem sempre que o
    # `auto` resolve, e mostrar o pedido como resultado seria a mesma confusão
    # entre estimativa e medição que o FR-022 trata.
    applied: dict[str, Any] | None = None


class JobStatus(BaseModel):
    id: str
    status: JobStatusValue
    media_type: MediaType = 'image'
    operation: Operation = 'enhance'
    content_type_detected: ContentType | None = None
    progress: int = 0
    stage: str | None = None
    eta_seconds: int | None = None
    queue_position: int | None = None
    input_file: str
    output_path: str | None = None
    error: str | None = None
    error_category: ErrorCategory | None = None
    # specs/008 (FR-065) — a razão em chave, para a interface traduzir, e a saída
    # bruta da ferramenta separada. Juntar as duas transferiria para a pessoa um
    # trabalho de diagnóstico que é nosso: "error code: -22 (Invalid argument)"
    # não diz a ninguém o que fazer a seguir.
    error_reason: str | None = None
    error_detail: str | None = None
    capacity_check: CapacityCheck | None = None
    created_at: str
    processing_started_at: str | None = None
    processing_ended_at: str | None = None
    source_meta: SizeMeta | None = None
    output_meta: SizeMeta | None = None
    # Present only when audio_mode != 'enhance' was used — absent (not null)
    # for every image/video/speech job and for the default music pipeline,
    # so their response payload is byte-for-byte unchanged (contracts/README.md).
    audio_analysis: AudioAnalysisSummary | None = None
    quality_verdict: QualityVerdictSummary | None = None
    # specs/008 — os números **medidos** da Central. Ausente (não nulo) em todo
    # job que não é de compressão, para que a resposta dos demais continue byte
    # a byte a mesma.
    compression: CompressionResultSummary | None = None


class ModelInfo(BaseModel):
    name: str
    category: str
    scale: int
    description: str


class Component(BaseModel):
    """`GET /components` — capability-first listing, never a technical name
    (FR-063/FR-064). No selection affordance: only install/update/remove."""
    id: str
    capability_label: str
    size_mb: int
    install_state: InstallState
    update_available: bool = False
    # False = a capacidade existe mas esta versao do app nao a instala (hoje, a
    # musica). A tela mostra "Em breve" sem botoes em vez de oferecer "Instalar"
    # e so' descobrir a recusa (422 `not_available_in_app`) depois do clique.
    available: bool = True


class ComponentDetails(Component):
    """`GET /components/{id}/details` — the one opt-in place technical detail is
    ever shown (FR-065/FR-066)."""
    technical_name: str
    version: str
    provenance: str
    license: str
    # Por que a última instalação em segundo plano falhou. Fica AQUI, e não em
    # `Component`: a mensagem carrega saída de pip e caminhos de arquivo, que é
    # exatamente o detalhe técnico que a listagem não pode expor. A tela mostra
    # que a instalação não completou; quem quiser o motivo abre os detalhes.
    error: str | None = None
    # Quando a falha foi de download: o motivo (`rate_limited`, `network`...),
    # para a interface escrever a frase na língua de quem usa, em vez de
    # repetir o texto do backend, que só existe em português.
    error_reason: str | None = None


class DetectContentTypeRequest(BaseModel):
    """Body for POST /content-type/detect — lets the UI show a correct default
    on the editable content-type indicator (FR-096) before a Job exists."""
    input_path: str
    media_type: MediaType


class LicenseStatusResponse(BaseModel):
    state: LicenseState
    installations_used: int
    installations_limit: int
    offline_days_remaining: int | None = None
    # O final da chave e o e-mail da compra (popover da licenca). None sem rede
    # ou antes de o servidor responder -- ver licensing.license_details().
    license_last4: str | None = None
    email: str | None = None


# --- Video editing (specs/007-video-editor-player) ---
#
# Every model below sets extra='forbid'. That is what makes contracts/api.md's
# two guarantees real rather than aspirational: a `codec`, `preset`, `crf` or
# `input_path` in a request body is a 422, never a silently-ignored key. The
# same reasoning MediaRequest already documents for `model`/`engine`.

VideoContainer = Literal['mp4', 'mov', 'mkv', 'webm']
AudioEditMode = Literal['keep', 'mute', 'remove']
RotationDegrees = Literal[0, 90, 180, 270]


class VideoAdjustments(BaseModel):
    """FR-013a. Ranges mirror the colour formula the renderer's preview shader
    reproduces (research.md Decisão 1) — originally FFmpeg's `eq` filter, now the
    equivalent `lutyuv` expression that replaced it when `eq` proved to be GPL
    and absent from the shipped build. The arithmetic did not change; the filter
    did. Changing a bound here without changing the shader makes the preview
    lie.

    Each control carries its own `<name>_enabled`, mirroring the toggles the
    editor shows — the same shape `VideoEffects` below already had. A control
    that is off does not apply, whatever value sits next to it: that is what
    lets a person park a setting and come back to it instead of dragging the
    slider to neutral and losing the number.

    The flags default to **True**, not False. A client that sends only
    `{"brightness": 0.3}` means it, and a default of False would silently
    discard every adjustment sent by anything written before the flags existed.
    """
    model_config = ConfigDict(extra='forbid')

    brightness: float = Field(default=0.0, ge=-1.0, le=1.0)  # additive, not multiplicative
    brightness_enabled: bool = True
    contrast: float = Field(default=1.0, ge=0.0, le=4.0)
    contrast_enabled: bool = True
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    saturation_enabled: bool = True
    gamma: float = Field(default=1.0, ge=0.1, le=10.0)
    gamma_enabled: bool = True
    hue_degrees: float = Field(default=0.0, ge=-180.0, le=180.0)
    hue_degrees_enabled: bool = True
    sharpness: float = Field(default=0.0, ge=0.0, le=2.0)
    sharpness_enabled: bool = True


class VideoEffects(BaseModel):
    """FR-013b. These are the operations the preview shader does NOT reproduce,
    which is why FR-015's disclosure exists."""
    model_config = ConfigDict(extra='forbid')

    denoise_enabled: bool = False
    denoise_strength: int = Field(default=45, ge=0, le=100)
    blur_enabled: bool = False
    blur_strength: int = Field(default=0, ge=0, le=100)
    grain_enabled: bool = False
    grain_strength: int = Field(default=0, ge=0, le=100)


class VideoCrop(BaseModel):
    model_config = ConfigDict(extra='forbid')

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=16)
    height: int = Field(ge=16)


class VideoTransform(BaseModel):
    """FR-013c. Application order is normative — crop, rotate, flip, scale — and
    is pinned by test_video_edits.py, because a different order is a different
    picture, not another route to the same one."""
    model_config = ConfigDict(extra='forbid')

    crop: VideoCrop | None = None
    rotation_degrees: RotationDegrees = 0
    flip_horizontal: bool = False
    flip_vertical: bool = False
    output_width: int | None = Field(default=None, ge=16)
    output_height: int | None = Field(default=None, ge=16)


class VideoTrim(BaseModel):
    """FR-013d. The resulting duration -- not the source file's -- is what the
    ceilings are checked against (video_edits.OperationSize)."""
    model_config = ConfigDict(extra='forbid')

    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(gt=0.0)


class VideoAudioEdit(BaseModel):
    """FR-013e. Track manipulation only — mastering and restoration are
    specs/006-audio-engine-masterizacao, not this feature."""
    model_config = ConfigDict(extra='forbid')

    mode: AudioEditMode = 'keep'
    volume: float = Field(default=1.0, ge=0.0, le=2.0)


class VideoEditSet(BaseModel):
    """Five fields for the six families of FR-013, and that is not an error: the
    sixth — export — is the operation that consumes this set, not a state inside
    it (data-model.md)."""
    model_config = ConfigDict(extra='forbid')

    adjustments: VideoAdjustments = Field(default_factory=VideoAdjustments)
    effects: VideoEffects = Field(default_factory=VideoEffects)
    transform: VideoTransform = Field(default_factory=VideoTransform)
    trim: VideoTrim | None = None
    audio: VideoAudioEdit = Field(default_factory=VideoAudioEdit)


# Os quatro tipos que o produto sabe abrir. Definido aqui, e não junto do resto
# da Central de Compressão, porque `MediaHandleResponse` o usa — e a rota de
# registro é anterior à Central: passou a servir todos os tipos quando a Central
# chegou, em vez de uma segunda rota de caminho ser aberta.
MediaKind = Literal['image', 'video', 'audio', 'animation']


class MediaHandleRequest(BaseModel):
    """The ONE route permitted to accept a filesystem path, under the bounded
    exception added to Princípio XIII in constitution v3.0.0. The path must come
    from the operating system's file dialog invoked by the Electron main
    process; it is validated before anything else and never returned."""
    model_config = ConfigDict(extra='forbid')

    path: str


class MediaHandleResponse(BaseModel):
    """Note what is absent: there is no path field, and there never may be.

    `duration_seconds` deixou de ser obrigatório quando esta rota passou a
    registrar qualquer tipo de mídia (specs/008). Uma imagem não tem duração, e
    `0.0` seria uma afirmação sobre a mídia onde a verdade é que a pergunta não
    se aplica. Todo vídeo continua trazendo o campo, então nada muda para quem
    já lia esta resposta.
    """
    model_config = ConfigDict(extra='forbid')

    handle_id: str
    display_name: str
    media_kind: MediaKind | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    frame_rate_is_variable: bool = False
    has_audio: bool = False
    size_bytes: int = 0
    content_key: str


class VideoExportRequest(BaseModel):
    """Intent only. No codec, encoder, preset, CRF, pixel format or path —
    Princípio V (the API accepts intent, never implementation) and Princípio
    XIII (media by identifier) enforced by the shape of the type itself."""
    model_config = ConfigDict(extra='forbid')

    handle_id: str
    edits: VideoEditSet = Field(default_factory=VideoEditSet)
    container: VideoContainer = 'mp4'
    profile: Profile = 'balanced'
    output_directory: str | None = None
    output_filename: str | None = None
    conflict: Literal['rename', 'overwrite'] = 'rename'


class VideoPreviewFrameRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    time_seconds: float = Field(ge=0.0)
    edits: VideoEditSet = Field(default_factory=VideoEditSet)


class ContainerAvailability(BaseModel):
    model_config = ConfigDict(extra='forbid')

    value: VideoContainer
    available: bool
    # A key, not a sentence: the interface translates it (Princípio XIV). Never
    # an encoder name (Princípio V).
    unavailable_reason: Literal['no_encoder_available'] | None = None


class VideoCeilingsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    max_duration_seconds: float
    max_width: int
    max_height: int
    max_frame_rate: float
    max_frame_count: int
    max_size_bytes: int


class VideoExportOptionsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    containers: list[ContainerAvailability]
    profiles: list[Profile]
    ceilings: VideoCeilingsResponse


class ImageFormatAvailability(BaseModel):
    """The image half of the same question `ContainerAvailability` answers for
    video: what this machine can actually write, not what the list permits.

    `unsupported_build` rather than a library name — the interface translates
    the key (Princípio XIV), and naming OpenCV to the client would be the same
    leak Princípio V keeps encoder names out for.
    """
    model_config = ConfigDict(extra='forbid')

    value: ExportFormat
    available: bool
    unavailable_reason: Literal['unsupported_build'] | None = None


class ImageExportOptionsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    formats: list[ImageFormatAvailability]

# --- Central de Compressão (specs/008-compression-centre) ---


# Motivo pelo qual algo não está disponível. **Chave, nunca frase e nunca nome
# de biblioteca**: a interface traduz (Princípio XIV) e o Princípio V mantém
# `nvenc`, `libx264` e afins fora do fio.
UnavailableReason = Literal[
    'no_encoder_available', 'requires_hardware_encoder', 'unsupported_build'
]


class CapabilityEntry(BaseModel):
    """Uma opção e se esta máquina consegue produzi-la.

    `requires_hardware` existe para a interface poder explicar por que H.264 está
    indisponível **sem nomear encoder** — a diferença entre uma recusa acionável
    e uma opaca.
    """
    model_config = ConfigDict(extra='forbid')

    value: str
    available: bool
    unavailable_reason: UnavailableReason | None = None
    requires_hardware: bool = False


class HardwareCapability(BaseModel):
    model_config = ConfigDict(extra='forbid')

    available: bool
    reason: Literal['no_working_hardware_encoder'] | None = None


class ImageCapabilities(BaseModel):
    model_config = ConfigDict(extra='forbid')

    formats: list[CapabilityEntry]


class VideoCapabilities(BaseModel):
    model_config = ConfigDict(extra='forbid')

    containers: list[CapabilityEntry]
    video_codecs: list[CapabilityEntry]
    audio_codecs: list[CapabilityEntry]
    # Já filtrada pela sonda: a interface recebe só o que é permitido pelo
    # container E presente na máquina, sem precisar conhecer as duas perguntas.
    compatibility: dict[str, dict[str, list[str]]]
    hardware: HardwareCapability


class AudioCapabilities(BaseModel):
    model_config = ConfigDict(extra='forbid')

    formats: list[CapabilityEntry]
    codecs: list[CapabilityEntry]


class AnimationCapabilities(BaseModel):
    model_config = ConfigDict(extra='forbid')

    formats: list[CapabilityEntry]


class CompressionCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image: ImageCapabilities
    video: VideoCapabilities
    audio: AudioCapabilities
    animation: AnimationCapabilities


SizeUnit = Literal['KB', 'MB', 'GB']
EstimateConfidence = Literal['measured_sample', 'derived', 'rough']
Feasibility = Literal['ok', 'below_floor', 'not_estimable']


class CompressionTarget(BaseModel):
    """O modo tamanho desejado (FR-016). Unidades decimais: "5 MB" num limite de
    upload são 5.000.000 bytes, e usar 1024 faria o arquivo passar de um limite
    que a pessoa acertou."""
    model_config = ConfigDict(extra='forbid')

    value: float = Field(gt=0)
    unit: SizeUnit = 'MB'


class CompressionEstimateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    handle_id: str
    media_kind: MediaKind
    # Livre por tipo de mídia; validado pelo serviço da mídia correspondente.
    # Um modelo fechado aqui duplicaria as quatro variantes de settings e seria
    # o segundo lugar a divergir.
    settings: dict[str, Any] = Field(default_factory=dict)
    target: CompressionTarget | None = None


class CompressionEstimateResponse(BaseModel):
    """`confidence` e `assumptions` viajam sempre.

    As mídias não são igualmente previsíveis, e apresentar as três com a mesma
    cara seria mentir sobre duas. `estimated_bytes` nulo é resposta legítima —
    "não sei" é verdade, e um chute com aparência de medição não é.
    """
    model_config = ConfigDict(extra='forbid')

    original_bytes: int
    estimated_bytes: int | None
    estimated_saving_bytes: int | None
    reduction_ratio: float | None
    confidence: EstimateConfidence
    assumptions: list[str]
    feasibility: Feasibility
    resolved_settings: dict[str, Any] | None = None


PresetOrigin = Literal['builtin', 'platform', 'user']


class CompressionPreset(BaseModel):
    """`name_key` para os internos (traduzível) e `name` literal para os do
    usuário — a pessoa escolheu aquela palavra e ela não se traduz."""
    model_config = ConfigDict(extra='forbid')

    id: str
    media_kind: MediaKind
    origin: PresetOrigin
    settings: dict[str, Any]
    name: str | None = None
    name_key: str | None = None


class CompressionPresetsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    presets: list[CompressionPreset]


class CompressionPresetCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=80)
    media_kind: MediaKind
    settings: dict[str, Any] = Field(default_factory=dict)


class CompressionPresetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=80)
    settings: dict[str, Any] | None = None


class CompressionExportConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    directory: str | None = None
    naming_pattern: str = '{filename}_compressed'
    conflict_policy: ConflictMode = 'rename'
    apply_to_all: bool = False


class CompressionMediaRequest(BaseModel):
    """Importar um arquivo para a Central, de qualquer tipo (FR-007).

    Separada de `MediaHandleRequest` porque a resposta é outra: aquela descreve
    vídeo e tem `extra='forbid'` com campos fixos, e alargá-la para caber áudio,
    imagem e animação quebraria os clientes que ela já serve.
    """
    model_config = ConfigDict(extra='forbid')

    path: str


class CompressionMediaResponse(BaseModel):
    """O que a interface mostra antes de processar.

    **Todo campo além dos três primeiros é opcional, e isso é o ponto** (FR-010):
    um campo que a sondagem não obteve chega ausente, nunca zerado. `None` fala
    da sondagem; `0` falaria da mídia, e a interface que exibisse "0 kbps" estaria
    afirmando algo que ninguém mediu.

    Não há campo de caminho aqui, e nunca pode haver.
    """
    model_config = ConfigDict(extra='forbid')

    handle_id: str
    display_name: str
    media_kind: MediaKind
    content_key: str
    size_bytes: int = 0

    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    frame_rate: float | None = None
    frame_rate_is_variable: bool | None = None
    has_audio: bool | None = None
    has_alpha: bool | None = None
    has_metadata: bool | None = None
    sample_rate: int | None = None
    channels: int | None = None
    # Codecs do contêiner (`h264`, `opus`), nunca encoders: o Princípio V mantém
    # `libx264` e `nvenc` fora do fio, e o que o arquivo **é** fica num nível
    # acima do que o produziu.
    video_codec: str | None = None
    audio_codec: str | None = None
    video_bitrate_bps: int | None = None
    audio_bitrate_bps: int | None = None
    container_bitrate_bps: int | None = None


class CompressionHistoryEntry(BaseModel):
    """Uma compressão concluída, como o histórico a guarda (FR-062).

    `settings_snapshot` é o que **foi usado**, e `preset_id` só diz de onde veio.
    Repetir a compressão parte do snapshot: um preset editado depois faria a
    repetição produzir algo diferente do que esta entrada exibe (FR-063).

    Não há campo de caminho de origem — uma entrada é o registro do que foi
    feito, não um atalho para um arquivo que pode ter sido movido.
    """
    model_config = ConfigDict(extra='forbid')

    id: str
    display_name: str
    media_kind: MediaKind
    settings_snapshot: dict[str, Any]
    preset_id: str | None = None
    result: dict[str, Any]
    output_path: str | None = None
    finished_at: str | None = None


class CompressionHistoryResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    entries: list[CompressionHistoryEntry] = []


class CompressionJobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    handle_id: str
    media_kind: MediaKind
    settings: dict[str, Any] = Field(default_factory=dict)
    target: CompressionTarget | None = None
    preset_id: str | None = None
    # Falso por padrão, e o backend verifica: a condição 2 da exceção do
    # Princípio V se perderia no dia em que alguém mexesse só na interface.
    advanced: bool = False
    export: CompressionExportConfig = Field(default_factory=CompressionExportConfig)


class CompressionJobResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    job_id: str
    status: JobStatusValue
    estimate: CompressionEstimateResponse | None = None

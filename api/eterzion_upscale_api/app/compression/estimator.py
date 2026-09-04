"""Quanto o arquivo vai pesar, e o que seria preciso para caber num alvo.

Duas operações inversas uma da outra:

- **estimar** — dadas as configurações, qual o tamanho? (FR-021)
- **resolver alvo** — dado o tamanho, quais configurações? (FR-017)

Nenhuma das duas processa nada nem escreve arquivo. `POST /compression/estimate`
é chamada a cada mudança de controle, e uma estimativa com efeito colateral
seria dezenas de arquivos temporários por sessão.

**Toda estimativa carrega `confidence` e `assumptions`**, porque as três mídias
não são igualmente previsíveis e apresentá-las com a mesma cara seria mentir
sobre duas delas. Vídeo e áudio saem de bitrate × duração, que é aritmética.
Imagem depende do conteúdo: a mesma resolução e a mesma qualidade dão arquivos
várias vezes diferentes entre um céu liso e uma folhagem. Por isso imagem é
medida numa amostra reduzida em vez de derivada de tabela — a amostra carrega o
conteúdo real, e uma tabela carrega a média de conteúdos que não são o seu.
"""
from __future__ import annotations

import io
import math
import os
from dataclasses import dataclass, field
from typing import Any, Literal

from . import config

Confidence = Literal['measured_sample', 'derived', 'rough']
Feasibility = Literal['ok', 'below_floor', 'not_estimable']


@dataclass
class Estimate:
    original_bytes: int
    estimated_bytes: int | None
    confidence: Confidence
    assumptions: list[str] = field(default_factory=list)
    feasibility: Feasibility = 'ok'
    resolved_settings: dict[str, Any] | None = None

    @property
    def saving_bytes(self) -> int | None:
        if self.estimated_bytes is None:
            return None
        return self.original_bytes - self.estimated_bytes

    @property
    def reduction_ratio(self) -> float | None:
        if self.estimated_bytes is None or not self.original_bytes:
            return None
        return 1.0 - (self.estimated_bytes / self.original_bytes)

    def as_dict(self) -> dict[str, Any]:
        return {
            'original_bytes': self.original_bytes,
            'estimated_bytes': self.estimated_bytes,
            'estimated_saving_bytes': self.saving_bytes,
            'reduction_ratio': self.reduction_ratio,
            'confidence': self.confidence,
            'assumptions': self.assumptions,
            'feasibility': self.feasibility,
            'resolved_settings': self.resolved_settings,
        }


# ------------------------------- imagem ------------------------------- #

# Lado do recorte de amostra, em pixels do ORIGINAL. Dois tamanhos porque a
# medição é de dois pontos — ver `estimate_image`.
_CROP_SMALL = 256
_CROP_LARGE = 512

# Pontos da grade de amostragem. Ver `_encode_crop`.
_GRID_POINTS = 5


def estimate_image(source_path: str, *, output_format: str, quality: int,
                   lossless: bool = False,
                   target_size: tuple[int, int] | None = None) -> Estimate:
    """Codifica **recortes em resolução nativa** e extrapola pela área.

    A primeira versão reduzia a imagem inteira e extrapolava. O benchmark da
    T015 a reprovou sem margem: 0 de 25 casos dentro de ±20%, erro médio de
    268%, pior de 1480%. A causa é estrutural, não de calibração — **reduzir uma
    imagem muda o seu conteúdo de frequência, que é exatamente o que decide o
    tamanho comprimido.** Num céu liso a amostra reduzida ficava dominada por
    cabeçalho e superestimava até 7×; num conteúdo ruidoso a redução *destruía*
    o ruído e subestimava 75%. O erro tinha sinais opostos conforme o conteúdo,
    que é a pior propriedade possível numa estimativa.

    Recortar preserva a frequência local: um bloco de 256×256 pixels do original
    tem a mesma textura, o mesmo ruído e as mesmas bordas que a imagem inteira.

    **Dois pontos, não um.** Todo arquivo comprimido tem um custo fixo — tabelas
    de Huffman no JPEG, paleta e cabeçalho no PNG — que não escala com a área.
    Um único recorte não consegue separar esse custo do custo por pixel, e é
    justamente ele que inflava a estimativa dos conteúdos lisos. Medindo dois
    tamanhos, a diferença dá o custo marginal por pixel e a sobra dá o fixo:

        bytes_por_pixel = (S_grande − S_pequeno) / (A_grande − A_pequeno)
        fixo            = S_pequeno − bytes_por_pixel × A_pequeno
        estimativa      = fixo + bytes_por_pixel × A_saída
    """
    from PIL import Image

    original_bytes = _file_size(source_path)
    try:
        with Image.open(source_path) as img:
            img.load()
            largura, altura = img.size
            saida_w, saida_h = target_size or (largura, altura)
            preparada = _prepare_for_format(img, output_format)
            opcoes = _encode_options(output_format, quality, lossless)

            pequeno = _encode_crop(preparada, _CROP_SMALL, output_format, opcoes)
            grande = _encode_crop(preparada, _CROP_LARGE, output_format, opcoes)
    except Exception:  # noqa: BLE001 — imagem ilegível é "não estimável", não erro
        return Estimate(original_bytes, None, 'rough', ['unreadable_source'], 'not_estimable')

    if pequeno is None:
        return Estimate(original_bytes, None, 'rough', [], 'not_estimable')

    bytes_p, area_p = pequeno
    pixels_saida = saida_w * saida_h
    premissas = ['native_resolution_crops', 'spatial_grid_sample']

    if grande is not None and grande[1] > area_p:
        bytes_g, area_g = grande
        bpp = (bytes_g - bytes_p) / (area_g - area_p)
        if bpp > 0:
            # O custo fixo medido é o de N arquivos; o resultado será UM.
            fixo_total = max(0.0, bytes_p - bpp * area_p)
            fixo_um = fixo_total / _GRID_POINTS
            previsto = int(fixo_um + bpp * pixels_saida)
            premissas.append('two_point_fixed_cost_removed')
            return Estimate(original_bytes, max(previsto, 1), 'measured_sample', premissas)

    previsto = int(bytes_p * pixels_saida / area_p)
    premissas.append('single_point_fallback')
    return Estimate(original_bytes, max(previsto, 1), 'derived', premissas)


def _encode_crop(img, lado: int, output_format: str,
                 opcoes: dict[str, Any]) -> tuple[int, int] | None:
    """Codifica uma GRADE de recortes em resolução nativa e soma.

    Um recorte só, mesmo centrado, mede uma região e responde pela imagem
    inteira. O benchmark mostrou o custo disso: num padrão cujo conteúdo varia
    entre as regiões, o centro subestimava o arquivo em até 71%. Amostrar em
    grade cobre a variação espacial que é justamente o que um recorte único
    perde.

    Cinco pontos — centro e quatro quadrantes — porque três não pegam os cantos
    e nove custam o dobro sem melhorar a resposta na medição.
    """
    largura, altura = img.size
    lado_w, lado_h = min(lado, largura), min(lado, altura)
    if lado_w <= 0 or lado_h <= 0:
        return None

    # Frações do centro de cada recorte. O 0.25/0.75 evita a borda, onde uma
    # moldura ou barra preta comprimiria como nada e não representa o arquivo.
    posicoes = ((0.5, 0.5), (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))
    total_bytes = 0
    total_area = 0
    for fx, fy in posicoes:
        esquerda = max(0, min(largura - lado_w, int(largura * fx - lado_w / 2)))
        topo = max(0, min(altura - lado_h, int(altura * fy - lado_h / 2)))
        recorte = img.crop((esquerda, topo, esquerda + lado_w, topo + lado_h))
        buffer = io.BytesIO()
        recorte.save(buffer, format=output_format.upper(), **opcoes)
        total_bytes += buffer.tell()
        total_area += lado_w * lado_h
    return total_bytes, total_area


def _prepare_for_format(img, output_format: str):
    """JPEG não tem canal alfa; gravar RGBA nele levanta em vez de estimar."""
    if output_format.lower() in ('jpeg', 'bmp') and img.mode in ('RGBA', 'LA', 'P'):
        return img.convert('RGB')
    return img


def _encode_options(output_format: str, quality: int, lossless: bool) -> dict[str, Any]:
    fmt = output_format.lower()
    if fmt == 'png':
        # PNG é sempre sem perda; `quality` vira nível de compressão invertido.
        return {'compress_level': _quality_to_png_level(quality)}
    if fmt in ('webp', 'avif'):
        return {'quality': quality, 'lossless': lossless}
    if fmt == 'jpeg':
        return {'quality': quality}
    return {}


def _quality_to_png_level(quality: int) -> int:
    """Qualidade alta pede arquivo fiel; no PNG, fidelidade é dada e o que varia
    é esforço. Qualidade baixa → mais compressão, que é mais esforço."""
    return max(0, min(9, round(9 - (quality / 100) * 9)))


# ------------------------------- vídeo ------------------------------- #

def estimate_video(*, original_bytes: int, duration_seconds: float,
                   video_bitrate_bps: int | None, audio_bitrate_bps: int | None,
                   container: str) -> Estimate:
    """Aritmética: (bitrate de vídeo + de áudio) × duração + overhead.

    `video_bitrate_bps` a `None` significa modo de qualidade constante (CRF), em
    que não há bitrate declarado. Estimar isso exigiria uma tabela
    bitrate-por-pixel calibrada por codec e CRF que **ainda não foi medida** —
    e inventá-la daria um número com a mesma aparência de um medido. Enquanto a
    tabela não existe, a resposta é `rough` sem valor, e a interface diz que não
    sabe em vez de chutar.
    """
    if duration_seconds <= 0:
        return Estimate(original_bytes, None, 'rough', ['no_duration'], 'not_estimable')
    if video_bitrate_bps is None:
        return Estimate(original_bytes, None, 'rough',
                        ['constant_quality_mode', 'no_calibrated_table'], 'not_estimable')

    total_bps = video_bitrate_bps + (audio_bitrate_bps or 0)
    payload = total_bps * duration_seconds / 8
    overhead = config.CONTAINER_OVERHEAD_RATIO.get(container, 0.02)
    previsto = int(payload * (1 + overhead))
    return Estimate(original_bytes, max(previsto, 1), 'derived',
                    ['bitrate_times_duration', 'container_overhead'])


def estimate_audio(*, original_bytes: int, duration_seconds: float,
                   bitrate_bps: int | None, lossless: bool = False) -> Estimate:
    if duration_seconds <= 0:
        return Estimate(original_bytes, None, 'rough', ['no_duration'], 'not_estimable')
    if lossless or bitrate_bps is None:
        # FLAC/WAV não têm bitrate alvo: o tamanho depende do conteúdo, e a
        # razão de compressão do FLAC varia demais entre silêncio e música densa
        # para um número único significar alguma coisa.
        return Estimate(original_bytes, None, 'rough', ['lossless_depends_on_content'],
                        'not_estimable')
    previsto = int(bitrate_bps * duration_seconds / 8)
    return Estimate(original_bytes, max(previsto, 1), 'derived', ['bitrate_times_duration'])


# ------------------------------- tamanho alvo ------------------------------- #

UNIT_BYTES = {'KB': 1000, 'MB': 1000 * 1000, 'GB': 1000 * 1000 * 1000}


def target_to_bytes(value: float, unit: str) -> int:
    """KB/MB/GB decimais, não binários.

    É o que "5 MB" significa num limite de upload, num aviso de e-mail e no
    gerenciador de arquivos — e a Central existe justamente para caber nesses
    limites. Usar 1024 faria o arquivo passar de um limite que a pessoa acertou.
    """
    if unit not in UNIT_BYTES:
        raise ValueError(f'Unidade desconhecida: {unit!r}')
    return int(value * UNIT_BYTES[unit])


def resolve_video_target(*, target_bytes: int, duration_seconds: float,
                         audio_bitrate_bps: int, height: int,
                         container: str) -> tuple[int | None, Feasibility]:
    """O bitrate de vídeo que faz o arquivo caber, ou por que não cabe.

    `below_floor` não é erro: o alvo é uma pergunta legítima e a resposta é "só
    destruindo a mídia". FR-020 exige dizer isso **antes** de processar, e dizer
    é responder — não recusar a pergunta.
    """
    if duration_seconds <= 0:
        return None, 'not_estimable'

    overhead = config.CONTAINER_OVERHEAD_RATIO.get(container, 0.02)
    payload_bytes = target_bytes / (1 + overhead)
    total_bps = payload_bytes * 8 / duration_seconds
    video_bps = total_bps - audio_bitrate_bps

    if video_bps < config.video_bitrate_floor(height):
        return None, 'below_floor'
    return int(video_bps), 'ok'


def resolve_audio_target(*, target_bytes: int,
                         duration_seconds: float) -> tuple[int | None, Feasibility]:
    if duration_seconds <= 0:
        return None, 'not_estimable'
    bps = target_bytes * 8 / duration_seconds
    if bps < config.AUDIO_BITRATE_FLOOR_BPS:
        return None, 'below_floor'
    return int(bps), 'ok'


def resolve_image_target(source_path: str, *, output_format: str, target_bytes: int,
                         lossless: bool = False,
                         target_size: tuple[int, int] | None = None,
                         max_iterations: int = 6) -> tuple[int | None, Feasibility]:
    """A qualidade que faz a imagem caber, por busca binária sobre a amostra.

    Não há inversão fechada: o tamanho de um JPEG em função da qualidade depende
    do conteúdo. Seis iterações sobre a amostra reduzida convergem em poucas
    dezenas de milissegundos — caro demais para rodar a cada tecla digitada, e
    por isso roda ao confirmar o alvo e não a cada dígito.

    Formatos sem perda ignoram qualidade, então não há o que buscar: ou cabem,
    ou o alvo é inatingível sem trocar o formato.
    """
    if lossless or output_format.lower() in ('png', 'bmp', 'tiff'):
        sem_perda = estimate_image(source_path, output_format=output_format, quality=100,
                                   lossless=True, target_size=target_size)
        if sem_perda.estimated_bytes is None:
            return None, 'not_estimable'
        return (None, 'ok') if sem_perda.estimated_bytes <= target_bytes else (None, 'below_floor')

    baixo, alto, melhor = 1, 100, None
    for _ in range(max_iterations):
        meio = (baixo + alto) // 2
        previsto = estimate_image(source_path, output_format=output_format, quality=meio,
                                  target_size=target_size).estimated_bytes
        if previsto is None:
            return None, 'not_estimable'
        if previsto <= target_bytes:
            melhor = meio
            baixo = meio + 1
        else:
            alto = meio - 1
        if baixo > alto:
            break

    # Qualidade 1 é o piso: abaixo disso não há o que ceder, e se nem ela cabe o
    # alvo não é atingível neste formato e nesta resolução.
    return (melhor, 'ok') if melhor is not None else (None, 'below_floor')


# ------------------------------- utilitários ------------------------------- #

def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def humanise(num_bytes: int | None) -> str | None:
    """Só para log e benchmark. A interface formata no idioma da pessoa."""
    if num_bytes is None:
        return None
    if num_bytes < 1000:
        return f'{num_bytes} B'
    expoente = min(int(math.log(num_bytes, 1000)), 3)
    unidade = ['B', 'KB', 'MB', 'GB'][expoente]
    return f'{num_bytes / 1000 ** expoente:.1f} {unidade}'


# ------------------------------- despacho ------------------------------- #

def estimate_for_kind(media_kind: str, source_path: str | None, info: dict[str, Any],
                      settings: dict[str, Any],
                      target_bytes: int | None = None) -> Estimate:
    """A porta única por onde a rota entra.

    Um despachante por tipo de mídia em vez de condicionais na rota: acrescentar
    um tipo (FR-004) toca este mapa e nada mais, e a rota não precisa saber que
    imagem se mede por amostra enquanto vídeo se calcula por bitrate.
    """
    if source_path is None:
        return Estimate(0, None, 'rough', ['unknown_handle'], 'not_estimable')

    original = _file_size(source_path)
    duracao = float(info.get('duration_seconds') or 0)

    if media_kind == 'image':
        return _estimate_image_kind(source_path, original, settings, target_bytes)
    if media_kind in ('video', 'animation'):
        return _estimate_video_kind(original, duracao, info, settings, target_bytes)
    if media_kind == 'audio':
        return _estimate_audio_kind(original, duracao, settings, target_bytes)
    return Estimate(original, None, 'rough', ['unknown_media_kind'], 'not_estimable')


def _estimate_image_kind(source_path: str, original: int, settings: dict[str, Any],
                         target_bytes: int | None) -> Estimate:
    fmt = settings.get('output_format') or 'jpeg'
    if fmt == 'keep':
        fmt = os.path.splitext(source_path)[1].lstrip('.').lower() or 'jpeg'
        fmt = 'jpeg' if fmt in ('jpg', 'jpeg') else fmt
    qualidade = int(settings.get('quality', 82))
    lossless = bool(settings.get('lossless'))
    tamanho = _target_dimensions(settings)

    if target_bytes is not None:
        qualidade_alvo, viabilidade = resolve_image_target(
            source_path, output_format=fmt, target_bytes=target_bytes,
            lossless=lossless, target_size=tamanho)
        if viabilidade != 'ok':
            est = estimate_image(source_path, output_format=fmt, quality=qualidade,
                                 lossless=lossless, target_size=tamanho)
            est.feasibility = viabilidade
            return est
        if qualidade_alvo is not None:
            qualidade = qualidade_alvo

    est = estimate_image(source_path, output_format=fmt, quality=qualidade,
                         lossless=lossless, target_size=tamanho)
    if target_bytes is not None:
        est.resolved_settings = {'quality': qualidade, 'output_format': fmt}
    return est


def _estimate_video_kind(original: int, duracao: float, info: dict[str, Any],
                         settings: dict[str, Any], target_bytes: int | None) -> Estimate:
    container = settings.get('container') or 'mp4'
    audio_bps = int(settings.get('audio_bitrate_bps') or 128_000)
    altura = int(settings.get('height') or info.get('height') or 1080)

    if target_bytes is not None:
        video_bps, viabilidade = resolve_video_target(
            target_bytes=target_bytes, duration_seconds=duracao,
            audio_bitrate_bps=audio_bps, height=altura, container=container)
        if viabilidade != 'ok':
            return Estimate(original, None, 'rough', ['target_unreachable'], viabilidade)
        est = estimate_video(original_bytes=original, duration_seconds=duracao,
                             video_bitrate_bps=video_bps, audio_bitrate_bps=audio_bps,
                             container=container)
        est.resolved_settings = {'video_bitrate_bps': video_bps,
                                 'audio_bitrate_bps': audio_bps}
        return est

    declarado = settings.get('video_bitrate_bps')
    return estimate_video(original_bytes=original, duration_seconds=duracao,
                          video_bitrate_bps=int(declarado) if declarado else None,
                          audio_bitrate_bps=audio_bps, container=container)


def _estimate_audio_kind(original: int, duracao: float, settings: dict[str, Any],
                         target_bytes: int | None) -> Estimate:
    lossless = settings.get('output_format') in ('flac', 'wav')

    if target_bytes is not None and not lossless:
        bps, viabilidade = resolve_audio_target(target_bytes=target_bytes,
                                                duration_seconds=duracao)
        if viabilidade != 'ok':
            return Estimate(original, None, 'rough', ['target_unreachable'], viabilidade)
        est = estimate_audio(original_bytes=original, duration_seconds=duracao,
                             bitrate_bps=bps)
        est.resolved_settings = {'bitrate_bps': bps}
        return est

    declarado = settings.get('bitrate_bps')
    return estimate_audio(original_bytes=original, duration_seconds=duracao,
                          bitrate_bps=int(declarado) if declarado else None,
                          lossless=lossless)


def _target_dimensions(settings: dict[str, Any]) -> tuple[int, int] | None:
    largura, altura = settings.get('width'), settings.get('height')
    if largura and altura:
        return int(largura), int(altura)
    return None

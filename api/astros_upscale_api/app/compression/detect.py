"""T025a — que tipo de mídia é este arquivo, e o que dá para saber sobre ele.

**A extensão não decide** (FR-007). Um `.png` que é JPEG, um `.mp4` que só tem
áudio, um `.gif` de um quadro só: em todos, a extensão afirma uma coisa e o
conteúdo é outra. Confiar nela faz a Central oferecer controles de vídeo para um
arquivo de áudio e falhar depois, que é a falha tardia que o Princípio XIII
proíbe.

**Campo que a sondagem não obteve fica ausente** (FR-010). `None` é uma
afirmação sobre a sondagem; `0` é uma afirmação sobre a mídia. Um bitrate zerado
faria a estimativa dividir por nada e responder com confiança total sobre um
número que ninguém mediu.
"""
from __future__ import annotations

import os
from typing import Any

from astros_upscale.media import ProbeError, probe_streams

# Um GIF de um único quadro é uma imagem. A distinção é ter mais de um quadro,
# não a extensão — e tratá-lo como animação ofereceria controles de FPS e
# otimização de quadros para algo que não se move.
_ANIMATION_MIN_FRAMES = 2


def detect_media_kind(path: str) -> str:
    """`image` · `video` · `audio` · `animation`, decidido pelo conteúdo.

    A ordem das perguntas importa: um arquivo com trilha de vídeo **e** de áudio
    é vídeo, não áudio. Só depois de as duas negarem é que a ausência decide.

    `animation` só é considerada nos formatos que guardam as duas coisas — GIF,
    WebP, APNG. Num container de vídeo a contagem de quadros não distingue nada,
    porque todo vídeo tem muitos.
    """
    try:
        return _detect_by_probe(path)
    except ProbeError:
        # ffprobe não leu: pode ser um formato de imagem que ele não conhece.
        # O Pillow é a segunda opinião, não a primeira — ele abre imagem e mais
        # nada, então uma resposta positiva dele é conclusiva e uma negativa não
        # significa que o arquivo é inválido.
        return _by_pillow(path)


# Formatos que **podem** conter animação e também podem conter uma imagem só.
# São os únicos em que a contagem de quadros decide algo: num `.mp4` a contagem
# não distingue nada, porque todo vídeo tem muitos quadros.
_ANIMATION_CAPABLE_EXTENSIONS = frozenset({'.gif', '.webp', '.png', '.apng'})


def _detect_by_probe(path: str) -> str:
    probe = probe_streams(path)
    tem_video = probe.get('video_stream_count', 0) > 0
    tem_audio = probe.get('audio_stream_count', 0) > 0

    if tem_video:
        # O ffprobe reporta "trilha de vídeo" para coisas que não são mídia — um
        # arquivo de texto com extensão de imagem chegou aqui como vídeo. Sem
        # dimensões não há imagem nem vídeo; é lixo com um cabeçalho que
        # enganou o demuxer.
        if not (probe.get('width') and probe.get('height')):
            # Sem dimensões o ffprobe não sabe o que leu. Pode ser lixo com um
            # cabeçalho que enganou o demuxer, ou um formato cujas dimensões ele
            # não reporta — o WebP animado é exatamente esse caso. O Pillow
            # desempata, e desempata **distinguindo animação**, não só dizendo
            # se abre.
            return _by_pillow(path)

        extensao = os.path.splitext(path)[1].lower()
        if extensao in _ANIMATION_CAPABLE_EXTENSIONS:
            # Aqui, e só aqui, a contagem decide: estes formatos guardam tanto
            # uma imagem parada quanto uma animação.
            quadros = _frame_count(path, probe)
            if quadros is not None:
                return 'animation' if quadros >= _ANIMATION_MIN_FRAMES else 'image'
            return 'image'
        # Container de vídeo. Duração nula significa quadro único — um still
        # gravado num container de vídeo é uma imagem, não um filme de 0 s.
        return 'video' if (probe.get('duration_seconds') or 0) > 0 else 'image'

    if tem_audio:
        return 'audio'
    return _by_pillow(path)


def _frame_count(path: str, probe: dict[str, Any]) -> int | None:
    """Quantos quadros, quando dá para saber sem decodificar o arquivo inteiro.

    Só é consultado para decidir imagem-versus-animação, e por isso a resposta
    aproximada basta: a pergunta é "mais de um?", não "quantos exatamente?".
    """
    contagem = probe.get('frame_count')
    if contagem:
        return int(contagem)
    extensao = os.path.splitext(path)[1].lower()
    if extensao in ('.gif', '.webp', '.png', '.apng'):
        return _pillow_frame_count(path)
    return None


def _pillow_frame_count(path: str) -> int | None:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return getattr(img, 'n_frames', 1)
    except Exception:  # noqa: BLE001
        return None


def _by_pillow(path: str) -> str:
    """O veredito do Pillow: `animation`, `image` ou `unknown`.

    Ele abre imagem e mais nada, então uma resposta positiva é conclusiva — e
    uma negativa significa "não é imagem", não "arquivo inválido".

    Distingue animação em vez de só dizer se abre: este caminho recebe o WebP
    animado, cujas dimensões o ffprobe não reporta, e responder `image` ali
    ofereceria os controles errados para um arquivo que se move.
    """
    quadros = _pillow_frame_count(path)
    if quadros is None:
        return 'unknown'
    return 'animation' if quadros >= _ANIMATION_MIN_FRAMES else 'image'


def probe_metadata(path: str, media_kind: str) -> dict[str, Any]:
    """Os metadados que a interface mostra antes de processar (FR-008).

    Só o que se aplica ao tipo, e só o que foi de fato obtido. Uma chave ausente
    é diferente de uma chave nula, e as duas são diferentes de zero — a interface
    omite o que não recebeu em vez de exibir um traço que parece medido.
    """
    dados: dict[str, Any] = {'size_bytes': _size(path)}

    if media_kind == 'image':
        dados.update(_image_metadata(path))
        return _sem_nulos(dados)

    try:
        probe = probe_streams(path)
    except ProbeError:
        return _sem_nulos(dados)

    if media_kind in ('video', 'animation'):
        dados.update({
            'width': probe.get('width'),
            'height': probe.get('height'),
            'duration_seconds': probe.get('duration_seconds'),
            'frame_rate': probe.get('frame_rate'),
            'frame_rate_is_variable': probe.get('frame_rate_is_variable'),
            'has_audio': probe.get('audio_stream_count', 0) > 0,
        })
    if media_kind == 'audio' or probe.get('audio_stream_count', 0) > 0:
        dados.update({
            'duration_seconds': dados.get('duration_seconds') or probe.get('duration_seconds'),
            'sample_rate': probe.get('sample_rate'),
            'channels': probe.get('channels'),
        })
    return _sem_nulos(dados)


def _image_metadata(path: str) -> dict[str, Any]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return {
                'width': img.width,
                'height': img.height,
                'has_alpha': img.mode in ('RGBA', 'LA', 'PA'),
                # Se há EXIF ou perfil de cor a preservar — é o que decide se o
                # controle de metadados tem o que fazer neste arquivo.
                'has_metadata': bool(img.info.get('exif') or img.info.get('icc_profile')),
            }
    except Exception:  # noqa: BLE001
        return {}


def _sem_nulos(dados: dict[str, Any]) -> dict[str, Any]:
    """Remove o que a sondagem não obteve, em vez de devolver nulo.

    FR-010. Ausente e nulo dizem a mesma coisa para a interface, mas ausente diz
    também que ninguém tentou fingir.
    """
    return {k: v for k, v in dados.items() if v is not None}


def _size(path: str) -> int | None:
    try:
        return os.path.getsize(path)
    except OSError:
        return None

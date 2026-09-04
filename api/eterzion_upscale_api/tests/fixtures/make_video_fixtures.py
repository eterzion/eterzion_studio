"""T005 (specs/007-video-editor-player) — generates the video fixtures the
007 test suite and quickstart.md need.

Real files produced by real FFmpeg, not synthetic bytes: Constitution
Princípio VIII requires processing pipelines to be tested against real
behaviour, and a "video" that ffprobe cannot read would test nothing.

Generated on demand rather than committed — a few seconds of encoding is
cheaper than binary blobs in git, and the fixtures then match whatever FFmpeg
the developer actually has.

    python -m tests.fixtures.make_video_fixtures            # missing ones only
    python -m tests.fixtures.make_video_fixtures --force    # rebuild all

`longo.mp4` is skipped by default: it exists only to exceed the duration
ceiling, and encoding two real hours to prove a refusal that happens before any
processing is a poor trade. `--with-long` builds it when the ceiling test is
being exercised for real; `test_video_ceilings.py` otherwise drives the check
with probed metadata, which is what the ceiling actually reads.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent


def _ffmpeg() -> str:
    """The same binary resolution the application uses — bundled first, PATH
    second — so fixtures come from the build the tests will exercise.

    Falls back to PATH when the backend package cannot be imported: importing
    `eterzion_upscale` pulls in psutil, torch and the rest of the processing
    stack, and a script whose only job is to write four test videos has no
    business requiring the full environment to run."""
    sys.path.insert(0, str(FIXTURES_DIR.parent.parent.parent))
    try:
        from eterzion_upscale.media import ffmpeg_path
    except ImportError:
        bundled_dir = os.environ.get('ASTROS_FFMPEG_DIR')
        if bundled_dir:
            name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
            bundled = os.path.join(bundled_dir, name)
            if os.path.isfile(bundled):
                return bundled
        return shutil.which('ffmpeg') or 'ffmpeg'
    return ffmpeg_path() or 'ffmpeg'


def _run(args: list[str]) -> None:
    import subprocess

    # shell=False and an argument list, per Princípio XIII — the rule holds for
    # test tooling too, not only for shipped code.
    result = subprocess.run([_ffmpeg(), '-y', *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg falhou: {result.stderr.strip()[-800:]}')


def _testsrc(duration: int, size: str, fps: int) -> list[str]:
    return ['-f', 'lavfi', '-i', f'testsrc=duration={duration}:size={size}:rate={fps}']


def _sine(duration: int) -> list[str]:
    return ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={duration}']


# `mpeg4`, not `libx264`. libx264 is GPL and simply absent from an LGPL FFmpeg —
# including the build the installer ships and the one a licence-conscious
# developer installs — so this script died with `Unknown encoder 'libx264'` and
# every test depending on these fixtures skipped itself, quietly, everywhere.
# 57 of them, CI included.
#
# mpeg4 is LGPL, present in every build, and valid in an mp4 container. No test
# asserts on the fixtures' codec: what they exercise is duration, frame rate,
# resolution and the presence of an audio track, none of which mpeg4 changes.
_FIXTURE_VIDEO_CODEC = ['-c:v', 'mpeg4', '-q:v', '3', '-pix_fmt', 'yuv420p']


def build_curto(path: Path) -> None:
    """~10 s, 1080p, 30 fps constant frame rate, with an audio track. The
    default subject of most scenarios."""
    _run([*_testsrc(10, '1920x1080', 30), *_sine(10),
          *_FIXTURE_VIDEO_CODEC, '-c:a', 'aac', '-shortest', str(path)])


def build_sem_audio(path: Path) -> None:
    """No audio track — drives FR-009 (do not offer a control for a track that
    is not there)."""
    _run([*_testsrc(5, '1280x720', 30), *_FIXTURE_VIDEO_CODEC, '-an', str(path)])


def build_vfr(path: Path) -> None:
    """Variable frame rate — drives FR-012 (a frame number that cannot be
    trusted must not be displayed as exact).

    Frames are dropped unevenly and their ORIGINAL timestamps are kept, which
    is what makes the result genuinely variable. Two details matter and are
    easy to get wrong:

    - No `setpts`. An earlier version chained `setpts=N/FRAME_RATE/TB` after
      the select, which re-linearises the timestamps and produces a perfectly
      constant frame rate with fewer frames — a file named vfr.mp4 that is not
      VFR, against which an FR-012 test passes while proving nothing.
    - `-fps_mode passthrough`, not `vfr`: `vfr` still lets the encoder
      normalise spacing.

    Verify with ffprobe after changing this: avg_frame_rate must differ from
    r_frame_rate, and pts_time spacing must be irregular.
    """
    _run([*_testsrc(6, '640x480', 30),
          '-vf', "select='if(eq(n,0),1,gt(random(0),0.45))'",
          '-fps_mode', 'passthrough', *_FIXTURE_VIDEO_CODEC, str(path)])


def build_curto_webm(path: Path) -> None:
    """O mesmo assunto do `curto.mp4`, em WebM — a saída que esta build sabe
    produzir sem encoder de hardware (specs/008).

    Curto e pequeno de propósito: os testes que o usam medem **progresso** e
    **sincronia**, não qualidade, e uma codificação VP9 de 10 s em 1080p
    custaria minutos a cada execução.
    """
    _run([*_testsrc(3, '640x480', 24), *_sine(3),
          '-c:v', 'libvpx-vp9', '-b:v', '300k', '-c:a', 'libopus',
          '-shortest', str(path)])


def build_curto_wav(path: Path) -> None:
    """Áudio a **32 kHz**, e a taxa é o ponto (specs/008, FR-034).

    Uma fixture a 44100 esconderia o defeito mais provável — cair no padrão do
    encoder, que costuma ser exatamente 44100 — e o teste de "não reamostrar"
    passaria com o bug presente.
    """
    _run(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=32000:duration=2',
          '-ac', '2', str(path)])


def build_animado_gif(path: Path) -> None:
    """GIF de verdade — 20 quadros, com movimento (specs/008).

    Duas propriedades da fixture importam, e as duas foram descobertas por um
    teste que passou sem provar nada:

    - **movimento**: um GIF de quadros idênticos comprime ao mínimo em qualquer
      configuração, e um teste sobre paleta e dithering aprovaria tudo;
    - **tamanho acima de 480p**: numa fixture pequena, pedir "reduza para 480p"
      não reduz nada — ela já cabe — e o teste de redução comparava um arquivo
      recodificado contra o original, que às vezes sai maior.
    """
    _run(['-f', 'lavfi', '-i', 'testsrc=duration=2:size=640x480:rate=10',
          '-vf', 'split[a][b];[a]palettegen[p];[b][p]paletteuse',
          '-loop', '0', str(path)])


def build_um_quadro_gif(path: Path) -> None:
    """GIF de **um quadro só** — o caso de borda do FR-007.

    Um arquivo assim é uma imagem, não uma animação, e a diferença decide quais
    controles a tela oferece.
    """
    _run(['-f', 'lavfi', '-i', 'color=c=orange:size=64x64:d=1',
          '-frames:v', '1', str(path)])


def build_longo(path: Path) -> None:
    """Over the 2 h ceiling. Cheap to encode despite its length: a static
    source at a low frame rate and tiny resolution — what matters is the
    duration ffprobe reports, not the picture."""
    _run(['-f', 'lavfi', '-i', 'color=c=black:size=320x240:rate=1:duration=7500',
          *_FIXTURE_VIDEO_CODEC, str(path)])


BUILDERS = {
    'curto.mp4': build_curto,
    'sem_audio.mp4': build_sem_audio,
    'vfr.mp4': build_vfr,
    'curto.webm': build_curto_webm,
    'curto.wav': build_curto_wav,
    'animado.gif': build_animado_gif,
    'um_quadro.gif': build_um_quadro_gif,
}

OPTIONAL_BUILDERS = {'longo.mp4': build_longo}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='rebuild fixtures that already exist')
    parser.add_argument('--with-long', action='store_true', help='also build longo.mp4 (slow)')
    args = parser.parse_args()

    builders = dict(BUILDERS)
    if args.with_long:
        builders.update(OPTIONAL_BUILDERS)

    for name, build in builders.items():
        path = FIXTURES_DIR / name
        if path.exists() and not args.force:
            print(f'{name}: já existe, pulando')
            continue
        print(f'{name}: gerando...')
        build(path)
        print(f'{name}: {path.stat().st_size} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

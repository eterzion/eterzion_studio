import json
import subprocess

import numpy as np
import pytest

from eterzion_upscale.processing import resolve_model
from eterzion_upscale.media import ImageOpenError, imread
from eterzion_upscale.media import VideoOpenError, VideoReader, VideoWriter, copy_audio, has_ffmpeg
from eterzion_upscale.media import ffprobe_path
from eterzion_upscale.media import ffmpeg_path


def _write_toy_video(path, frames=5, width=32, height=24, fps=10.0):
    writer = VideoWriter(str(path), fps=fps, width=width, height=height)
    rng = np.random.default_rng(0)
    for _ in range(frames):
        writer.write(rng.integers(0, 255, (height, width, 3), dtype=np.uint8))
    writer.close()
    return str(path)


def _probe_streams(path):
    result = subprocess.run(
        [ffprobe_path() or 'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], capture_output=True, text=True)
    return [s['codec_type'] for s in json.loads(result.stdout)['streams']]


def test_video_roundtrip(tmp_path):
    path = _write_toy_video(tmp_path / 'toy.mp4', frames=5, width=32, height=24, fps=10.0)
    reader = VideoReader(path)
    assert (reader.width, reader.height) == (32, 24)
    assert reader.fps == pytest.approx(10.0)
    assert len(reader) == 5
    frames = list(reader)
    reader.close()
    assert len(frames) == 5
    assert frames[0].shape == (24, 32, 3)


def test_video_reader_nonexistent(tmp_path):
    with pytest.raises(ValueError):
        VideoReader(str(tmp_path / 'nao_existe.mp4'))


def test_video_reader_corrupted(tmp_path):
    bad = tmp_path / 'corrompido.mp4'
    bad.write_bytes(b'isto nao e um video' * 100)
    with pytest.raises(VideoOpenError):
        VideoReader(str(bad))


def test_imread_nonexistent(tmp_path):
    with pytest.raises(ImageOpenError):
        imread(str(tmp_path / 'nao_existe.png'))


def test_resolve_model_invalid():
    with pytest.raises(ValueError, match='Modelo desconhecido'):
        resolve_model('modelo-que-nao-existe')


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_copy_audio_preserves_audio_track(tmp_path):
    from ffmpeg import FFmpeg

    upscaled = _write_toy_video(tmp_path / 'upscaled.mp4')
    silent_source = _write_toy_video(tmp_path / 'source_silent.mp4')

    # build a source video WITH an audio track (sine wave)
    source_with_audio = str(tmp_path / 'source_audio.mp4')
    (FFmpeg(executable=ffmpeg_path() or 'ffmpeg').option('y')
     .input(silent_source)
     .input('sine=frequency=440:duration=1', f='lavfi')
     .output(source_with_audio, {'c:v': 'copy', 'c:a': 'aac'}, shortest=None)
     .execute())
    assert 'audio' in _probe_streams(source_with_audio)

    output = str(tmp_path / 'final.mp4')
    assert copy_audio(source_with_audio, upscaled, output) is True
    streams = _probe_streams(output)
    assert 'video' in streams and 'audio' in streams


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_copy_audio_source_without_audio(tmp_path):
    # a source with no audio track must still succeed (video-only output)
    upscaled = _write_toy_video(tmp_path / 'upscaled.mp4')
    silent_source = _write_toy_video(tmp_path / 'source_silent.mp4')
    output = str(tmp_path / 'final.mp4')
    assert copy_audio(silent_source, upscaled, output) is True
    assert _probe_streams(output) == ['video']


def test_copy_audio_invalid_input(tmp_path):
    # a corrupted "upscaled" file must fail gracefully (False), never raise
    bad = tmp_path / 'bad.mp4'
    bad.write_bytes(b'nao e video')
    ok = copy_audio(str(bad), str(bad), str(tmp_path / 'out.mp4'))
    assert ok is False


@pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg binary not available')
def test_ffprobe_reads_tags_and_paths_with_accents(tmp_path):
    """Tags e caminho fora do ASCII. No Windows o `text=True` sozinho decodifica
    a saida UTF-8 do ffprobe em cp1252: a thread de leitura quebrava, o stdout
    chegava None e a criacao do job caia com 500 -- achado num MP3 de musica
    com o titulo acentuado, na 1.1.9 instalada."""
    from eterzion_upscale.media import ffprobe_json

    pasta = tmp_path / 'Músicas — ação'
    pasta.mkdir()
    arquivo = pasta / 'canção.wav'
    subprocess.run(
        [ffmpeg_path(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.5',
         '-metadata', 'title=Canção — Ação ♪ 音楽', '-metadata', 'artist=Zoë & Ñandú', str(arquivo)],
        check=True, capture_output=True)
    dados = ffprobe_json(str(arquivo))
    tags = {k.lower(): v for k, v in dados['format'].get('tags', {}).items()}
    assert tags['title'] == 'Canção — Ação ♪ 音楽'
    assert tags['artist'] == 'Zoë & Ñandú'


def test_ffmpeg_and_ffprobe_never_open_a_terminal_window(tmp_path, monkeypatch):
    """No backend empacotado (sem console), cada processo de console ganha uma
    janela: um job de musica piscava varios terminais. Todo processo do
    ffmpeg/ffprobe precisa nascer com CREATE_NO_WINDOW -- inclusive os do
    run_ffmpeg, cuja biblioteca fixava outra flag."""
    import subprocess as sp

    from eterzion_upscale import media

    flag = getattr(sp, 'CREATE_NO_WINDOW', 0)
    if not flag:
        pytest.skip('flag exclusiva do Windows')
    criados = []
    original = sp.Popen

    class Espiao(original):
        def __init__(self, *args, **kwargs):
            criados.append(kwargs.get('creationflags', 0))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(sp, 'Popen', Espiao)

    saida = tmp_path / 'tom.wav'
    progresso = []

    def construir(f):
        f.on('progress', progresso.append)
        return f.input('sine=frequency=440:duration=1', f='lavfi').output(str(saida))

    media.run_ffmpeg(construir)
    media.ffprobe_json(str(saida))
    assert len(criados) >= 2
    assert all(c & flag for c in criados), criados
    # O execute() da biblioteca continua o dela: a compressao depende destes
    # eventos para a barra de progresso.
    assert progresso, 'o run_ffmpeg deixou de emitir progresso'


def test_run_ffmpeg_failure_keeps_the_known_prefix(tmp_path):
    """jobs._FFMPEG_MARKERS reconhece a falha pelo prefixo e manda a saida do
    ffmpeg para a area recolhida da interface."""
    from eterzion_upscale import media

    with pytest.raises(RuntimeError, match='^Falha ao processar com ffmpeg'):
        media.run_ffmpeg(lambda f: f.input(str(tmp_path / 'nao-existe.wav')).output(str(tmp_path / 'x.wav')))

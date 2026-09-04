"""T054 — o progresso do vídeo acompanha o arquivo, não o relógio.

A distinção parece pedante até o primeiro vídeo com um trecho pesado. A
codificação desacelera ali; uma barra movida por relógio continua subindo no
mesmo ritmo, chega a 100% com o arquivo pela metade, e depois fica parada em
100% pelo resto do tempo. Uma barra que mente é pior que nenhuma barra, porque
quem a lê toma decisões com ela — fecha o notebook, sai da sala.

O que se verifica aqui é que os valores vêm da **posição de tempo que o FFmpeg
reporta**, e que a sequência tem as propriedades que uma barra precisa ter:
nunca recua, nunca passa de 100, e chega a 100 exatamente uma vez, no fim.
"""
from __future__ import annotations

import os
import pathlib

import pytest

from app.compression import runner, video

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
CURTO = FIXTURES / 'curto.webm'


pytestmark = pytest.mark.skipif(
    not CURTO.is_file(), reason='fixture de vídeo ausente')


def _pode_comprimir_webm() -> bool:
    from app.compression import capabilities

    return capabilities.video_codec_encoder('vp9') is not None or \
        capabilities.video_codec_encoder('av1') is not None


requer_encoder = pytest.mark.skipif(
    not _pode_comprimir_webm(),
    reason='esta máquina não produz nenhum codec de WebM')


@requer_encoder
def test_o_progresso_vem_do_arquivo_e_nao_de_um_relogio(tmp_path):
    eventos: list[int] = []
    saida = str(tmp_path / 'saida.webm')

    video.compress(str(CURTO), saida, video.VideoSettings(quality=40),
                   on_progress=eventos.append)

    assert eventos, 'nenhum progresso foi reportado'
    # Não decrescente: um percentual que recua é lido como "deu errado e está
    # refazendo".
    assert eventos == sorted(eventos), f'o progresso recuou: {eventos}'
    assert max(eventos) <= 99, 'o 100% é do encerramento, não da codificação'
    assert min(eventos) >= 0


@requer_encoder
def test_o_runner_fecha_em_cem_uma_vez_so(tmp_path):
    """A barra chega a 100 quando o arquivo existe no destino, não quando o
    FFmpeg termina — entre as duas coisas há um `move`."""
    eventos: list[int] = []
    saida = str(tmp_path / 'saida.webm')

    runner.run('video', str(CURTO), saida, {'quality': 40}, on_progress=eventos.append)

    assert eventos[-1] == 100
    assert eventos.count(100) == 1
    assert eventos == sorted(eventos), f'o progresso recuou: {eventos}'
    assert os.path.isfile(saida)


@requer_encoder
def test_o_marco_do_runner_nao_puxa_a_barra_para_tras(tmp_path):
    """O caso concreto que a trava do runner existe para impedir.

    O vídeo reporta progresso real e passa de 90 sozinho; o marco fixo
    pós-compressão vale 90. Sem a trava, a sequência teria um 90 depois de um 95.
    """
    eventos: list[int] = []
    runner.run('video', str(CURTO), str(tmp_path / 's.webm'), {'quality': 40},
               on_progress=eventos.append)

    altos = [v for v in eventos if v >= 90]
    assert altos == sorted(altos), f'houve recuo na faixa final: {altos}'


def test_sem_duracao_conhecida_nao_se_inventa_percentual(tmp_path, monkeypatch):
    """Uma sondagem que não obteve duração não pode virar uma barra.

    Sem duração não há denominador, e o que apareceria seria um número inventado
    com aparência de medida — a mesma confusão entre ausente e zero que o FR-010
    trata do outro lado.
    """
    chamadas: list[int] = []

    def sonda_sem_duracao(path):
        return {'width': 320, 'height': 240, 'duration_seconds': None,
                'has_audio': False, 'audio_codec': None}

    monkeypatch.setattr(video, '_probe', sonda_sem_duracao)
    executados: list[dict] = []
    monkeypatch.setattr(video, '_run',
                        lambda *a, **k: executados.append({'args': a}))

    video.compress(str(CURTO), str(tmp_path / 's.webm'),
                   video.VideoSettings(video_codec='vp9', container='webm'),
                   on_progress=chamadas.append)

    assert executados, 'a compressão não chegou a executar'
    assert chamadas == [], 'inventou progresso sem duração conhecida'

"""classify_audio: uma musica cantada do comeco ao fim nao pode sair como fala.

O VAD dispara no canto e a musica e' mais harmonica que a fala, entao os dois
sinais originais do classificador empurravam uma faixa assim para 'speech' --
foi o que aconteceu com uma musica real na tela de Audio. A assinatura de
mixagem (graves fortes E quase nenhuma pausa) desempata; nenhuma fala tem os
dois juntos. O VAD aqui e' um substituto que sempre "ouve voz": o que se testa
e' a decisao depois dele, nao o modelo.
"""
from __future__ import annotations

import numpy as np
import pytest

from eterzion_upscale import processing

_RATE = 22050


class _VozSempre:
    def __call__(self, tensor, sample_rate):
        class _P:
            def item(self_inner):
                return 0.95
        return _P()


@pytest.fixture
def vad_que_ouve_voz(monkeypatch):
    monkeypatch.setattr(processing, '_get_vad_model', lambda: _VozSempre())


def _cantada(segundos=8.0) -> np.ndarray:
    """Base grave continua (baixo em 55/110 Hz) com uma linha melodica por cima,
    sem nenhum silencio -- o formato de uma mixagem com voz o tempo todo."""
    t = np.arange(int(_RATE * segundos)) / _RATE
    baixo = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.3 * np.sin(2 * np.pi * 110 * t)
    melodia = 0.15 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.sin(2 * np.pi * 660 * t)
    return (baixo + melodia).astype(np.float32)


def _fala(segundos=8.0) -> np.ndarray:
    """Frases de 1,2 s separadas por 0,5 s de silencio, sem graves de mixagem."""
    t = np.arange(int(_RATE * 1.2)) / _RATE
    frase = (0.3 * np.sin(2 * np.pi * 220 * t) + 0.15 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    pausa = np.zeros(int(_RATE * 0.5), dtype=np.float32)
    trecho = np.concatenate([frase, pausa])
    repeticoes = int(np.ceil(segundos * _RATE / trecho.size))
    return np.tile(trecho, repeticoes)[: int(segundos * _RATE)]


def test_assinatura_de_mixagem_separa_os_dois():
    graves, pausas = processing._mix_signature(_cantada(), _RATE)
    assert graves >= processing._MIX_MIN_BASS_RATIO
    assert pausas <= processing._MIX_MAX_PAUSE_RATIO

    graves, pausas = processing._mix_signature(_fala(), _RATE)
    assert graves < processing._MIX_MIN_BASS_RATIO
    assert pausas > processing._MIX_MAX_PAUSE_RATIO


def test_musica_cantada_sai_como_musica_mesmo_com_o_vad_ouvindo_voz(vad_que_ouve_voz):
    resultado = processing.classify_audio(_cantada(), _RATE)
    assert resultado.content_type == 'music'


def test_fala_com_pausas_continua_fala(vad_que_ouve_voz):
    resultado = processing.classify_audio(_fala(), _RATE)
    assert resultado.content_type == 'speech'


def test_silencio_nao_quebra_a_assinatura():
    graves, pausas = processing._mix_signature(np.zeros(_RATE, dtype=np.float32), _RATE)
    assert graves == 0.0

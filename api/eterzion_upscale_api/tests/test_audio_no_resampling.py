"""T065 — `original` não reamostra, medido no arquivo que saiu.

O teste irmão (`test_audio_lossless_controls.py`) verifica que nenhum `-ar` é
gerado. Este verifica a consequência: o arquivo produzido está na mesma taxa da
origem. São afirmações diferentes, e a distância entre elas é onde um `-ar`
acrescentado em outro lugar do caminho passaria despercebido.

A fixture está a **32 kHz** de propósito. Uma origem a 44100 esconderia o defeito
mais provável — cair no padrão do encoder, que costuma ser 44100 — e o teste
passaria com o bug presente.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from app.compression import audio, capabilities

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
ORIGEM = FIXTURES / 'curto.wav'
TAXA_DA_ORIGEM = 32000


pytestmark = pytest.mark.skipif(not ORIGEM.is_file(), reason='fixture de áudio ausente')


def _sonda(path: str) -> dict:
    from eterzion_upscale.media import ffprobe_json

    dados = ffprobe_json(path)
    stream = next(s for s in dados['streams'] if s['codec_type'] == 'audio')
    return {
        'sample_rate': int(stream['sample_rate']),
        'channels': int(stream['channels']),
        'codec': stream['codec_name'],
    }


def _requer(codec: str) -> None:
    if capabilities.audio_codec_encoder(codec) is None:
        pytest.skip(f'esta máquina não produz {codec}')


def test_a_origem_esta_onde_o_teste_pensa_que_esta():
    """Se a fixture mudar de taxa, os testes abaixo passam a não provar nada —
    e passariam em silêncio."""
    assert _sonda(str(ORIGEM))['sample_rate'] == TAXA_DA_ORIGEM


def test_original_preserva_a_taxa_da_origem(tmp_path):
    _requer('mp3')
    saida = str(tmp_path / 'saida.mp3')
    audio.compress(str(ORIGEM), saida,
                   audio.AudioSettings(output_format='mp3', sample_rate='original'))
    assert _sonda(saida)['sample_rate'] == TAXA_DA_ORIGEM


def test_sem_dizer_nada_tambem_preserva(tmp_path):
    """O padrão é não mexer. Reamostrar por omissão seria alterar a mídia sem
    ninguém ter pedido."""
    _requer('mp3')
    saida = str(tmp_path / 'saida.mp3')
    audio.compress(str(ORIGEM), saida, audio.AudioSettings(output_format='mp3'))
    assert _sonda(saida)['sample_rate'] == TAXA_DA_ORIGEM


def test_uma_taxa_escolhida_e_de_fato_aplicada(tmp_path):
    """O contraponto: não reamostrar quando pedido seria ignorar a escolha."""
    _requer('mp3')
    saida = str(tmp_path / 'saida.mp3')
    audio.compress(str(ORIGEM), saida,
                   audio.AudioSettings(output_format='mp3', sample_rate=44100))
    assert _sonda(saida)['sample_rate'] == 44100


def test_os_canais_tambem_ficam_como_estavam(tmp_path):
    _requer('mp3')
    saida = str(tmp_path / 'saida.mp3')
    audio.compress(str(ORIGEM), saida, audio.AudioSettings(output_format='mp3'))
    assert _sonda(saida)['channels'] == 2


def test_sem_perda_sai_sem_perda_e_menor_que_wav(tmp_path):
    """FLAC comprime pelo conteúdo, e o resultado tem que ser um FLAC de
    verdade — não um WAV renomeado."""
    _requer('flac')
    saida = str(tmp_path / 'saida.flac')
    aplicado = audio.compress(str(ORIGEM), saida, audio.AudioSettings(output_format='flac'))

    assert aplicado['lossless'] is True
    sondado = _sonda(saida)
    assert sondado['codec'] == 'flac'
    assert sondado['sample_rate'] == TAXA_DA_ORIGEM
    assert os.path.getsize(saida) < os.path.getsize(ORIGEM)


def test_a_qualidade_nao_muda_um_arquivo_sem_perda(tmp_path):
    """FR-033 medido: dois FLACs com qualidades opostas têm que sair idênticos.

    Se saírem diferentes, algum controle de bitrate chegou ao encoder — e o
    slider que a interface esconde estaria fazendo efeito por baixo.
    """
    _requer('flac')
    alto = str(tmp_path / 'alto.flac')
    baixo = str(tmp_path / 'baixo.flac')
    audio.compress(str(ORIGEM), alto, audio.AudioSettings(output_format='flac', quality=100))
    audio.compress(str(ORIGEM), baixo, audio.AudioSettings(output_format='flac', quality=1))

    assert os.path.getsize(alto) == os.path.getsize(baixo)


def test_a_origem_continua_intacta(tmp_path):
    """Princípio XV."""
    import hashlib

    _requer('mp3')
    antes = hashlib.sha256(ORIGEM.read_bytes()).hexdigest()
    audio.compress(str(ORIGEM), str(tmp_path / 's.mp3'),
                   audio.AudioSettings(output_format='mp3'))
    assert hashlib.sha256(ORIGEM.read_bytes()).hexdigest() == antes


def test_a_saida_nunca_e_a_origem():
    with pytest.raises(audio.AudioCompressionError) as erro:
        audio.compress(str(ORIGEM), str(ORIGEM), audio.AudioSettings())
    assert erro.value.reason == 'source_would_be_overwritten'

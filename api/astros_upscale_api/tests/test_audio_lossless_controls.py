"""T065 — as duas regras do áudio, e as duas são sobre não fingir controle.

**FR-033**: formato sem perda não tem bitrate a escolher. Um controle que aceita
um valor e não faz nada com ele é pior que a sua ausência — a pessoa move o
slider, vê o arquivo sair do mesmo tamanho, e conclui que o produto está
quebrado. A ausência do controle é uma afirmação verdadeira.

**FR-034**: `original` não reamostra. A alternativa que parece equivalente — ler
a taxa da origem e passá-la de volta — não é: quando a sondagem falha ou o
arquivo não declara, o que sai é um valor adivinhado, e o áudio é reamostrado sem
ninguém ter pedido. Reamostrar é conversão com perda.

Os dois são verificados **nas opções que chegam ao FFmpeg**, e não no arquivo
produzido. É a diferença entre "o resultado parece certo" e "o pedido foi certo":
um `-ar` a mais pode não mudar nada num arquivo que já está na taxa pedida, e
passaria despercebido até o arquivo que estivesse noutra.
"""
from __future__ import annotations

import pytest

from app.compression import audio, config


# ------------------------- sem perda não tem bitrate ------------------------- #

@pytest.mark.parametrize('codec', sorted(config.AUDIO_CODECS_LOSSLESS))
def test_codec_sem_perda_nao_recebe_bitrate(codec):
    opcoes = audio._rate_options(codec, audio.AudioSettings(quality=30, bitrate_bps=64000))
    assert 'b:a' not in opcoes
    assert 'q:a' not in opcoes
    assert opcoes == {}, f'{codec} recebeu opções de taxa: {opcoes}'


@pytest.mark.parametrize('codec', ['mp3', 'aac', 'opus', 'vorbis'])
def test_codec_com_perda_recebe_bitrate(codec):
    """O contraponto: omitir onde deveria haver seria igualmente errado, e mais
    difícil de notar — o arquivo sairia no padrão do encoder."""
    opcoes = audio._rate_options(codec, audio.AudioSettings(quality=70))
    assert 'b:a' in opcoes or 'q:a' in opcoes


def test_formato_sem_perda_e_reconhecido_pelo_formato_e_nao_por_lista_paralela():
    """A interface pergunta sobre o **formato**, não sobre o codec.

    Uma lista paralela de "formatos sem perda" sairia de sincronia com
    `AUDIO_FORMATS` no primeiro formato acrescentado.
    """
    assert audio.lossless_format('flac')
    assert audio.lossless_format('wav')
    assert not audio.lossless_format('mp3')
    assert not audio.lossless_format('opus')
    # OGG aceita Vorbis e Opus, os dois com perda.
    assert not audio.lossless_format('ogg')


def test_um_formato_desconhecido_nao_e_declarado_sem_perda():
    """`False` por não saber é o lado seguro: declarar sem perda esconderia o
    controle de bitrate de um formato que precisa dele."""
    assert not audio.lossless_format('inventado')


def test_a_qualidade_vira_um_degrau_de_bitrate_reconhecivel():
    """Interpolar linearmente produziria 187 kbps — um número que nenhum player
    exibe de forma reconhecível e que ninguém pediria."""
    degraus_bps = {k * 1000 for k in config.AUDIO_BITRATE_PRESETS_KBPS}
    for qualidade in range(0, 101, 5):
        opcoes = audio._rate_options('aac', audio.AudioSettings(quality=qualidade))
        assert opcoes['b:a'] in degraus_bps


def test_qualidade_maior_nunca_produz_bitrate_menor():
    anterior = 0
    for qualidade in range(0, 101, 5):
        atual = audio._rate_options('aac', audio.AudioSettings(quality=qualidade))['b:a']
        assert atual >= anterior, f'qualidade {qualidade} baixou o bitrate'
        anterior = atual


# ------------------------- original não reamostra ------------------------- #

@pytest.mark.parametrize('valor', [None, 'original', ''])
def test_sample_rate_original_nao_gera_argumento(valor):
    assert audio._sample_rate_options(audio.AudioSettings(sample_rate=valor)) == {}


def test_sample_rate_escolhido_gera_argumento():
    opcoes = audio._sample_rate_options(audio.AudioSettings(sample_rate=44100))
    assert opcoes == {'ar': 44100}


def test_sample_rate_fora_da_tabela_e_recusado():
    """Recusar em vez de aceitar e deixar o FFmpeg falhar no meio: a recusa aqui
    fala do que a pessoa escolheu, e a de lá falaria do interior do FFmpeg."""
    with pytest.raises(audio.AudioCompressionError) as erro:
        audio._sample_rate_options(audio.AudioSettings(sample_rate=12345))
    assert erro.value.reason == 'invalid_settings'
    assert erro.value.detail['supported']


@pytest.mark.parametrize('valor', [None, 'original', ''])
def test_canais_original_tambem_nao_gera_argumento(valor):
    """Mesma regra, mesma razão: rebaixar estéreo para mono é uma escolha, e
    fazê-la sozinho é alterar a mídia por conta própria."""
    assert audio._channel_options(audio.AudioSettings(channels=valor)) == {}


def test_canais_escolhidos_geram_argumento():
    assert audio._channel_options(audio.AudioSettings(channels=1)) == {'ac': 1}


# ------------------------- formato e codec ------------------------- #

def test_o_formato_decide_quais_codecs_sao_aceitos():
    with pytest.raises(audio.AudioCompressionError) as erro:
        audio._resolve_codec('mp3', audio.AudioSettings(codec='opus'))
    assert erro.value.reason == 'incompatible_combination'


def test_sem_escolha_o_codec_e_resolvido():
    """O modo Básico não escolhe codec (FR-039)."""
    from app.compression import capabilities

    for formato, aceitos in config.AUDIO_FORMATS.items():
        possiveis = [c for c in aceitos if capabilities.audio_codec_encoder(c) is not None]
        if not possiveis:
            continue
        assert audio._resolve_codec(formato, audio.AudioSettings()) in possiveis


def test_numero_invalido_e_recusado_com_o_nome_do_campo():
    """A mensagem nomeia o campo porque é o que a interface precisa para apontar
    o controle certo."""
    with pytest.raises(audio.AudioCompressionError) as erro:
        audio._channel_options(audio.AudioSettings(channels='muitos'))
    assert 'channels' in str(erro.value)

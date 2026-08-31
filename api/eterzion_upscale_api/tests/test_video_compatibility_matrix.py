"""T057 — combinação incompatível nunca é oferecida e nunca é aceita em silêncio (FR-046).

As duas metades importam por motivos diferentes.

**Nunca oferecida** é sobre não fazer a pessoa perder tempo montando uma
configuração que não pode existir. AAC dentro de WebM não é um formato raro: é um
formato que não existe.

**Nunca aceita em silêncio** é sobre o que acontece quando a interface erra, ou
quando um preset antigo é aplicado depois de o produto mudar. Tolerar produziria
um arquivo — o FFmpeg costuma escolher alguma coisa quando o pedido não faz
sentido — e o arquivo produzido não seria o que foi pedido. Um erro é melhor que
um resultado que ninguém consegue explicar.
"""
from __future__ import annotations

import itertools

import pytest

from app.compression import capabilities, config, video


# ------------------------- nunca oferecida ------------------------- #

def test_a_matriz_publicada_bate_com_a_configuracao():
    """O que a rota de capacidades diz que combina tem que ser o que combina.

    Se as duas divergirem, a interface desabilita o que funciona ou oferece o
    que não funciona — e nos dois casos a culpa apareceria como bug do backend.
    """
    publicada = capabilities.compatibility()
    for container, spec in config.VIDEO_CONTAINERS.items():
        assert container in publicada
        assert set(publicada[container]['video']) <= set(spec.video_codecs)
        assert set(publicada[container]['audio']) <= set(spec.audio_codecs)


def test_a_matriz_publicada_so_lista_o_que_esta_maquina_produz():
    """Listar um codec que esta máquina não consegue produzir seria oferecer
    uma escolha que falha depois — a falha tardia que o Princípio XIII trata."""
    publicada = capabilities.compatibility()
    for container, combinacoes in publicada.items():
        for codec in combinacoes['video']:
            assert capabilities.video_codec_encoder(codec) is not None, \
                f'{container} oferece {codec}, que esta máquina não produz'
        for codec in combinacoes['audio']:
            assert capabilities.audio_codec_encoder(codec) is not None, \
                f'{container} oferece áudio {codec}, que esta máquina não produz'


def test_webm_nunca_oferece_aac_nem_mp3():
    """O caso concreto: um container que só aceita áudio livre.

    Escrito por nome e não derivado da configuração de propósito — se alguém
    acrescentar AAC ao WebM na tabela, o teste que lê a tabela concordaria com a
    mudança e este não.
    """
    webm = config.VIDEO_CONTAINERS['webm']
    assert 'aac' not in webm.audio_codecs
    assert 'mp3' not in webm.audio_codecs
    assert 'h264' not in webm.video_codecs


# ------------------------- nunca aceita em silêncio ------------------------- #

def _incompativeis() -> list[tuple[str, str]]:
    """Todo par (container, codec) que a tabela **não** permite."""
    todos = set(config.VIDEO_CODEC_ENCODERS)
    return [(container, codec)
            for container, spec in config.VIDEO_CONTAINERS.items()
            for codec in sorted(todos - set(spec.video_codecs))]


@pytest.mark.parametrize('container,codec', _incompativeis())
def test_codec_de_video_incompativel_e_recusado(container, codec):
    with pytest.raises(video.VideoCompressionError) as erro:
        video._resolve_codec(container, video.VideoSettings(video_codec=codec))
    assert erro.value.reason == 'incompatible_combination'
    # O detalhe nomeia os dois lados: sem isso a interface não tem como dizer
    # qual dos dois controles a pessoa deveria mexer.
    assert erro.value.detail['container'] == container
    assert erro.value.detail['codec'] == codec


def _audios_incompativeis() -> list[tuple[str, str]]:
    todos = set(config.AUDIO_CODEC_ENCODERS)
    return [(container, codec)
            for container, spec in config.VIDEO_CONTAINERS.items()
            for codec in sorted(todos - set(spec.audio_codecs))]


@pytest.mark.parametrize('container,codec', _audios_incompativeis())
def test_codec_de_audio_incompativel_e_recusado(container, codec):
    origem = {'has_audio': True, 'audio_codec': 'aac'}
    with pytest.raises(video.VideoCompressionError) as erro:
        video._audio_codec_applied(
            container, video.VideoSettings(audio_codec=codec), origem)
    assert erro.value.reason == 'incompatible_combination'


def test_todo_par_permitido_e_de_fato_aceito():
    """O outro lado da mesma moeda: recusar o que é válido seria igualmente
    errado, e mais difícil de perceber — a pessoa concluiria que o produto não
    suporta o que ela pediu."""
    for container, spec in config.VIDEO_CONTAINERS.items():
        for codec in spec.video_codecs:
            if capabilities.video_codec_encoder(codec) is None:
                continue  # esta máquina não produz; é outra recusa, não esta
            resolvido = video._resolve_codec(
                container, video.VideoSettings(video_codec=codec))
            assert resolvido == codec


def test_container_desconhecido_e_recusado():
    with pytest.raises(video.VideoCompressionError) as erro:
        video._resolve_codec('inventado', video.VideoSettings())
    assert erro.value.reason == 'invalid_settings'


# ------------------------- resolução automática ------------------------- #

def test_sem_escolha_o_codec_e_resolvido_e_nao_exigido():
    """O modo Básico não escolhe codec, e o produto ainda tem que produzir o
    melhor arquivo possível aqui (FR-039)."""
    for container, spec in config.VIDEO_CONTAINERS.items():
        possiveis = [c for c in spec.video_codecs
                     if capabilities.video_codec_encoder(c) is not None]
        if not possiveis:
            continue
        escolhido = video._resolve_codec(container, video.VideoSettings())
        assert escolhido in possiveis


def test_h264_e_h265_so_saem_de_hardware_nesta_build():
    """A restrição de licenciamento, verificada e não assumida.

    `libx264` e `libx265` são GPL e não estão na build LGPL que o produto
    distribui. Se um dia um encoder por software de H.264 aparecer disponível,
    este teste falha — e falhar é o certo, porque significaria que a build
    mudou e o licenciamento precisa ser reexaminado antes de o produto sair.
    """
    for codec in ('h264', 'h265'):
        for encoder in config.VIDEO_CODEC_ENCODERS[codec]:
            assert video.encoder_is_hardware(encoder), \
                f'{codec} lista {encoder}, que não é de hardware'


def test_a_preferencia_por_gpu_cai_para_cpu_em_vez_de_recusar():
    """Pedir GPU numa máquina sem GPU utilizável não é erro (FR-047).

    Recusar o trabalho trocaria um arquivo um pouco mais lento por nenhum
    arquivo.
    """
    for codec in config.VIDEO_CODEC_ENCODERS:
        disponivel = capabilities.video_codec_encoder(codec) is not None
        escolhido = video.resolve_encoder_preference(codec, 'gpu')
        assert (escolhido is not None) == disponivel


def test_a_preferencia_automatica_prefere_qualidade_a_velocidade():
    """FR-048: a um mesmo tamanho, o encoder por software produz imagem melhor.

    O hardware entra quando é a única forma de produzir aquele codec, ou quando
    a pessoa pede — nunca por ser mais rápido.
    """
    for codec, encoders in config.VIDEO_CODEC_ENCODERS.items():
        software = [e for e in encoders
                    if not video.encoder_is_hardware(e) and capabilities.encoder_works(e)]
        if not software:
            continue
        assert video.resolve_encoder_preference(codec, None) in software
        assert video.resolve_encoder_preference(codec, 'auto') in software

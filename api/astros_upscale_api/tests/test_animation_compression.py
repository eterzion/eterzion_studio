"""T071/T072 — o resultado continua animado, e um quadro só é imagem.

Três propriedades, e cada uma existe por um defeito que já aconteceu em produtos
que fazem isto:

- **o resultado continua animado.** A cadeia de paleta é fácil de montar errado
  de um jeito que produz um único quadro — e um GIF de um quadro tem exatamente
  a aparência do primeiro quadro do original, então uma inspeção visual rápida
  aprova;
- **a ordem dos quadros é preservada.** `split` duplica o fluxo, e um erro na
  cadeia pode reordenar ou repetir;
- **um GIF de um quadro é uma imagem** (FR-007). Tratá-lo como animação
  ofereceria controles de FPS e de otimização de quadros para um arquivo que não
  tem o que otimizar.
"""
from __future__ import annotations

import os
import pathlib

import pytest

from app.compression import animation, detect

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
ANIMADO = FIXTURES / 'animado.gif'
UM_QUADRO = FIXTURES / 'um_quadro.gif'


pytestmark = pytest.mark.skipif(
    not (ANIMADO.is_file() and UM_QUADRO.is_file()),
    reason='fixtures de GIF ausentes')


def _quadros(path: str) -> int:
    """Conta quadros de fato lidos, e não o que o cabeçalho declara.

    `nb_frames` num GIF costuma vir ausente; `-count_frames` decodifica. É mais
    caro e é o único número em que se pode confiar aqui.
    """
    import json
    import subprocess

    from astros_upscale.media import ffprobe_path

    resultado = subprocess.run(
        [ffprobe_path() or 'ffprobe', '-v', 'error', '-count_frames',
         '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
         '-of', 'json', path],
        capture_output=True, text=True, timeout=60)
    dados = json.loads(resultado.stdout)
    return int(dados['streams'][0]['nb_read_frames'])


# ------------------------- continua animado ------------------------- #

def test_a_fixture_tem_mais_de_um_quadro():
    """Se ela deixar de ter, os testes abaixo passam a não provar nada — e
    passariam em silêncio."""
    assert _quadros(str(ANIMADO)) > 1


def test_o_resultado_continua_animado(tmp_path):
    saida = str(tmp_path / 'saida.gif')
    animation.compress(str(ANIMADO), saida, animation.AnimationSettings(quality=50))
    assert _quadros(saida) > 1, 'a compressão achatou a animação num quadro'


def test_a_contagem_de_quadros_e_preservada_sem_mudar_o_fps(tmp_path):
    """Sem tocar em FPS, sair com menos quadros seria perder animação — não
    comprimir."""
    saida = str(tmp_path / 'saida.gif')
    animation.compress(str(ANIMADO), saida, animation.AnimationSettings(quality=50))
    assert _quadros(saida) == _quadros(str(ANIMADO))


def test_reduzir_o_fps_reduz_os_quadros(tmp_path):
    """O contraponto: pedir metade dos quadros e receber todos significaria que
    o controle não faz nada."""
    original = _quadros(str(ANIMADO))
    saida = str(tmp_path / 'saida.gif')
    animation.compress(str(ANIMADO), saida, animation.AnimationSettings(fps=5))
    assert _quadros(saida) < original


def test_comprimir_de_fato_reduz(tmp_path):
    saida = str(tmp_path / 'saida.gif')
    animation.compress(str(ANIMADO), saida,
                       animation.AnimationSettings(quality=20, resolution='480p'))
    assert os.path.getsize(saida) < os.path.getsize(ANIMADO)


def test_menos_cores_produz_arquivo_menor(tmp_path):
    """O controle de cores é o principal no GIF, e é onde ele precisa ter
    efeito medível."""
    muitas = str(tmp_path / 'muitas.gif')
    poucas = str(tmp_path / 'poucas.gif')
    animation.compress(str(ANIMADO), muitas, animation.AnimationSettings(max_colors=256))
    animation.compress(str(ANIMADO), poucas, animation.AnimationSettings(max_colors=8))
    assert os.path.getsize(poucas) < os.path.getsize(muitas)


# ------------------------- um quadro é imagem ------------------------- #

def test_gif_de_um_quadro_nao_e_animacao():
    assert not animation.is_animated(str(UM_QUADRO))


def test_gif_com_movimento_e_animacao():
    assert animation.is_animated(str(ANIMADO))


def test_a_deteccao_classifica_um_quadro_como_imagem():
    """FR-007, no lugar onde a interface lê a resposta."""
    assert detect.detect_media_kind(str(UM_QUADRO)) == 'image'
    assert detect.detect_media_kind(str(ANIMADO)) == 'animation'


def test_uma_contagem_nao_obtida_nao_vira_animacao(tmp_path, monkeypatch):
    """`None` não é `0` e também não é "muitos".

    Classificar como imagem é o lado recuperável do erro; o contrário ofereceria
    controles de quadros para um arquivo de um quadro.
    """
    monkeypatch.setattr(animation, 'frame_count', lambda _: None)
    assert not animation.is_animated(str(ANIMADO))


# ------------------------- recusas e limites ------------------------- #

def test_dithering_desconhecido_e_recusado():
    with pytest.raises(animation.AnimationCompressionError) as erro:
        animation._dither_for(animation.AnimationSettings(dither='inventado'))
    assert erro.value.reason == 'invalid_settings'
    assert erro.value.detail['supported']


def test_cores_fora_da_faixa_sao_recusadas():
    with pytest.raises(animation.AnimationCompressionError):
        animation._colors_for(animation.AnimationSettings(max_colors=1000))


def test_a_paleta_e_gerada_depois_da_escala(tmp_path):
    """A ordem da cadeia, verificada na cadeia.

    Gerar a paleta sobre o material original e aplicá-la a quadros já reduzidos
    escolheria cores para uma imagem que não existe mais — e o resultado
    pareceria apenas "um pouco pior", que é o tipo de defeito que ninguém
    rastreia até a ordem dos filtros.
    """
    saida = str(tmp_path / 's.gif')
    # Largura explícita, e não um degrau nomeado: a fixture cabe em 480p, e um
    # degrau que não reduz não produz `scale=` na cadeia — o teste passaria a
    # verificar a ausência de algo em vez da ordem.
    aplicado = animation.compress(
        str(ANIMADO), saida, animation.AnimationSettings(width=320, fps=5))
    cadeia = aplicado['filter_complex']
    assert cadeia.index('fps=') < cadeia.index('split')
    assert cadeia.index('scale=') < cadeia.index('split')
    assert cadeia.index('split') < cadeia.index('palettegen')


def test_a_origem_continua_intacta(tmp_path):
    import hashlib

    antes = hashlib.sha256(ANIMADO.read_bytes()).hexdigest()
    animation.compress(str(ANIMADO), str(tmp_path / 's.gif'), animation.AnimationSettings())
    assert hashlib.sha256(ANIMADO.read_bytes()).hexdigest() == antes


def test_a_saida_nunca_e_a_origem():
    with pytest.raises(animation.AnimationCompressionError) as erro:
        animation.compress(str(ANIMADO), str(ANIMADO), animation.AnimationSettings())
    assert erro.value.reason == 'source_would_be_overwritten'


# ------------------------- conversão ------------------------- #

def test_gif_vira_webp_animado(tmp_path):
    from astros_upscale.media import encoder_works

    if not encoder_works('libwebp_anim'):
        pytest.skip('esta build não grava WebP animado')
    saida = str(tmp_path / 'saida.webp')
    animation.compress(str(ANIMADO), saida,
                       animation.AnimationSettings(output_format='webp'))
    assert os.path.isfile(saida) and os.path.getsize(saida) > 0


def test_gif_vira_video_sem_trilha_de_audio(tmp_path):
    """Um GIF não tem áudio, e o container não pode declarar uma trilha vazia."""
    from app.compression import capabilities

    if capabilities.video_codec_encoder('vp9') is None:
        pytest.skip('esta máquina não produz WebM')
    saida = str(tmp_path / 'saida.webm')
    aplicado = animation.compress(str(ANIMADO), saida,
                                  animation.AnimationSettings(output_format='webm'))
    assert aplicado['audio_codec'] is None
    assert os.path.getsize(saida) > 0

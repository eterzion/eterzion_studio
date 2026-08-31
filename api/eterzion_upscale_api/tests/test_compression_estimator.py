"""T016 — a estimativa e a resolução de tamanho alvo.

O benchmark (docs/benchmarks/compression-estimate.md) mede a *precisão*. Estes
testes fixam o *comportamento*: que um alvo impossível seja recusado antes, que
a estimativa não invente número quando não sabe, e que as premissas viajem junto
com a resposta.

A distinção importa: precisão se remede quando o Pillow muda; comportamento não
pode regredir nunca.
"""
from __future__ import annotations

import os

import pytest
from PIL import Image

from app.compression import config, estimator


@pytest.fixture
def imagem(tmp_path):
    """Ruído, não cor chapada: uma imagem lisa comprime a quase nada e
    esconderia erros de proporção que só aparecem com conteúdo real."""
    import random

    rng = random.Random(0)
    img = Image.new('RGB', (800, 600))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(800 * 600)])
    caminho = tmp_path / 'origem.png'
    img.save(caminho)
    return str(caminho)


# ------------------------------- unidades ------------------------------- #

def test_as_unidades_sao_decimais_e_nao_binarias():
    """"5 MB" num limite de upload, num aviso de e-mail e no gerenciador de
    arquivos significa 5.000.000 bytes. Usar 1024 faria o arquivo passar de um
    limite que a pessoa acertou — e a Central existe para caber nesses limites."""
    assert estimator.target_to_bytes(5, 'MB') == 5_000_000
    assert estimator.target_to_bytes(1, 'GB') == 1_000_000_000
    assert estimator.target_to_bytes(500, 'KB') == 500_000


def test_unidade_desconhecida_levanta():
    with pytest.raises(ValueError):
        estimator.target_to_bytes(1, 'TB')


# ------------------------------- imagem ------------------------------- #

def test_estima_e_declara_como_mediu(imagem):
    est = estimator.estimate_image(imagem, output_format='jpeg', quality=80)
    assert est.estimated_bytes and est.estimated_bytes > 0
    assert est.confidence == 'measured_sample'
    # As premissas não são decoração: são o que permite à interface ser honesta
    # sobre o que a estimativa não sabe.
    assert 'native_resolution_crops' in est.assumptions


def test_qualidade_menor_estima_arquivo_menor(imagem):
    alta = estimator.estimate_image(imagem, output_format='jpeg', quality=90)
    baixa = estimator.estimate_image(imagem, output_format='jpeg', quality=20)
    assert baixa.estimated_bytes < alta.estimated_bytes


def test_reduzir_a_resolucao_estima_arquivo_menor(imagem):
    inteira = estimator.estimate_image(imagem, output_format='jpeg', quality=80)
    metade = estimator.estimate_image(imagem, output_format='jpeg', quality=80,
                                      target_size=(400, 300))
    assert metade.estimated_bytes < inteira.estimated_bytes


def test_imagem_ilegivel_e_nao_estimavel_e_nao_erro(tmp_path):
    """Uma imagem quebrada é uma resposta ("não sei"), não uma exceção que
    derruba a rota chamada a cada movimento de slider."""
    ruim = tmp_path / 'quebrada.png'
    ruim.write_bytes(b'isto nao e um png')
    est = estimator.estimate_image(str(ruim), output_format='jpeg', quality=80)
    assert est.estimated_bytes is None
    assert est.feasibility == 'not_estimable'


def test_a_estimativa_nao_escreve_nada(imagem, tmp_path):
    """`POST /compression/estimate` é chamada a cada mudança de controle. Efeito
    colateral aqui seriam dezenas de arquivos por sessão."""
    antes = set(os.listdir(tmp_path))
    estimator.estimate_image(imagem, output_format='webp', quality=70)
    assert set(os.listdir(tmp_path)) == antes


def test_uma_imagem_menor_que_o_recorte_ainda_estima(tmp_path):
    """Cai para o ponto único e **declara** que caiu, em vez de fingir a mesma
    confiança."""
    pequena = tmp_path / 'pequena.png'
    Image.new('RGB', (64, 48), (200, 30, 90)).save(pequena)
    est = estimator.estimate_image(str(pequena), output_format='png', quality=80)
    assert est.estimated_bytes is not None
    assert 'single_point_fallback' in est.assumptions
    assert est.confidence == 'derived'


# ------------------------------- vídeo ------------------------------- #

def test_video_estima_por_bitrate_vezes_duracao():
    est = estimator.estimate_video(original_bytes=100_000_000, duration_seconds=60,
                                   video_bitrate_bps=2_000_000,
                                   audio_bitrate_bps=128_000, container='mp4')
    # (2.000.000 + 128.000) x 60 / 8 = 15,96 MB, mais overhead
    assert 15_900_000 < est.estimated_bytes < 16_400_000
    assert est.confidence == 'derived'


def test_qualidade_constante_admite_que_nao_sabe():
    """Sem tabela calibrada, um número teria a mesma aparência de um medido.

    Preferir o silêncio é a escolha: a interface diz que não sabe, e isso é
    verdade, enquanto um chute com cara de estimativa não é."""
    est = estimator.estimate_video(original_bytes=1000, duration_seconds=60,
                                   video_bitrate_bps=None, audio_bitrate_bps=128_000,
                                   container='mp4')
    assert est.estimated_bytes is None
    assert est.feasibility == 'not_estimable'
    assert 'no_calibrated_table' in est.assumptions


def test_sem_duracao_nao_ha_o_que_estimar():
    est = estimator.estimate_video(original_bytes=1000, duration_seconds=0,
                                   video_bitrate_bps=1_000_000, audio_bitrate_bps=0,
                                   container='mp4')
    assert est.feasibility == 'not_estimable'


# ------------------------------- áudio ------------------------------- #

def test_audio_lossy_estima_e_lossless_nao():
    lossy = estimator.estimate_audio(original_bytes=50_000_000, duration_seconds=180,
                                     bitrate_bps=128_000)
    assert lossy.estimated_bytes == pytest.approx(128_000 * 180 / 8, rel=0.01)

    # FLAC varia demais entre silêncio e música densa para um número único
    # significar alguma coisa.
    lossless = estimator.estimate_audio(original_bytes=50_000_000, duration_seconds=180,
                                        bitrate_bps=None, lossless=True)
    assert lossless.estimated_bytes is None
    assert 'lossless_depends_on_content' in lossless.assumptions


# ------------------------------- tamanho alvo ------------------------------- #

def test_alvo_atingivel_devolve_o_bitrate_que_cabe():
    bps, viabilidade = estimator.resolve_video_target(
        target_bytes=8_000_000, duration_seconds=60, audio_bitrate_bps=128_000,
        height=1080, container='mp4')
    assert viabilidade == 'ok'
    assert bps > config.video_bitrate_floor(1080)


def test_alvo_abaixo_do_piso_e_recusado_antes_de_processar():
    """FR-020. `below_floor` é resposta, não erro: o alvo é pergunta legítima e
    a resposta é "só destruindo a mídia". Processar e entregar algo ilegível
    seria pior que recusar."""
    bps, viabilidade = estimator.resolve_video_target(
        target_bytes=100_000, duration_seconds=7200, audio_bitrate_bps=128_000,
        height=1080, container='mp4')
    assert viabilidade == 'below_floor'
    assert bps is None


def test_o_piso_acompanha_a_resolucao():
    """4K precisa de muito mais bitrate que 480p para o mesmo julgamento de
    "ainda utilizável"."""
    assert config.video_bitrate_floor(2160) > config.video_bitrate_floor(1080)
    assert config.video_bitrate_floor(1080) > config.video_bitrate_floor(480)


def test_o_piso_usa_o_degrau_imediatamente_abaixo():
    """Interpolar daria número mais bonito e não mais verdadeiro: o piso é um
    julgamento sobre utilizabilidade, não uma curva."""
    assert config.video_bitrate_floor(1200) == config.video_bitrate_floor(1080)
    assert config.video_bitrate_floor(10) == config.VIDEO_BITRATE_FLOOR_BPS[0]


def test_alvo_de_audio_abaixo_do_piso_e_recusado():
    bps, viabilidade = estimator.resolve_audio_target(target_bytes=1000, duration_seconds=600)
    assert viabilidade == 'below_floor' and bps is None


def test_alvo_de_imagem_encontra_a_qualidade_que_cabe(imagem):
    original = os.path.getsize(imagem)
    alvo = original // 4
    qualidade, viabilidade = estimator.resolve_image_target(
        imagem, output_format='jpeg', target_bytes=alvo)
    assert viabilidade == 'ok'
    assert 1 <= qualidade <= 100
    # E a qualidade encontrada de fato cabe.
    est = estimator.estimate_image(imagem, output_format='jpeg', quality=qualidade)
    assert est.estimated_bytes <= alvo


def test_alvo_de_imagem_impossivel_e_declarado(imagem):
    _, viabilidade = estimator.resolve_image_target(
        imagem, output_format='jpeg', target_bytes=50)
    assert viabilidade == 'below_floor'


def test_formato_sem_perda_nao_tem_qualidade_a_buscar(imagem):
    """PNG ignora qualidade: ou cabe, ou o alvo exige trocar o formato. Buscar
    seria fingir um controle que não existe."""
    qualidade, viabilidade = estimator.resolve_image_target(
        imagem, output_format='png', target_bytes=10)
    assert qualidade is None
    assert viabilidade == 'below_floor'


# ------------------------------- forma ------------------------------- #

def test_a_resposta_carrega_economia_e_reducao_calculadas():
    est = estimator.Estimate(original_bytes=1000, estimated_bytes=250,
                             confidence='derived')
    assert est.saving_bytes == 750
    assert est.reduction_ratio == pytest.approx(0.75)


def test_sem_estimativa_nao_ha_economia_inventada():
    est = estimator.Estimate(original_bytes=1000, estimated_bytes=None, confidence='rough')
    assert est.saving_bytes is None
    assert est.reduction_ratio is None
    assert est.as_dict()['estimated_saving_bytes'] is None

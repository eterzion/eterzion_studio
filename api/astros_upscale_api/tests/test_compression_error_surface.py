"""T088/T089 — o que a pessoa lê, e o que o log guarda.

São dois destinos com regras opostas, e é justamente por isso que precisam ser
separados por construção em vez de por cuidado.

**A interface** recebe uma razão em chave e nenhum nome de encoder (Princípio V).
A saída bruta da ferramenta vai num campo à parte porque é indispensável para
diagnosticar e ilegível para decidir: "Task finished with error code: -22
(Invalid argument)" não diz a ninguém o que fazer a seguir, e apresentá-la como
*a* mensagem transfere para a pessoa um trabalho que é nosso (FR-065).

**O log** recebe encoder, codec e parâmetros resolvidos — exatamente o que
responde "por que falhou na máquina dele e não na minha", e exatamente o que não
pode aparecer na tela (FR-066).
"""
from __future__ import annotations

import logging
import random

import pytest
from PIL import Image

from app.compression import runner, video

# Nomes que nunca podem sair da API. Não é a lista inteira — é a lista dos que
# este produto de fato usa, que é onde um vazamento aconteceria.
NOMES_DE_ENCODER = (
    'libx264', 'libx265', 'nvenc', 'h264_nvenc', 'hevc_nvenc', 'qsv', 'amf',
    'libvpx', 'libsvtav1', 'libaom', 'libmp3lame', 'libopus', 'libvorbis',
    'libwebp', 'pcm_s16le',
)


@pytest.fixture
def imagem(tmp_path):
    rng = random.Random(5)
    img = Image.new('RGB', (120, 90))
    img.putdata([(x % 256, y % 256, rng.randrange(256)) for y in range(90) for x in range(120)])
    caminho = tmp_path / 'foto.png'
    img.save(caminho)
    return str(caminho)


# ------------------------- o que a pessoa lê ------------------------- #

def test_a_recusa_traz_razao_em_chave_e_nao_frase_pronta(imagem, tmp_path):
    with pytest.raises(runner.CompressionRefused) as erro:
        runner.run('video', imagem, str(tmp_path / 's.mp4'), {'video_codec': 'inventado'})
    # `reason` é o que a interface traduz; a mensagem é diagnóstico.
    assert erro.value.reason
    assert erro.value.reason.islower()
    assert ' ' not in erro.value.reason


def test_nenhuma_recusa_nomeia_um_encoder(imagem, tmp_path):
    """O Princípio V medido onde ele pode vazar: uma recusa que cite `libx264`
    já é o nome do encoder na tela da pessoa."""
    tentativas = [
        ('video', {'video_codec': 'h264', 'container': 'webm'}),
        ('video', {'video_codec': 'inventado'}),
        ('video', {'container': 'inventado'}),
        ('audio', {'output_format': 'inventado'}),
        ('audio', {'sample_rate': 12345}),
        ('image', {'output_format': 'inventado'}),
        ('animation', {'dither': 'inventado'}),
    ]
    for media_kind, settings in tentativas:
        try:
            runner.validate(media_kind, settings, advanced=True)
        except runner.CompressionRefused as erro:
            texto = f'{erro.reason} {erro} {erro.detail}'.lower()
            vazou = [n for n in NOMES_DE_ENCODER if n in texto]
            assert not vazou, f'{media_kind}/{settings} vazou {vazou}: {texto}'


def test_um_codec_indisponivel_fala_do_codec_e_nao_do_encoder():
    """A pessoa escolheu "H.264"; é sobre H.264 que a recusa fala.

    A recusa por indisponibilidade vive na **validação**, e não em
    `_resolve_codec` — aquele só sabe se o container aceita o codec. Escrever o
    teste contra o lugar errado foi o que revelou a distinção: MKV aceita H.264,
    então `_resolve_codec` não levantava nada mesmo sem encoder na máquina.
    """
    from app.compression import capabilities

    if capabilities.video_codec_encoder('h264') is not None:
        pytest.skip('esta máquina produz H.264 — não há recusa a inspecionar')

    with pytest.raises(runner.CompressionRefused) as erro:
        runner.validate('video', {'video_codec': 'h264'}, advanced=True)
    assert erro.value.reason == 'encoder_unavailable'
    assert erro.value.detail['codec'] == 'h264'
    texto = f'{erro.value} {erro.value.detail}'.lower()
    assert not any(n in texto for n in NOMES_DE_ENCODER)


# ------------------------- o que o log guarda ------------------------- #

def test_o_log_registra_o_que_a_interface_nao_pode(imagem, tmp_path, caplog):
    """FR-066: encoder, codec e parâmetros resolvidos ficam no log.

    É o que responde "por que falhou na máquina dele e não na minha" — e é
    exatamente o que o Princípio V mantém fora da tela.
    """
    destino = str(tmp_path / 'saida.jpg')
    with caplog.at_level(logging.INFO, logger='astros.compression'):
        runner.run('image', imagem, destino, {'output_format': 'jpeg', 'quality': 60})

    registros = [r for r in caplog.records if hasattr(r, 'compression')]
    assert registros, 'a compressão concluída não gerou log técnico'
    dados = registros[-1].compression
    assert dados['status'] == 'done'
    assert dados['media_kind'] == 'image'
    assert dados['settings']['quality'] == 60
    assert dados['output_bytes'] > 0
    assert dados['elapsed_seconds'] >= 0


def test_a_falha_tambem_e_registrada_com_o_motivo(imagem, tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger='astros.compression'):
        with pytest.raises(runner.CompressionRefused):
            runner.run('image', imagem, str(tmp_path / 's.jpg'),
                       {'output_format': 'inventado'})

    registros = [r for r in caplog.records if hasattr(r, 'compression')]
    assert registros, 'a falha não gerou log técnico'
    dados = registros[-1].compression
    assert dados['status'] == 'error'
    assert dados['reason']


def test_o_log_nao_carrega_o_caminho_completo_da_origem(imagem, tmp_path, caplog):
    """Um log costuma ser colado num relatório de suporte. O nome do arquivo
    basta para diagnosticar; a árvore de pastas de alguém, não."""
    with caplog.at_level(logging.INFO, logger='astros.compression'):
        runner.run('image', imagem, str(tmp_path / 'saida.jpg'),
                   {'output_format': 'jpeg'})

    dados = [r for r in caplog.records if hasattr(r, 'compression')][-1].compression
    assert '/' not in dados['source'] and '\\\\' not in dados['source']

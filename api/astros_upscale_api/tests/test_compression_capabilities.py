"""T011/T013 (specs/008-compression-centre) — a Central só oferece o que a
máquina consegue, e nunca nomeia como.

Duas propriedades distintas, e confundi-las é o defeito clássico:

- **permitido** é `config.py`, propriedade do formato;
- **presente** é `capabilities.py`, sonda funcional desta máquina.

Estes testes fixam a segunda, e fixam também que a primeira nunca vira a
resposta — Princípio XIII, e condição 3 da exceção do Princípio V (v4.0.0).
"""
from __future__ import annotations

import json

import pytest

from app.compression import capabilities, config
from astros_upscale.media import GPL_ENCODERS, filter_works, has_ffmpeg

needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


# ------------------------------- vazamento ------------------------------- #

# Tudo que nomeia uma implementação em vez de uma capacidade. `test_no_codec_leak`
# faz o mesmo para as rotas de vídeo; a Central é uma superfície nova e precisa
# da sua própria guarda, porque uma superfície nova é onde a regra se perde.
NOMES_INTERNOS = (
    'nvenc', 'qsv', 'amf', 'vaapi', 'videotoolbox',
    'libx264', 'libx265', 'x264', 'x265',
    'libvpx', 'libaom', 'libsvtav1', 'librav1e',
    'libopus', 'libvorbis', 'libmp3lame', 'libwebp', 'pcm_s16le',
    'opencv', 'cv2', 'pillow', 'ffmpeg',
)


def test_o_instantaneo_nao_nomeia_nenhuma_implementacao():
    """O que sai daqui é nome público de codec e chave de motivo.

    Um nome de encoder na resposta é o Princípio V perdido — e ele se perde
    exatamente assim: alguém acrescenta um campo de diagnóstico útil.
    """
    corpo = json.dumps(capabilities.snapshot()).lower()
    vazados = [n for n in NOMES_INTERNOS if n in corpo]
    assert not vazados, f'nomes internos na resposta: {vazados}'


def test_o_motivo_e_chave_e_nao_frase():
    """A interface traduz (Princípio XIV). Uma frase aqui seria intraduzível."""
    permitidas = {'no_encoder_available', 'requires_hardware_encoder', 'unsupported_build'}
    for grupo in capabilities.snapshot().values():
        for entradas in grupo.values():
            if not isinstance(entradas, list):
                continue
            for entrada in entradas:
                if entrada['unavailable_reason'] is not None:
                    assert entrada['unavailable_reason'] in permitidas


# ------------------------------- licenciamento ------------------------------- #

def test_nenhum_encoder_gpl_esta_na_configuracao():
    """A condição 5 da exceção constitucional: licenciamento não vira escolha do
    usuário. Nenhum caminho da Central pode chegar a libx264/libx265, e a forma
    de garantir isso é eles não existirem na tabela."""
    todos = {e for candidatos in config.VIDEO_CODEC_ENCODERS.values() for e in candidatos}
    todos |= {e for candidatos in config.AUDIO_CODEC_ENCODERS.values() for e in candidatos}
    assert not (todos & GPL_ENCODERS)


def test_h264_e_h265_so_saem_de_hardware():
    """Consequência direta da restrição de licenciamento: sem encoder GPL, a
    única fonte de H.264/H.265 é hardware."""
    assert config.VIDEO_CODECS_REQUIRING_HARDWARE == {'h264', 'h265'}
    for codec in config.VIDEO_CODECS_REQUIRING_HARDWARE:
        assert all('nvenc' in e or 'qsv' in e or 'amf' in e
                   for e in config.VIDEO_CODEC_ENCODERS[codec])


@needs_ffmpeg
def test_um_codec_de_hardware_indisponivel_diz_que_e_de_hardware():
    """Motivo genérico esconderia que a pessoa não pode fazer nada a respeito
    pelo software — é questão de máquina, e dizer isso é a diferença entre uma
    recusa útil e uma opaca."""
    for entrada in capabilities.video_codecs():
        if entrada['value'] in config.VIDEO_CODECS_REQUIRING_HARDWARE:
            assert entrada['requires_hardware'] is True
            if not entrada['available']:
                assert entrada['unavailable_reason'] == 'requires_hardware_encoder'


# ------------------------------- sonda real ------------------------------- #

@needs_ffmpeg
def test_disponibilidade_vem_de_sonda_e_nao_de_tabela():
    """Compara a resposta com o que a sonda diz quando de fato mandam codificar.

    Se um dia alguém trocar a sonda por uma consulta a `ffmpeg -encoders`, este
    teste falha — e deve falhar: nesta máquina os três encoders H.264 de
    hardware estão listados e nenhum codifica um quadro.
    """
    for entrada in capabilities.video_codecs():
        esperado = capabilities.video_codec_encoder(entrada['value']) is not None
        assert entrada['available'] == esperado


@needs_ffmpeg
def test_a_compatibilidade_e_a_intersecao_das_duas_perguntas():
    """Só chega à interface o que é permitido pelo container **e** presente na
    máquina."""
    matriz = capabilities.compatibility()
    for nome, spec in config.VIDEO_CONTAINERS.items():
        assert set(matriz[nome]['video']) <= set(spec.video_codecs)
        assert set(matriz[nome]['audio']) <= set(spec.audio_codecs)
        for codec in matriz[nome]['video']:
            assert capabilities.video_codec_encoder(codec) is not None


@needs_ffmpeg
def test_container_sem_audio_utilizavel_nao_e_oferecido():
    """"Não pude codificar o áudio" no meio da exportação é a falha tardia que o
    Princípio XIII proíbe."""
    for entrada in capabilities.video_containers():
        if entrada['available']:
            spec = config.VIDEO_CONTAINERS[entrada['value']]
            assert any(capabilities.audio_codec_encoder(c) for c in spec.audio_codecs)


# ------------------------------- imagem ------------------------------- #

def test_a_sonda_de_imagem_interroga_a_biblioteca_que_grava():
    """A primeira versão sondava o OpenCV e reprovava AVIF, que o Pillow grava.

    A Decisão 1 de research.md leva a imagem da Central para o Pillow; uma sonda
    que pergunta a outra biblioteca responde sobre outra coisa. PNG e JPEG
    existem em qualquer instalação — se falharem aqui, quem quebrou foi a sonda.
    """
    assert capabilities.pillow_format_works('png')
    assert capabilities.pillow_format_works('jpeg')
    assert not capabilities.pillow_format_works('naoexiste')


def test_todo_formato_declarado_tem_resposta():
    valores = {e['value'] for e in capabilities.image_formats()}
    assert valores == set(config.IMAGE_FORMATS)


# ------------------------------- animação ------------------------------- #

@needs_ffmpeg
def test_gif_depende_dos_filtros_de_paleta_e_nao_so_do_encoder():
    """Um build com o encoder `gif` e sem `palettegen` produziria GIFs de cores
    aproximadas — pior que os de hoje, e sem aviso."""
    gif = next(e for e in capabilities.animation_formats() if e['value'] == 'gif')
    esperado = all(filter_works(f) for f in config.ANIMATION_REQUIRED_FILTERS)
    if not esperado:
        assert not gif['available']


@needs_ffmpeg
def test_a_sonda_de_filtro_respeita_a_aridade():
    """`paletteuse` tem duas entradas e `split` tem duas saídas. Sondá-los com
    `-vf <nome>` os reprova numa build que os executa perfeitamente — foi o
    falso negativo registrado na Decisão 2, e ele teria desligado a compressão
    de GIF inteira.

    Um falso negativo numa sonda de capacidade não é a falha segura que parece:
    ele remove do produto algo que a máquina faz.
    """
    assert filter_works('palettegen')
    assert filter_works('paletteuse')
    assert filter_works('split')


@needs_ffmpeg
def test_filtros_gpl_continuam_ausentes_na_build_lgpl():
    """Guarda de regressão do que a 007 corrigiu: `eq` e `hqdn3d` não existem na
    build que o instalador empacota."""
    assert not filter_works('eq')
    assert not filter_works('hqdn3d')


# ------------------------------- forma ------------------------------- #

def test_toda_entrada_tem_a_mesma_forma():
    """Disponível não carrega motivo; indisponível carrega. Um motivo pendurado
    numa entrada disponível é lixo que a interface acabaria exibindo."""
    for grupo in capabilities.snapshot().values():
        for entradas in grupo.values():
            if not isinstance(entradas, list):
                continue
            for e in entradas:
                assert set(e) == {'value', 'available', 'unavailable_reason', 'requires_hardware'}
                assert (e['unavailable_reason'] is None) == e['available']

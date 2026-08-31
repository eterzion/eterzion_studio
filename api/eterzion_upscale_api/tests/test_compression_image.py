"""T033/T035 — compressão de imagem: formatos, metadados e redimensionamento.

Cada política de metadados é verificada **lendo os metadados do arquivo
produzido**, nunca pela aparência: uma imagem sem EXIF e uma com EXIF intacto
são visualmente idênticas, e é justamente por isso que este defeito passa.
"""
from __future__ import annotations

import os

import pytest
from PIL import Image

from app.compression.image import (DEFAULT_METADATA_POLICY, ImageCompressionError,
                                   ImageSettings, compress)

_ORIENTATION = 274
_GPS_IFD = 34853
_DESCRIPTION = 270


def _com_metadados(caminho, largura=400, altura=300):
    """Uma imagem com EXIF de orientação, GPS, comentário e perfil de cor.

    O GPS entra pelo `get_ifd`, com `Fraction`: atribuir o IFD como dicionário
    de tuplas levanta na gravação, e as coordenadas precisam ser racionais.
    """
    from fractions import Fraction

    exif = Image.Exif()
    exif[_ORIENTATION] = 6
    exif[_DESCRIPTION] = 'comentario que ninguem quer publicar'
    gps = exif.get_ifd(_GPS_IFD)
    gps[1] = 'S'
    gps[2] = (Fraction(23), Fraction(33), Fraction(0))
    img = Image.new('RGB', (largura, altura), (120, 60, 200))
    img.save(caminho, format='JPEG', exif=exif,
             icc_profile=b'\x00' * 128)  # perfil sintético: basta existir
    return caminho


@pytest.fixture
def origem(tmp_path):
    return str(_com_metadados(tmp_path / 'origem.jpg'))


@pytest.fixture
def ruidosa(tmp_path):
    """Conteúdo real, não cor chapada.

    Gradiente com ruído leve, e os dois extremos foram descartados por medição:

    - **cor chapada** comprime ao mínimo em qualquer nível, e os testes de
      tamanho comparavam ruído de cabeçalho. Foi assim que a primeira versão
      afirmou que sem-perda é sempre maior que com-perda — falso justamente
      para conteúdo liso;
    - **ruído puro** é incompressível, e aí o nível de compressão do PNG não
      muda nada. Errar para esse lado deu dois arquivos idênticos.

    O que mede é conteúdo com redundância **e** detalhe: o gradiente dá o que
    comprimir, o ruído dá o que a compressão com perda joga fora.
    """
    import random

    rng = random.Random(7)
    largura, altura = 300, 200
    pixels = []
    for y in range(altura):
        for x in range(largura):
            base = int(255 * x / largura)
            pixels.append((
                max(0, min(255, base + rng.randrange(-12, 13))),
                max(0, min(255, int(255 * y / altura) + rng.randrange(-12, 13))),
                max(0, min(255, 128 + rng.randrange(-12, 13))),
            ))
    img = Image.new('RGB', (largura, altura))
    img.putdata(pixels)
    caminho = tmp_path / 'ruidosa.png'
    img.save(caminho)
    return str(caminho)


def _exif_do_arquivo(caminho) -> dict:
    with Image.open(caminho) as img:
        return dict(img.getexif())


def _tem_icc(caminho) -> bool:
    with Image.open(caminho) as img:
        return bool(img.info.get('icc_profile'))


# ------------------------------- formatos ------------------------------- #

@pytest.mark.parametrize('fmt', ['png', 'jpeg', 'webp', 'avif', 'tiff', 'bmp'])
def test_grava_os_seis_formatos(origem, tmp_path, fmt):
    saida = str(tmp_path / f'saida.{fmt}')
    aplicado = compress(origem, saida, ImageSettings(output_format=fmt, quality=80))
    assert os.path.getsize(saida) > 0
    assert aplicado['output_format'] == fmt


def test_keep_mantem_o_formato_da_origem(origem, tmp_path):
    saida = str(tmp_path / 'saida.jpg')
    aplicado = compress(origem, saida, ImageSettings(output_format='keep'))
    assert aplicado['output_format'] == 'jpeg'


def test_qualidade_menor_produz_arquivo_menor(origem, tmp_path):
    alta = str(tmp_path / 'alta.jpg')
    baixa = str(tmp_path / 'baixa.jpg')
    compress(origem, alta, ImageSettings(output_format='jpeg', quality=95))
    compress(origem, baixa, ImageSettings(output_format='jpeg', quality=30))
    assert os.path.getsize(baixa) < os.path.getsize(alta)


def test_lossless_em_formato_que_nao_tem_e_recusado(origem, tmp_path):
    """FR-026: desabilitar onde não se aplica, com motivo. Aceitar e ignorar
    prometeria uma compressão sem perda que o arquivo não tem."""
    with pytest.raises(ImageCompressionError) as erro:
        compress(origem, str(tmp_path / 'x.jpg'),
                 ImageSettings(output_format='jpeg', lossless=True))
    assert erro.value.reason == 'lossless_unsupported'


def test_transparencia_vira_branco_e_nao_halo_preto(tmp_path):
    """Descartar o alfa deixa halos pretos nas bordas — o defeito clássico.
    Compor sobre branco é a escolha."""
    com_alfa = tmp_path / 'alfa.png'
    img = Image.new('RGBA', (40, 40), (255, 0, 0, 0))
    img.save(com_alfa)

    saida = str(tmp_path / 'sem_alfa.jpg')
    compress(str(com_alfa), saida, ImageSettings(output_format='jpeg', quality=90))
    with Image.open(saida) as resultado:
        assert resultado.getpixel((20, 20)) == pytest.approx((255, 255, 255), abs=4)


# ------------------------------- origem intacta ------------------------------- #

def test_a_saida_nunca_e_a_origem(origem):
    """Princípio XV, decidido aqui e não confiado ao chamador: um destino que
    resolve para a entrada é o caso em que "a saída é a entrada" parece natural
    de implementar e destrói o original de alguém."""
    with pytest.raises(ImageCompressionError) as erro:
        compress(origem, origem, ImageSettings())
    assert erro.value.reason == 'output_is_source'


def test_a_origem_continua_identica(origem, tmp_path):
    import hashlib

    antes = hashlib.sha256(open(origem, 'rb').read()).hexdigest()
    compress(origem, str(tmp_path / 'saida.webp'), ImageSettings(output_format='webp'))
    assert hashlib.sha256(open(origem, 'rb').read()).hexdigest() == antes


# ------------------------------- metadados ------------------------------- #

def test_preserve_all_mantem_tudo(origem, tmp_path):
    saida = str(tmp_path / 'tudo.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='preserve_all'))
    exif = _exif_do_arquivo(saida)
    assert exif.get(_ORIENTATION) == 6
    assert _DESCRIPTION in exif
    assert _tem_icc(saida)


def test_strip_all_nao_deixa_nada(origem, tmp_path):
    saida = str(tmp_path / 'nada.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='strip_all'))
    assert not _exif_do_arquivo(saida)
    assert not _tem_icc(saida)


def test_essential_only_e_o_padrao_e_protege_sem_degradar(origem, tmp_path):
    """As duas metades do FR-028 ao mesmo tempo. Remover orientação gira a foto;
    remover o perfil de cor muda as cores. GPS e comentário não mudam pixel
    nenhum e são o que ninguém quer publicar junto."""
    assert ImageSettings().metadata_policy == DEFAULT_METADATA_POLICY

    saida = str(tmp_path / 'essencial.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg'))
    exif = _exif_do_arquivo(saida)

    assert exif.get(_ORIENTATION) == 6, 'orientação removida gira a imagem'
    assert _tem_icc(saida), 'perfil removido muda as cores'
    assert _GPS_IFD not in exif
    assert _DESCRIPTION not in exif


def test_strip_gps_tira_so_a_localizacao(origem, tmp_path):
    saida = str(tmp_path / 'sem_gps.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='strip_gps'))
    exif = _exif_do_arquivo(saida)
    assert _GPS_IFD not in exif
    assert exif.get(_ORIENTATION) == 6
    assert _DESCRIPTION in exif


def test_strip_comments_tira_so_o_texto(origem, tmp_path):
    saida = str(tmp_path / 'sem_texto.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='strip_comments'))
    exif = _exif_do_arquivo(saida)
    assert _DESCRIPTION not in exif
    assert exif.get(_ORIENTATION) == 6


def test_strip_icc_tira_so_o_perfil(origem, tmp_path):
    saida = str(tmp_path / 'sem_icc.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='strip_icc'))
    assert not _tem_icc(saida)
    assert _exif_do_arquivo(saida).get(_ORIENTATION) == 6


def test_strip_exif_tira_exif_e_mantem_o_perfil(origem, tmp_path):
    saida = str(tmp_path / 'sem_exif.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg',
                                          metadata_policy='strip_exif'))
    assert not _exif_do_arquivo(saida)
    assert _tem_icc(saida)


def test_politica_desconhecida_e_recusada(origem, tmp_path):
    with pytest.raises(ImageCompressionError) as erro:
        compress(origem, str(tmp_path / 'x.jpg'),
                 ImageSettings(metadata_policy='inventada'))
    assert erro.value.reason == 'invalid_settings'


# ------------------------------- redimensionamento ------------------------------- #

def test_largura_e_altura_exatas(origem, tmp_path):
    saida = str(tmp_path / 'exato.png')
    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', width=200, height=150,
                                      preserve_aspect=False))
    assert aplicado['output_size'] == (200, 150)


def test_so_a_largura_deriva_a_altura(origem, tmp_path):
    """400x300 → largura 200 deve dar 150, não 300."""
    saida = str(tmp_path / 'derivado.png')
    aplicado = compress(origem, saida, ImageSettings(output_format='png', width=200))
    assert aplicado['output_size'] == (200, 150)


def test_percentual(origem, tmp_path):
    saida = str(tmp_path / 'metade.png')
    aplicado = compress(origem, saida, ImageSettings(output_format='png', percent=50))
    assert aplicado['output_size'] == (200, 150)


def test_preservar_proporcao_cabe_na_caixa_sem_distorcer(origem, tmp_path):
    """Esticar para preencher exatamente mudaria o que a imagem mostra, não o
    seu tamanho."""
    saida = str(tmp_path / 'caixa.png')
    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', width=200, height=200,
                                      preserve_aspect=True))
    largura, altura = aplicado['output_size']
    assert (largura, altura) == (200, 150)


def test_impedir_upscale_de_fato_impede(origem, tmp_path):
    """Ligado por padrão: aumentar não reduz arquivo nenhum, e pedir 4000 px numa
    tela de compressão é quase sempre engano de digitação."""
    saida = str(tmp_path / 'grande.png')
    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', width=4000, height=3000))
    assert aplicado['output_size'] == (400, 300)


def test_desligar_a_protecao_permite_aumentar(origem, tmp_path):
    saida = str(tmp_path / 'aumentada.png')
    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', width=800, height=600,
                                      prevent_upscale=False, preserve_aspect=False))
    assert aplicado['output_size'] == (800, 600)


# ------------------------------- opções por formato ------------------------------- #

def test_progressivo_e_subamostragem_no_jpeg(origem, tmp_path):
    saida = str(tmp_path / 'prog.jpg')
    compress(origem, saida, ImageSettings(output_format='jpeg', quality=85,
                                          progressive=True, chroma_subsampling='4:2:0'))
    with Image.open(saida) as img:
        assert img.info.get('progressive')


def test_subamostragem_invalida_e_recusada(origem, tmp_path):
    with pytest.raises(ImageCompressionError) as erro:
        compress(origem, str(tmp_path / 'x.jpg'),
                 ImageSettings(output_format='jpeg', chroma_subsampling='9:9:9'))
    assert erro.value.reason == 'invalid_settings'


def test_webp_sem_perda_e_maior_em_conteudo_real(ruidosa, tmp_path):
    """Em conteúdo detalhado, sem perda é maior — é o que se paga por não jogar
    nada fora. Numa cor chapada seria o contrário, e é por isso que este teste
    usa ruído."""
    com = str(tmp_path / 'com.webp')
    sem = str(tmp_path / 'sem.webp')
    compress(ruidosa, com, ImageSettings(output_format='webp', quality=60))
    compress(ruidosa, sem, ImageSettings(output_format='webp', lossless=True))
    assert os.path.getsize(sem) > os.path.getsize(com)


def test_png_ignora_qualidade_e_usa_nivel_de_compressao(ruidosa, tmp_path):
    """No PNG a fidelidade é dada; o que varia é esforço. O nível explícito tem
    que vencer a derivação a partir da qualidade.

    Com ruído: numa cor chapada os dois níveis chegam ao mesmo tamanho mínimo e
    o teste não mediria nada."""
    baixo = str(tmp_path / 'nivel0.png')
    alto = str(tmp_path / 'nivel9.png')
    compress(ruidosa, baixo, ImageSettings(output_format='png', png_compress_level=0))
    compress(ruidosa, alto, ImageSettings(output_format='png', png_compress_level=9))
    assert os.path.getsize(alto) < os.path.getsize(baixo)


# --------------------- presets de resolução (FR-027) --------------------- #

def test_o_preset_limita_o_lado_maior(tmp_path):
    """"1080p" é um teto, não uma caixa fixa.

    Aplicar 1920×1080 literalmente a um retrato o deitaria — o que a pessoa pede
    ao escolher um degrau é "não passe disso", nos dois sentidos.
    """
    origem = str(tmp_path / 'retrato.png')
    Image.new('RGB', (1080, 1920), (40, 40, 40)).save(origem)
    saida = str(tmp_path / 'saida.png')

    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', resolution='720p'))
    largura, altura = aplicado['output_size']
    assert max(largura, altura) <= 1280
    assert min(largura, altura) <= 720
    assert altura > largura, 'o retrato foi deitado'


def test_um_arquivo_que_ja_cabe_no_preset_nao_e_tocado(tmp_path):
    """Reduzir o que já cabe custaria detalhe sem economizar nada — e a pessoa
    escolheu um teto, não uma medida."""
    origem = str(tmp_path / 'pequena.png')
    Image.new('RGB', (800, 600), (10, 120, 200)).save(origem)
    saida = str(tmp_path / 'saida.png')

    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', resolution='1080p'))
    assert aplicado['output_size'] == (800, 600)


def test_resolucao_original_nao_redimensiona(tmp_path):
    origem = str(tmp_path / 'grande.png')
    Image.new('RGB', (2400, 1200), (200, 30, 30)).save(origem)
    saida = str(tmp_path / 'saida.png')

    aplicado = compress(origem, saida,
                        ImageSettings(output_format='png', resolution='original'))
    assert aplicado['output_size'] == (2400, 1200)

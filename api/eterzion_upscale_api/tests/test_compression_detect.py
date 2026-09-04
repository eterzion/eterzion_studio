"""T025b/T025d — o tipo vem do conteúdo, e o que não foi sondado fica ausente.

Dois defeitos que estes testes impedem, e que não se parecem:

- **confiar na extensão** faz a Central oferecer controles de vídeo para um
  arquivo de áudio e falhar depois de a pessoa escolher;
- **zerar o que não foi sondado** faz a estimativa dividir por um número que
  ninguém mediu e responder com confiança total.
"""
from __future__ import annotations

import subprocess

import pytest
from PIL import Image

from app import media_handles
from app.compression import detect
from eterzion_upscale.media import ffmpeg_path, has_ffmpeg

needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason='ffmpeg não encontrado')


def _ffmpeg(*args: str) -> None:
    subprocess.run([ffmpeg_path() or 'ffmpeg', '-y', '-hide_banner', '-v', 'error', *args],
                   check=True)


# ------------------------------- a extensão não decide ------------------------------- #

def test_um_png_que_e_jpeg_e_detectado_como_imagem(tmp_path):
    mentiroso = tmp_path / 'mentiroso.png'
    Image.new('RGB', (32, 32), (10, 200, 40)).save(mentiroso, format='JPEG')
    assert detect.detect_media_kind(str(mentiroso)) == 'image'


def test_uma_extensao_desconhecida_com_imagem_dentro_e_imagem(tmp_path):
    """A pessoa arrastou um arquivo sem extensão ou com uma inventada. O
    conteúdo continua sendo o que é."""
    sem_pista = tmp_path / 'arquivo.xyz'
    Image.new('RGB', (32, 32), (90, 90, 200)).save(sem_pista, format='PNG')
    assert detect.detect_media_kind(str(sem_pista)) == 'image'


def test_um_arquivo_que_nao_e_midia_e_recusado(tmp_path):
    lixo = tmp_path / 'texto.png'
    lixo.write_bytes(b'isto nao e imagem nenhuma')
    assert detect.detect_media_kind(str(lixo)) == 'unknown'

    with pytest.raises(media_handles.HandleError) as erro:
        media_handles.register_media(str(lixo))
    assert erro.value.reason == 'unsupported_media'


@needs_ffmpeg
def test_um_arquivo_so_de_audio_e_audio(tmp_path):
    audio = tmp_path / 'som.m4a'
    _ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:a', 'aac', str(audio))
    assert detect.detect_media_kind(str(audio)) == 'audio'


@needs_ffmpeg
def test_um_video_com_audio_e_video_e_nao_audio(tmp_path):
    """A ordem das perguntas importa: ter trilha de áudio não faz de um vídeo um
    arquivo de áudio."""
    video = tmp_path / 'clipe.mp4'
    _ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x48:d=1:r=10',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            '-c:v', 'mpeg4', '-c:a', 'aac', '-shortest', str(video))
    assert detect.detect_media_kind(str(video)) == 'video'


# ------------------------------- imagem × animação ------------------------------- #

def test_um_gif_de_varios_quadros_e_animacao(tmp_path):
    gif = tmp_path / 'anima.gif'
    quadros = [Image.new('RGB', (32, 32), (i * 20, 50, 200)) for i in range(1, 5)]
    quadros[0].save(gif, save_all=True, append_images=quadros[1:], duration=100, loop=0)
    assert detect.detect_media_kind(str(gif)) == 'animation'


def test_um_gif_de_um_quadro_e_imagem(tmp_path):
    """Caso de borda registrado na spec. Tratá-lo como animação ofereceria
    controles de FPS e otimização de quadros para algo que não se move."""
    gif = tmp_path / 'parado.gif'
    Image.new('RGB', (32, 32), (200, 30, 30)).save(gif)
    assert detect.detect_media_kind(str(gif)) == 'image'


def test_um_webp_animado_e_animacao(tmp_path):
    webp = tmp_path / 'anima.webp'
    quadros = [Image.new('RGB', (32, 32), (i * 30, 80, 120)) for i in range(1, 4)]
    quadros[0].save(webp, save_all=True, append_images=quadros[1:], duration=100)
    assert detect.detect_media_kind(str(webp)) == 'animation'


# ------------------------------- ausente ≠ zero ------------------------------- #

def test_metadado_nao_sondado_fica_ausente_e_nao_zerado(tmp_path):
    """FR-010. `None` é uma afirmação sobre a sondagem; `0` é uma afirmação
    sobre a mídia. Um bitrate zerado faria a estimativa responder com confiança
    total sobre um número que ninguém mediu."""
    imagem = tmp_path / 'foto.png'
    Image.new('RGB', (100, 80), (10, 10, 10)).save(imagem)
    dados = detect.probe_metadata(str(imagem), 'image')

    # Uma imagem não tem duração, taxa de quadros nem canais.
    for campo in ('duration_seconds', 'frame_rate', 'channels', 'sample_rate'):
        assert campo not in dados, f'{campo} não deveria existir para imagem'
    assert dados['width'] == 100 and dados['height'] == 80


def test_nenhum_valor_nulo_sobrevive(tmp_path):
    imagem = tmp_path / 'foto.png'
    Image.new('RGB', (10, 10)).save(imagem)
    dados = detect.probe_metadata(str(imagem), 'image')
    assert all(v is not None for v in dados.values())


def test_imagem_com_e_sem_metadados_e_distinguida(tmp_path):
    """`has_metadata` decide se o controle de metadados tem o que fazer neste
    arquivo — oferecê-lo para uma imagem sem EXIF seria um controle inerte."""
    com = tmp_path / 'com.jpg'
    ex = Image.Exif()
    ex[271] = 'Astros'
    Image.new('RGB', (32, 32)).save(com, format='JPEG', exif=ex)
    assert detect.probe_metadata(str(com), 'image')['has_metadata'] is True

    sem = tmp_path / 'sem.png'
    Image.new('RGB', (32, 32)).save(sem)
    assert detect.probe_metadata(str(sem), 'image').get('has_metadata') is False


# ------------------------------- registro ------------------------------- #

def test_o_registro_guarda_o_tipo_detectado(tmp_path):
    imagem = tmp_path / 'foto.png'
    Image.new('RGB', (40, 30)).save(imagem)
    handle = media_handles.register_media(str(imagem))
    assert media_handles.describe(handle)['media_kind'] == 'image'


def test_o_registro_do_editor_valida_sem_os_campos_novos(tmp_path):
    """Uma feature nova não muda o contrato de uma antiga (FR-069).

    `MediaHandleResponse` é `extra='forbid'`, e acrescentar um campo
    **obrigatório** faria a rota do editor de vídeo reprovar na validação da
    resposta — foi o que aconteceu ao escrever isto pela primeira vez.

    A verificação mudou de forma quando a rota de registro passou a servir os
    quatro tipos de mídia: proibir o campo deixou de ser possível, porque a
    Central precisa dele. O que continua valendo, e é o que sempre importou, é
    que **todo campo acrescentado depois é opcional** — o registro do editor não
    os escreve, e a resposta dele tem que continuar validando exatamente como
    antes.
    """
    from app.schemas import MediaHandleResponse

    do_editor = {'handle_id', 'display_name', 'content_key', 'duration_seconds',
                 'width', 'height', 'frame_rate', 'frame_rate_is_variable',
                 'has_audio', 'size_bytes'}
    obrigatorios = {nome for nome, campo in MediaHandleResponse.model_fields.items()
                    if campo.is_required()}
    assert obrigatorios <= do_editor, (
        f'campo obrigatório novo quebraria a rota do editor: {obrigatorios - do_editor}')


def test_a_resposta_do_editor_valida_com_um_video_de_verdade():
    """O mesmo, medido em vez de deduzido do schema."""
    import pathlib as _pathlib

    from app.schemas import MediaHandleResponse

    fixture = _pathlib.Path(__file__).parent / 'fixtures' / 'curto.mp4'
    if not fixture.is_file():
        pytest.skip('fixture de vídeo ausente')

    handle = media_handles.register(str(fixture))
    info = media_handles.describe(handle)
    conhecidos = MediaHandleResponse.model_fields
    resposta = MediaHandleResponse(
        handle_id=handle, **{k: v for k, v in info.items() if k in conhecidos})
    assert resposta.duration_seconds is not None
    assert resposta.media_kind is None, 'o registro do editor não escreve media_kind'


def test_o_caminho_nunca_sai_no_describe(tmp_path):
    """Princípio XIII: o identificador é a referência, e o caminho fica dentro
    do módulo. `describe` exclui uma vez, em vez de cada chamador lembrar."""
    imagem = tmp_path / 'foto.png'
    Image.new('RGB', (40, 30)).save(imagem)
    dados = media_handles.describe(media_handles.register_media(str(imagem)))
    assert 'path' not in dados
    assert str(tmp_path) not in str(dados)


def test_o_registro_do_editor_de_video_continua_recusando_imagem(tmp_path):
    """`register` é do editor e espera largura, taxa de quadros e o resto.
    Afrouxá-lo para caber a Central quebraria quem já depende dele."""
    imagem = tmp_path / 'foto.png'
    Image.new('RGB', (40, 30)).save(imagem)
    with pytest.raises(media_handles.HandleError):
        media_handles.register(str(imagem))

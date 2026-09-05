"""Os cenários do quickstart que a API pode provar sozinha.

O `quickstart.md` descreve 24 cenários. Vários deles são sobre o que aparece na
tela e exigem a janela do Electron; os que estão aqui são os que se decidem no
corpo das respostas e nos arquivos produzidos — e esses ganham mais sendo testes
permanentes do que sendo um roteiro seguido uma vez.

**O cenário 5 é o mais importante do arquivo.** A spec o chama de "o que dá dente
à condição 4" da exceção constitucional: sem ele, "Automático funciona" é uma
promessa. Ele compara os bytes de duas compressões — uma pelo Básico, outra pelo
Avançado com tudo em Automático — e exige que sejam idênticas. Se um dia
divergirem, a exceção do Princípio V perde a condição que a sustenta, e isso tem
que quebrar a suíte em vez de aparecer como "o Avançado ficou um pouco melhor".
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pathlib
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import jobs, media_handles
from app.main import app

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'

# Nomes que nunca podem aparecer numa resposta da API (Princípio V).
NOMES_PROIBIDOS = (
    'libx264', 'libx265', 'nvenc', 'qsv', 'amf', 'libvpx', 'libsvtav1',
    'libaom', 'libmp3lame', 'libopus', 'libvorbis', 'libwebp', 'pcm_s16le',
    'h264_nvenc', 'hevc_nvenc', 'palettegen', 'paletteuse',
)


@pytest.fixture
def client():
    media_handles.clear()
    jobs.jobs.clear()
    with TestClient(app) as c:
        yield c
    media_handles.clear()
    jobs.jobs.clear()


@pytest.fixture
def foto(tmp_path):
    rng = random.Random(21)
    img = Image.new('RGB', (400, 300))
    img.putdata([
        ((x * 3) % 256, (y * 3) % 256, (x + y + rng.randrange(-15, 16)) % 256)
        for y in range(300) for x in range(400)
    ])
    caminho = tmp_path / 'foto.png'
    img.save(caminho)
    return str(caminho)


def _processar(job_id: str) -> None:
    job = jobs.get_job(job_id)
    if job and job['status'] in ('done', 'error', 'cancelled'):
        return
    if job and job['status'] == 'pending':
        job['status'] = 'queued'
    asyncio.run(jobs._process_job(job_id))


def _comprimir(client, caminho, destino, **corpo) -> dict:
    handle = media_handles.register_media(caminho)
    pedido = {'handle_id': handle, 'media_kind': 'image',
              'settings': {'output_format': 'jpeg', 'quality': 70},
              'export': {'directory': str(destino)}}
    pedido.update(corpo)
    resposta = client.post('/compression/jobs', json=pedido)
    if resposta.status_code != 202:
        return {'refused': resposta}
    job_id = resposta.json()['job_id']
    _processar(job_id)
    return {'job': jobs.get_job(job_id)}


def _sha(caminho: str) -> str:
    return hashlib.sha256(open(caminho, 'rb').read()).hexdigest()


# ------------------------- 5 — Básico e Avançado produzem o mesmo ------------------------- #

def test_cenario_5_basico_e_avancado_com_automatico_produzem_bytes_identicos(
        client, foto, tmp_path):
    """Condição 4 da exceção constitucional, medida por hash.

    O Avançado existe para quem quer controlar; quem não abre o Avançado tem que
    obter exatamente o mesmo arquivo. Se divergirem, "Automático funciona" deixa
    de ser verdade e a exceção perde o que a sustenta.
    """
    basico_dir = tmp_path / 'basico'
    avancado_dir = tmp_path / 'avancado'
    basico_dir.mkdir()
    avancado_dir.mkdir()

    configuracoes = {'output_format': 'jpeg', 'quality': 70}

    b = _comprimir(client, foto, basico_dir, settings=configuracoes, advanced=False)
    assert 'job' in b, getattr(b.get('refused'), 'text', '')
    assert b['job']['status'] == 'done', b['job'].get('error')

    # Avançado com **todos os controles em Automático** é a mesma coisa que o
    # Básico: nenhum campo técnico enviado.
    a = _comprimir(client, foto, avancado_dir, settings=configuracoes, advanced=True)
    assert 'job' in a
    assert a['job']['status'] == 'done', a['job'].get('error')

    assert _sha(b['job']['output_path']) == _sha(a['job']['output_path']), (
        'Básico e Avançado-em-Automático produziram arquivos diferentes — '
        'a condição 4 da exceção do Princípio V deixou de valer')


# ------------------------- 6 — o Básico não conhece codec ------------------------- #

@pytest.mark.parametrize('media_kind', ['image', 'video', 'audio', 'animation'])
def test_cenario_6_nenhuma_resposta_do_basico_nomeia_encoder(client, foto, media_kind):
    """O mesmo que `test_no_codec_leak.py` faz para o editor, aqui para a Central."""
    handle = media_handles.register_media(foto)
    respostas = [
        client.get('/compression/capabilities'),
        client.get('/compression/presets'),
        client.get(f'/compression/media/{handle}'),
        client.post('/compression/estimate', json={
            'handle_id': handle, 'media_kind': media_kind, 'settings': {}}),
    ]
    for resposta in respostas:
        texto = json.dumps(resposta.json(), ensure_ascii=False).lower()
        vazou = [n for n in NOMES_PROIBIDOS if n in texto]
        assert not vazou, f'{resposta.request.url} vazou {vazou}'


# ------------------------- 7 — contorno da interface ------------------------- #

def test_cenario_7_basico_mandando_codec_e_recusado(client, foto):
    """Tolerar seria a porta pela qual a condição 2 deixa de valer: um cliente
    que manda codec no Básico passaria a funcionar, e isso viraria
    comportamento."""
    handle = media_handles.register_media(foto)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'video', 'advanced': False,
        'settings': {'video_codec': 'h264'}})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'invalid_settings'
    assert 'video_codec' in r.json()['detail']['fields']


# ------------------------- 8 — indisponível é indisponível ------------------------- #

def test_cenario_8_codec_indisponivel_e_recusado_sem_nomear_encoder(client, foto):
    from app.compression import capabilities

    indisponiveis = [e['value'] for e in capabilities.video_codecs() if not e['available']]
    if not indisponiveis:
        pytest.skip('esta máquina produz todos os codecs — não há recusa a inspecionar')

    handle = media_handles.register_media(foto)
    for codec in indisponiveis:
        r = client.post('/compression/jobs', json={
            'handle_id': handle, 'media_kind': 'video', 'advanced': True,
            'settings': {'video_codec': codec, 'container': 'mkv'}})
        assert r.status_code == 422
        detalhe = r.json()['detail']
        assert detalhe['reason'] in ('encoder_unavailable', 'incompatible_combination')
        texto = json.dumps(detalhe, ensure_ascii=False).lower()
        assert not any(n in texto for n in NOMES_PROIBIDOS), texto


def test_cenario_8_a_razao_distingue_hardware_de_ausencia(client):
    """"Precisa de hardware que esta máquina não tem" e "não disponível" são
    coisas diferentes, e a pessoa pode agir sobre uma e não sobre a outra."""
    capacidades = client.get('/compression/capabilities').json()
    for entrada in capacidades['video']['video_codecs']:
        if entrada['available']:
            continue
        if entrada['requires_hardware']:
            assert entrada['unavailable_reason'] == 'requires_hardware_encoder'
        else:
            assert entrada['unavailable_reason'] == 'no_encoder_available'


# ------------------------- 9 — combinação incompatível ------------------------- #

def test_cenario_9_webm_so_oferece_os_codecs_que_aceita(client):
    capacidades = client.get('/compression/capabilities').json()
    webm = capacidades['video']['compatibility'].get('webm')
    assert webm is not None
    assert 'h264' not in webm['video']
    assert 'h265' not in webm['video']
    assert set(webm['video']) <= {'vp9', 'av1'}


def test_cenario_9_forcar_a_combinacao_pela_api_e_recusado(client, foto):
    """"Não aparece como opção" e "não é aceito" precisam ser a mesma coisa —
    senão a interface é só uma sugestão."""
    handle = media_handles.register_media(foto)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'video', 'advanced': True,
        'settings': {'container': 'webm', 'video_codec': 'h264'}})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] in ('incompatible_combination', 'encoder_unavailable')


# ------------------------- 10 — origem intacta ------------------------- #

def test_cenario_10_a_origem_nao_muda_um_byte(client, foto, tmp_path):
    destino = tmp_path / 'saida'
    destino.mkdir()
    antes = _sha(foto)
    resultado = _comprimir(client, foto, destino)
    assert resultado['job']['status'] == 'done'
    assert _sha(foto) == antes


# ------------------------- 11 — nada órfão ------------------------- #

def test_cenario_11_nenhum_temporario_sobra(client, foto, tmp_path, tempdir_isolado):
    import tempfile

    def temporarios() -> set[str]:
        raiz = tempfile.gettempdir()
        return {n for n in os.listdir(raiz) if n.startswith('astros-compression-')}

    destino = tmp_path / 'saida'
    destino.mkdir()
    antes = temporarios()
    _comprimir(client, foto, destino)
    assert temporarios() == antes


# ------------------------- 13 — metadados sob controle ------------------------- #

def test_cenario_13_a_politica_de_metadados_e_aplicada(client, tmp_path):
    """Verificado **lendo os metadados do arquivo produzido**, não pela
    aparência."""
    from PIL import Image as PILImage

    origem = tmp_path / 'com_exif.jpg'
    img = PILImage.new('RGB', (80, 60), (120, 40, 200))
    exif = img.getexif()
    exif[274] = 3          # orientação
    exif[271] = 'Camera X'  # fabricante
    img.save(origem, exif=exif)

    destino = tmp_path / 'saida'
    destino.mkdir()
    resultado = _comprimir(client, str(origem), destino,
                           settings={'output_format': 'jpeg', 'metadata_policy': 'strip_all'})
    assert resultado['job']['status'] == 'done'

    with PILImage.open(resultado['job']['output_path']) as saida:
        assert not dict(saida.getexif()), 'strip_all deixou metadados no arquivo'


# ------------------------- 18 — compressão que aumenta ------------------------- #

def test_cenario_18_quando_o_arquivo_cresce_o_resultado_diz(client, tmp_path):
    """FR-023. Uma redução negativa apresentada como economia é o tipo de defeito
    que passa por formatação — por isso `grew` é campo, e não conta do cliente.
    """
    # Ruído puro em PNG já está perto do incompressível; convertê-lo para PNG com
    # nível baixo costuma crescer.
    rng = random.Random(9)
    origem = tmp_path / 'ruido.png'
    img = Image.new('RGB', (200, 200))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(200 * 200)])
    img.save(origem, optimize=True)

    destino = tmp_path / 'saida'
    destino.mkdir()
    resultado = _comprimir(client, str(origem), destino,
                           settings={'output_format': 'png', 'png_compress_level': 0},
                           advanced=True)
    assert resultado['job']['status'] == 'done'

    medido = resultado['job']['compression']
    cresceu = medido['output_size_bytes'] > medido['original_bytes']
    # O que se verifica não é que cresceu — isso depende do conteúdo — e sim que
    # `grew` **concorda com os bytes**, nos dois sentidos.
    assert medido['grew'] is cresceu
    assert medido['saving_bytes'] == medido['original_bytes'] - medido['output_size_bytes']


# ------------------------- 20 — preset sobrevive ao reinício ------------------------- #

def test_cenario_20_o_preset_do_usuario_sobrevive_ao_reinicio(client, tmp_path, monkeypatch):
    from app.compression import presets

    loja = tmp_path / 'presets.json'
    monkeypatch.setattr(presets, '_store_path', lambda: str(loja))

    criado = client.post('/compression/presets', json={
        'name': 'Meu jeito', 'media_kind': 'image',
        'settings': {'output_format': 'webp', 'quality': 55}}).json()

    # "Reiniciar" é ler do disco de novo, sem estado em memória.
    presets._load.cache_clear() if hasattr(presets._load, 'cache_clear') else None
    relidos = presets.user_presets()
    assert any(p['id'] == criado['id'] and p['settings']['quality'] == 55 for p in relidos)


# ------------------------- 21 — repetir do histórico ------------------------- #

def test_cenario_21_repetir_usa_o_snapshot(client, foto, tmp_path, monkeypatch):
    from app.compression import history, presets

    monkeypatch.setattr(history, '_store_path', lambda: str(tmp_path / 'hist.json'))
    monkeypatch.setattr(presets, '_store_path', lambda: str(tmp_path / 'presets.json'))

    preset = presets.create('Web leve', 'image', {'output_format': 'jpeg', 'quality': 60})
    destino = tmp_path / 'saida'
    destino.mkdir()
    resultado = _comprimir(client, foto, destino,
                           settings=dict(preset['settings']), preset_id=preset['id'])
    assert resultado['job']['status'] == 'done'

    # A pessoa muda o preset depois.
    presets.update(preset['id'], settings={'output_format': 'png', 'quality': 100})

    entradas = client.get('/compression/history').json()['entries']
    assert entradas, 'a compressão não entrou no histórico'
    snapshot = entradas[0]['settings_snapshot']
    assert snapshot['quality'] == 60, 'repetir usaria o preset atual, não o que foi usado'


# ------------------------- 24 — erro compreensível ------------------------- #

def test_cenario_24_o_erro_traz_razao_e_a_saida_bruta_separadas(client, foto, tmp_path):
    """FR-065: a razão é o que a pessoa lê; a saída da ferramenta fica à parte."""
    handle = media_handles.register_media(foto)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'inventado'}})
    assert r.status_code == 422
    detalhe = r.json()['detail']
    assert detalhe['reason'] == 'invalid_settings'
    # A recusa antes de processar não tem saída de ferramenta — e não inventa
    # uma. O campo só existe quando houve.
    assert 'error_detail' not in detalhe

"""T023/T025 — o job de compressão: recusas antes de processar, e nada órfão.

Duas propriedades, e as duas são sobre o que **não** acontece:

- toda recusa possível acontece antes de qualquer processamento (FR-064) — uma
  recusa depois da barra de progresso já custou o tempo da pessoa;
- nenhum temporário sobrevive a sucesso, erro ou cancelamento (FR-053, SC-005).
"""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import jobs, media_handles
from app.compression import runner, workspace
from app.main import app


@pytest.fixture
def client():
    media_handles.clear()
    jobs.jobs.clear()
    with TestClient(app) as test_client:
        yield test_client
    media_handles.clear()
    jobs.jobs.clear()


@pytest.fixture
def imagem(tmp_path):
    import random

    rng = random.Random(3)
    img = Image.new('RGB', (320, 240))
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                 for _ in range(320 * 240)])
    caminho = tmp_path / 'foto.png'
    img.save(caminho)
    return str(caminho)


def _pedido(handle: str, **extra) -> dict:
    corpo = {'handle_id': handle, 'media_kind': 'image',
             'settings': {'output_format': 'jpeg', 'quality': 70}}
    corpo.update(extra)
    return corpo


# ------------------------------- caminho feliz ------------------------------- #

def test_comprime_uma_imagem_de_ponta_a_ponta(client, imagem, tmp_path):
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()

    r = client.post('/compression/jobs', json=_pedido(
        handle, export={'directory': str(destino), 'naming_pattern': '{filename}_compressed',
                        'conflict_policy': 'rename', 'apply_to_all': False}))
    assert r.status_code == 202
    job_id = r.json()['job_id']

    _aguardar(job_id)
    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')

    assert os.path.isfile(job['output_path'])
    assert os.path.getsize(job['output_path']) > 0
    assert job['output_meta']['size_bytes'] == os.path.getsize(job['output_path'])


def test_os_numeros_do_resultado_sao_medidos_e_nao_a_estimativa(client, imagem, tmp_path):
    """FR-022 pede o real. Repetir a previsão como resultado seria a mentira
    mais fácil de cometer aqui."""
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = client.post('/compression/jobs', json=_pedido(
        handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)

    job = jobs.get_job(job_id)
    medido = job['compression']
    tamanho_real = os.path.getsize(job['output_path'])
    assert medido['output_size_bytes'] == tamanho_real
    assert medido['saving_bytes'] == medido['original_bytes'] - tamanho_real
    assert medido['elapsed_seconds'] >= 0
    assert medido['grew'] is (tamanho_real > medido['original_bytes'])


def test_a_origem_continua_identica(client, imagem, tmp_path):
    import hashlib

    antes = hashlib.sha256(open(imagem, 'rb').read()).hexdigest()
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = client.post('/compression/jobs',
                         json=_pedido(handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)
    assert hashlib.sha256(open(imagem, 'rb').read()).hexdigest() == antes


def test_a_saida_nunca_e_a_origem(client, imagem):
    """Mesmo sem diretório de destino — o padrão é a pasta da origem, e é ali
    que a colisão acontece por construção (Princípio XV)."""
    handle = media_handles.register_media(imagem)
    job_id = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'png'},
        'export': {'naming_pattern': '{filename}'},
    }).json()['job_id']
    _aguardar(job_id)
    job = jobs.get_job(job_id)
    assert os.path.abspath(job['output_path']) != os.path.abspath(imagem)
    assert os.path.isfile(imagem)


def test_os_numeros_medidos_chegam_na_consulta_do_job(client, imagem, tmp_path):
    """A interface lê `GET /jobs/{id}`, não o dicionário interno.

    Sem este teste, os números poderiam existir no job e ser filtrados na visão
    pública — a tela mostraria um resultado vazio para uma compressão que deu
    certo, e nada no backend estaria errado.
    """
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = client.post('/compression/jobs', json=_pedido(
        handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)

    corpo = client.get(f'/jobs/{job_id}').json()
    assert corpo['status'] == 'done', corpo.get('error')
    medido = corpo['compression']
    assert medido['output_size_bytes'] == os.path.getsize(corpo['output_path'])
    assert set(medido) >= {'original_bytes', 'output_size_bytes', 'saving_bytes',
                           'reduction_ratio', 'grew', 'elapsed_seconds'}


def test_a_compressao_entra_no_historico_com_o_snapshot(client, imagem, tmp_path, monkeypatch):
    """FR-062, medido no caminho real — o job grava, não um teste unitário.

    Sem isto, o módulo de histórico poderia estar correto e nunca ser chamado: a
    tela ficaria vazia e nenhum teste falharia.
    """
    from app.compression import history

    monkeypatch.setattr(history, '_store_path',
                        lambda: str(tmp_path / 'compression-history.json'))
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = client.post('/compression/jobs', json=_pedido(
        handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)

    entradas = history.all_entries()
    assert len(entradas) == 1
    entrada = entradas[0]
    assert entrada['id'] == job_id
    assert entrada['settings_snapshot']['output_format'] == 'jpeg'
    assert entrada['result']['output_size_bytes'] == os.path.getsize(
        jobs.get_job(job_id)['output_path'])


def test_um_historico_que_nao_grava_nao_derruba_o_job(client, imagem, tmp_path, monkeypatch):
    """O arquivo já existe no disco e é o que a pessoa pediu. Um histórico que
    não gravou custa memória, não trabalho."""
    from app.compression import history

    def explode(**_):
        raise OSError('disco cheio')

    monkeypatch.setattr(history, 'record', explode)
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = client.post('/compression/jobs', json=_pedido(
        handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)

    job = jobs.get_job(job_id)
    assert job['status'] == 'done', job.get('error')
    assert os.path.isfile(job['output_path'])


# ------------------------------- recusas ------------------------------- #

def test_modo_basico_com_campo_tecnico_e_recusado(client, imagem):
    """A condição 2 da exceção constitucional, verificada no backend.

    Tolerar seria a porta pela qual ela deixa de valer: um cliente que manda
    codec no modo Básico passaria a funcionar, e isso viraria comportamento.
    """
    handle = media_handles.register_media(imagem)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'png_compress_level': 9},
        'advanced': False,
    })
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'invalid_settings'


def test_o_mesmo_campo_passa_no_modo_avancado(client, imagem, tmp_path):
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'png', 'png_compress_level': 9},
        'advanced': True, 'export': {'directory': str(destino)},
    })
    assert r.status_code == 202


def test_formato_desconhecido_e_recusado(client, imagem):
    handle = media_handles.register_media(imagem)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'inventado'}})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'invalid_settings'


def test_alvo_impossivel_e_recusado_sem_criar_job(client, imagem):
    """FR-020: dizer antes. Nenhum job criado, nenhum arquivo escrito."""
    handle = media_handles.register_media(imagem)
    antes = len(jobs.jobs)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg'},
        'target': {'value': 1, 'unit': 'KB'}})
    assert r.status_code == 422
    assert r.json()['detail']['reason'] == 'target_below_floor'
    assert len(jobs.jobs) == antes


def test_alvo_atingivel_entra_de_fato_nas_configuracoes(client, imagem, tmp_path):
    """Sem isto o alvo seria decoração: o arquivo sairia com a qualidade padrão
    e o tamanho pedido seria ignorado em silêncio."""
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    original = os.path.getsize(imagem)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg'},
        'target': {'value': original / 8 / 1000, 'unit': 'KB'},
        'export': {'directory': str(destino)}})
    assert r.status_code == 202
    job_id = r.json()['job_id']
    _aguardar(job_id)
    assert os.path.getsize(jobs.get_job(job_id)['output_path']) < original


def test_video_ainda_nao_esta_disponivel_e_diz_isso(client, imagem):
    """Melhor que uma implementação parcial que produza arquivo errado em
    silêncio."""
    handle = media_handles.register_media(imagem)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'video', 'settings': {}})
    # A validação de vídeo passa (settings vazio é válido); quem recusa é o
    # executor, e o job termina em erro em vez de produzir lixo.
    if r.status_code == 202:
        _aguardar(r.json()['job_id'])
        assert jobs.get_job(r.json()['job_id'])['status'] == 'error'


def test_handle_desconhecido_e_404(client):
    r = client.post('/compression/jobs', json={
        'handle_id': 'vh_naoexiste', 'media_kind': 'image', 'settings': {}})
    assert r.status_code == 404


def test_campo_desconhecido_e_recusado(client, imagem):
    handle = media_handles.register_media(imagem)
    r = client.post('/compression/jobs', json={
        'handle_id': handle, 'media_kind': 'image', 'settings': {}, 'inventado': 1})
    assert r.status_code == 422


# ------------------------------- temporários ------------------------------- #

def test_o_espaco_de_trabalho_some_no_sucesso():
    with workspace.workspace() as caminho:
        assert os.path.isdir(caminho)
        open(os.path.join(caminho, 'x'), 'w').close()
    assert not os.path.exists(caminho)


def test_o_espaco_de_trabalho_some_no_erro():
    """Um `finally` cobre isto. O teste existe porque a versão sem ele parece
    igualmente correta."""
    with pytest.raises(RuntimeError):
        with workspace.workspace() as caminho:
            guardado = caminho
            raise RuntimeError('falha proposital')
    assert not os.path.exists(guardado)


def test_a_varredura_apaga_orfaos_de_execucoes_que_nao_terminaram():
    """A rede que pega o que nem o `finally` nem o `atexit` pegam — travamento,
    queda de energia, processo morto. Sem ela, um travamento por semana enche o
    disco em silêncio."""
    orfao = tempfile.mkdtemp(prefix='astros-compression-')
    open(os.path.join(orfao, 'restou'), 'w').close()

    workspace.sweep_orphans()
    assert not os.path.exists(orfao)


def test_a_varredura_nao_toca_execucao_em_curso():
    with workspace.workspace() as vivo:
        workspace.sweep_orphans()
        assert os.path.isdir(vivo), 'a varredura apagou um trabalho em andamento'


def test_nenhum_temporario_sobra_depois_de_comprimir(client, imagem, tmp_path):
    handle = media_handles.register_media(imagem)
    destino = tmp_path / 'saida'
    destino.mkdir()
    antes = _temporarios_da_central()

    job_id = client.post('/compression/jobs',
                         json=_pedido(handle, export={'directory': str(destino)})).json()['job_id']
    _aguardar(job_id)

    assert _temporarios_da_central() == antes


def test_nenhum_temporario_sobra_depois_de_um_erro(tmp_path):
    """Uma compressão que levanta não pode deixar o diretório de trabalho."""
    antes = _temporarios_da_central()
    with pytest.raises(runner.CompressionRefused):
        runner.run('video', str(tmp_path), str(tmp_path / 'x.mp4'), {})
    assert _temporarios_da_central() == antes


# ------------------------------- auxiliares ------------------------------- #

def _temporarios_da_central() -> set[str]:
    raiz = tempfile.gettempdir()
    try:
        return {n for n in os.listdir(raiz) if n.startswith('astros-compression-')}
    except OSError:
        return set()


def _aguardar(job_id: str, limite: float = 30.0) -> None:
    """Processa o job aqui, em vez de esperar o laço da aplicação.

    O `TestClient` não gira o laço entre requisições, então esperar não termina
    nunca. É o mesmo caminho que os testes de compress/convert já usam — o job
    passa por `_process_job` de verdade, com o mesmo despacho e o mesmo
    tratamento de erro que a aplicação usa.
    """
    job = jobs.get_job(job_id)
    if job and job['status'] in ('done', 'error', 'cancelled'):
        return
    if job and job['status'] == 'pending':
        job['status'] = 'queued'
    asyncio.run(jobs._process_job(job_id))

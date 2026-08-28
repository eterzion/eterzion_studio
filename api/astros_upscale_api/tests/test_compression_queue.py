"""T080 — cancelar um não afeta os outros, e um erro não para a fila.

As duas propriedades justificam a decisão registrada em `contracts/api.md`: a
Central manda **N pedidos**, um por arquivo, em vez de uma rota em lote.

Uma rota em lote devolveria um resultado agregado, e quando um arquivo falhasse a
resposta teria que carregar qual — reconstruindo, pior, o que N jobs dão de
graça. Com um job por arquivo, cancelar um é cancelar um e o erro aponta para o
arquivo que o causou.

**Um erro não parar a fila** é a propriedade cara. O contrário é fácil de
escrever e destrói o valor do lote: quem deixou trinta arquivos processando à
noite volta e encontra vinte e nove não feitos por causa de um PNG corrompido.
"""
from __future__ import annotations

import asyncio
import os
import random

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import jobs, media_handles
from app.main import app


@pytest.fixture
def client():
    media_handles.clear()
    jobs.jobs.clear()
    with TestClient(app) as c:
        yield c
    media_handles.clear()
    jobs.jobs.clear()


@pytest.fixture
def imagens(tmp_path):
    """Três imagens comprimíveis — gradiente com ruído leve.

    Cor sólida comprime ao mínimo em qualquer configuração e ruído puro é
    incompressível; nos dois casos os testes passariam sem provar nada sobre
    compressão.
    """
    rng = random.Random(7)
    caminhos = []
    for i in range(3):
        img = Image.new('RGB', (160, 120))
        img.putdata([
            ((x * 2 + i * 20) % 256,
             (y * 2) % 256,
             (x + y + rng.randrange(-10, 11)) % 256)
            for y in range(120) for x in range(160)
        ])
        caminho = tmp_path / f'foto{i}.png'
        img.save(caminho)
        caminhos.append(str(caminho))
    return caminhos


def _pedir(client, handle, destino, **extra):
    corpo = {
        'handle_id': handle, 'media_kind': 'image',
        'settings': {'output_format': 'jpeg', 'quality': 70},
        'export': {'directory': str(destino)},
    }
    corpo.update(extra)
    return client.post('/compression/jobs', json=corpo)


def _criar_parado(caminho: str, destino) -> str:
    """Cria um job **sem** passar pela rota, e portanto sem que a fila o pegue.

    Descoberto ao escrever isto: sob o `TestClient`, o laço da aplicação roda
    entre requisições e um job de imagem já está `done` quando o POST retorna.
    Cancelar depois disso é uma corrida que nenhum teste vence de forma estável,
    e um teste que às vezes cancela um job já pronto não mede o que afirma.

    Criar direto no armazenamento deixa o job parado em `pending`, que é o estado
    em que a propriedade — cancelar um não toca os outros — de fato importa.
    """
    handle = media_handles.register_media(caminho)
    info = media_handles.describe(handle)
    return jobs.create_job(
        caminho, info['display_name'],
        {'media_kind': 'image', 'settings': {'output_format': 'jpeg', 'quality': 70},
         'output_path': str(destino / (os.path.splitext(os.path.basename(caminho))[0] + '.jpg')),
         'preset_id': None, 'advanced': False},
        operation='compression', media_type='image')


def _processar(job_id: str) -> None:
    job = jobs.get_job(job_id)
    if job and job['status'] in ('done', 'error', 'cancelled'):
        return
    if job and job['status'] == 'pending':
        job['status'] = 'queued'
    asyncio.run(jobs._process_job(job_id))


# ------------------------- cancelar um não afeta os outros ------------------------- #

def test_cancelar_um_item_nao_toca_os_outros(client, imagens, tmp_path):
    destino = tmp_path / 'saida'
    destino.mkdir()
    ids = [_criar_parado(p, destino) for p in imagens]

    assert client.delete(f'/jobs/{ids[1]}').status_code == 200

    for job_id in (ids[0], ids[2]):
        _processar(job_id)
        assert jobs.get_job(job_id)['status'] == 'done', jobs.get_job(job_id).get('error')

    assert jobs.get_job(ids[1])['status'] == 'cancelled'


def test_o_arquivo_do_item_cancelado_nao_e_escrito(client, imagens, tmp_path):
    """Cancelar tem que impedir o resultado, não só marcar o estado."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = _criar_parado(imagens[0], destino)

    client.delete(f'/jobs/{job_id}')
    _processar(job_id)

    assert jobs.get_job(job_id)['status'] == 'cancelled'
    assert not list(destino.iterdir()), 'o item cancelado escreveu arquivo'


def test_cancelar_um_job_que_ja_terminou_nao_desfaz_o_resultado(client, imagens, tmp_path):
    """Um cancelamento que chega tarde é inofensivo — e não pode apagar o que já
    foi produzido."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    job_id = _pedir(client, media_handles.register_media(imagens[0]), destino).json()['job_id']
    _processar(job_id)
    saida = jobs.get_job(job_id)['output_path']
    assert os.path.isfile(saida)

    client.delete(f'/jobs/{job_id}')
    assert os.path.isfile(saida), 'o cancelamento tardio apagou o resultado'


# ------------------------- um erro não para a fila ------------------------- #

def test_um_arquivo_ilegivel_nao_impede_os_demais(client, imagens, tmp_path):
    destino = tmp_path / 'saida'
    destino.mkdir()

    bom1 = _pedir(client, media_handles.register_media(imagens[0]), destino).json()['job_id']
    quebrado = media_handles.register_media(imagens[1])
    bom2 = _pedir(client, media_handles.register_media(imagens[2]), destino).json()['job_id']

    # O arquivo some depois de registrado — o caso real de uma pasta sincronizada
    # ou de um pendrive removido no meio do lote.
    ruim = _pedir(client, quebrado, destino).json()['job_id']
    os.remove(imagens[1])

    for job_id in (bom1, ruim, bom2):
        _processar(job_id)

    assert jobs.get_job(bom1)['status'] == 'done'
    assert jobs.get_job(bom2)['status'] == 'done'
    assert jobs.get_job(ruim)['status'] == 'error'


def test_a_recusa_de_um_pedido_nao_impede_os_outros(client, imagens, tmp_path):
    """Uma configuração impossível num arquivo é recusada na criação — e os
    outros nem ficam sabendo."""
    destino = tmp_path / 'saida'
    destino.mkdir()

    # 50 bytes: abaixo do piso para qualquer imagem que ainda seja uma imagem.
    # Um alvo de 1 KB não serve aqui — estas fixtures são pequenas o bastante
    # para caberem nele, e o teste passaria a medir o tamanho da fixture.
    recusado = _pedir(client, media_handles.register_media(imagens[0]), destino,
                      target={'value': 0.05, 'unit': 'KB'})
    assert recusado.status_code == 422, recusado.text

    aceito = _pedir(client, media_handles.register_media(imagens[1]), destino)
    assert aceito.status_code == 202
    _processar(aceito.json()['job_id'])
    assert jobs.get_job(aceito.json()['job_id'])['status'] == 'done'


def test_cada_job_carrega_o_seu_proprio_arquivo(client, imagens, tmp_path):
    """A propriedade que uma rota em lote perderia: saber **qual** arquivo é
    qual sem reconstruir a associação."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    ids = {}
    for caminho in imagens:
        handle = media_handles.register_media(caminho)
        ids[_pedir(client, handle, destino).json()['job_id']] = os.path.basename(caminho)

    for job_id, nome in ids.items():
        job = jobs.get_job(job_id)
        assert os.path.basename(job['input_path']) == nome


def test_os_resultados_sao_arquivos_distintos(client, imagens, tmp_path):
    """Três compressões para a mesma pasta não podem produzir um arquivo só —
    seria o lote apagando o próprio trabalho (Princípio XV)."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    saidas = []
    for caminho in imagens:
        job_id = _pedir(client, media_handles.register_media(caminho), destino).json()['job_id']
        _processar(job_id)
        saidas.append(jobs.get_job(job_id)['output_path'])

    assert len(set(saidas)) == len(saidas), f'saídas colidiram: {saidas}'
    for caminho in saidas:
        assert os.path.isfile(caminho)


def test_a_economia_do_lote_e_a_soma_do_que_foi_medido(client, imagens, tmp_path):
    """FR-022 no plural: o total do lote é a soma de medições, e não de
    estimativas somadas."""
    destino = tmp_path / 'saida'
    destino.mkdir()
    total_economizado = 0
    for caminho in imagens:
        job_id = _pedir(client, media_handles.register_media(caminho), destino).json()['job_id']
        _processar(job_id)
        medido = jobs.get_job(job_id)['compression']
        real = os.path.getsize(jobs.get_job(job_id)['output_path'])
        assert medido['output_size_bytes'] == real
        total_economizado += medido['saving_bytes']

    assert total_economizado != 0

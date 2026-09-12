"""O download roda no worker isolado; o erro atravessa o IPC ate' o job.

Sem `reason`/`detail` na travessia, o detalhe tecnico de um DownloadError se
perdia -- ou, pior, voltava a ser a unica coisa que a pessoa via.
"""
from __future__ import annotations

from app import jobs
from eterzion_upscale.media import _DOWNLOAD_MESSAGES


def test_detalhe_vai_para_a_area_recolhida_e_a_frase_fica_limpa():
    detalhe = 'x.safetensors: falha ao baixar de https://h.invalido/x (HTTP Error 429)'
    falha = jobs.WorkerFailure(_DOWNLOAD_MESSAGES['rate_limited'], 'DownloadError',
                               'rate_limited', detalhe)
    job: dict = {}
    jobs._record_failure(job, falha)
    assert job['error'] == _DOWNLOAD_MESSAGES['rate_limited']
    assert job['error_reason'] == 'rate_limited'
    assert job['error_detail'] == detalhe
    assert 'http' not in job['error'].lower()


def test_falha_sem_detalhe_nao_ganha_area_recolhida():
    job: dict = {}
    jobs._record_failure(job, jobs.WorkerFailure('CUDA out of memory', 'RuntimeError'))
    assert 'error_detail' not in job
    assert 'error_reason' not in job


def test_download_que_falhou_nao_vira_erro_de_processamento():
    """"Tente outro modelo ou dispositivo" e' o conselho errado para um 429."""
    falha = jobs.WorkerFailure(_DOWNLOAD_MESSAGES['rate_limited'], 'DownloadError', 'rate_limited', 'x')
    assert jobs._categorize_error(falha) == 'download_failed'
    assert jobs._categorize_error(jobs.WorkerFailure('boom', 'RuntimeError')) == 'model_failure'


def test_componente_guarda_o_motivo_para_a_interface_traduzir(monkeypatch):
    """A tela de Componentes tambem recebe o motivo: o texto do backend so'
    existe em portugues, e o app tem onze linguas."""
    import threading

    from app import processing
    from eterzion_upscale.media import DownloadError

    pronto = threading.Event()

    def falha():
        try:
            raise DownloadError('rate_limited', 'detalhe com https://h.invalido/x')
        finally:
            pronto.set()

    processing._start_background('anime_image', falha)
    assert pronto.wait(5)
    for _ in range(500):
        with processing._INSTALL_LOCK:
            if 'anime_image' not in processing._INSTALLING:
                break
        threading.Event().wait(0.01)
    try:
        with processing._INSTALL_LOCK:
            assert processing._INSTALL_ERROR_REASONS['anime_image'] == 'rate_limited'
            assert 'http' not in processing._INSTALL_ERRORS['anime_image'].lower()
    finally:
        with processing._INSTALL_LOCK:
            processing._INSTALL_ERRORS.pop('anime_image', None)
            processing._INSTALL_ERROR_REASONS.pop('anime_image', None)

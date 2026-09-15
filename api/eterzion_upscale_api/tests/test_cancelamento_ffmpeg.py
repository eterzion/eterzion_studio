"""Cancelar interrompe de verdade o ffmpeg dos trabalhos que rodam numa thread
da API: edicao de video, compressao e musica.

Antes, `cancel_job` so' sabia encerrar o worker isolado da IA. Esses tres
rodavam fora dele: cancelar marcava o job e deixava o ffmpeg ir ate' o fim --
e, na compressao, o arquivo era gravado no destino mesmo assim.

Nada simulado onde importa: um ffmpeg de verdade, codificando o bastante para
ainda estar rodando quando o cancelamento chega de outra thread. O que se mede
e' o tempo entre cancelar e o trabalho parar, e o que sobra no disco.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time

import pytest

from app import jobs
from app.compression import runner
from eterzion_upscale import media
from eterzion_upscale.media import (
    Cancelado,
    Cancelamento,
    escopo_de_cancelamento,
    ffmpeg_path,
    has_ffmpeg,
    run_ffmpeg,
)

pytestmark = pytest.mark.skipif(not has_ffmpeg(), reason='requires a real ffmpeg binary')

# VP9 no esforco maximo: minutos de trabalho em qualquer maquina, para o
# cancelamento chegar com o ffmpeg ainda codificando. Uma primeira versao usava
# FFV1, que codificou 120 s de video em menos de 5 s -- e o teste passava mesmo
# com o cancelamento desligado. Curto no tempo de video, para que uma regressao
# nao deixe o ffmpeg ocupando o runner do CI por muito tempo.
_LONGO = 'testsrc2=size=1280x720:rate=30:d=20'
_LIMITE_PARA_PARAR_S = 5.0


def _video(caminho: str, segundos: int = 40) -> str:
    """Um video real, rapido de gerar (mpeg4) e lento de recodificar em VP9."""
    r = subprocess.run([
        ffmpeg_path() or 'ffmpeg', '-y', '-f', 'lavfi', '-i',
        f'testsrc2=size=1280x720:rate=30:d={segundos}', '-c:v', 'mpeg4', '-q:v', '3', '-an', caminho,
    ], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return caminho


def _codificacao_longa(saida: str, comandos: list | None = None):
    def construir(f):
        if comandos is not None:
            comandos.append(f)  # para o teste conferir como o processo terminou
        return f.input(_LONGO, {'f': 'lavfi'}).output(
            saida, {'c:v': 'libvpx-vp9', 'deadline': 'good', 'cpu-used': '0', 'b:v': '2M'})
    return construir


# ------------------------------------------------------------- o mecanismo --


def test_cancelar_interrompe_o_ffmpeg_em_segundos(tmp_path):
    cancelamento = Cancelamento()
    resultado: dict[str, object] = {}
    comandos: list = []

    def trabalho():
        try:
            with escopo_de_cancelamento(cancelamento):
                run_ffmpeg(_codificacao_longa(str(tmp_path / 'saida.webm'), comandos))
            resultado['fim'] = 'terminou'
        except Cancelado:
            resultado['fim'] = 'cancelado'

    t = threading.Thread(target=trabalho, daemon=True)
    t.start()
    time.sleep(1.0)  # o ffmpeg ja' esta' codificando
    inicio = time.monotonic()
    cancelamento.cancelar()
    t.join(timeout=30)

    assert not t.is_alive(), 'o ffmpeg continuou rodando depois de cancelar'
    assert time.monotonic() - inicio < _LIMITE_PARA_PARAR_S
    assert resultado['fim'] == 'cancelado'
    # A prova direta, que nao depende de quanto a maquina e' rapida: o processo
    # foi morto (saida diferente de zero), e nao terminou sozinho (saida zero).
    # Numa maquina carregada o cancelamento pode chegar antes de o processo
    # existir -- e ai ele nem chega a ser criado, o que tambem esta' certo.
    processo = getattr(comandos[0], '_process', None) if comandos else None
    assert processo is None or processo.returncode not in (0, None)


def test_cancelado_quando_o_ffmpeg_ja_terminou_nao_vira_sucesso():
    # A corrida estreita: o ffmpeg termina (saida 0) e o cancelamento chega
    # antes de run_ffmpeg retornar. O execute() retorna normalmente; sem a
    # conferencia final, quem chamou seguiria em frente e moveria o resultado
    # para o destino de um job cancelado.
    cancelamento = Cancelamento()

    class TerminaEnquantoCancelam:
        def execute(self):
            cancelamento.cancelar()  # chega "durante" um execute que da' certo
            return b''

    with escopo_de_cancelamento(cancelamento), pytest.raises(Cancelado):
        run_ffmpeg(lambda f: TerminaEnquantoCancelam())


def test_cancelado_antes_de_comecar_nem_abre_o_ffmpeg():
    cancelamento = Cancelamento()
    cancelamento.cancelar()
    chamado = []

    def construir(f):
        chamado.append(True)
        return f

    with escopo_de_cancelamento(cancelamento), pytest.raises(Cancelado):
        run_ffmpeg(construir)
    assert chamado == []


def test_fora_de_um_escopo_nada_muda(tmp_path):
    saida = tmp_path / 'curto.mkv'
    run_ffmpeg(lambda f: f.input('testsrc2=size=64x64:rate=5:d=1', {'f': 'lavfi'})
               .output(str(saida), {'c:v': 'ffv1'}))
    assert saida.is_file()


def test_o_cancelamento_de_uma_thread_nao_atinge_outra(tmp_path):
    # O escopo e' por thread: dois jobs nunca compartilham um cancelamento.
    cancelado = Cancelamento()
    cancelado.cancelar()
    saida = tmp_path / 'outra.mkv'
    erros: list[BaseException] = []

    def outra_thread():
        try:
            run_ffmpeg(lambda f: f.input('testsrc2=size=64x64:rate=5:d=1', {'f': 'lavfi'})
                       .output(str(saida), {'c:v': 'ffv1'}))
        except BaseException as e:  # noqa: BLE001
            erros.append(e)

    with escopo_de_cancelamento(cancelado):
        t = threading.Thread(target=outra_thread)
        t.start()
        t.join(timeout=30)
    assert erros == []
    assert saida.is_file()


def test_cancelamento_que_chega_antes_do_processo_existir_nao_se_perde():
    # A python-ffmpeg so' cria o processo dentro do execute(); quem cancela
    # nessa janela nao tem o que matar ainda. O processo que aparece depois tem
    # que ser morto do mesmo jeito.
    class Processo:
        morto = False

        def kill(self):
            Processo.morto = True

    class Comando:
        pass

    comando = Comando()
    fim = threading.Event()

    def aparecer_depois():
        time.sleep(0.3)
        comando._process = Processo()

    threading.Thread(target=aparecer_depois).start()
    media._matar_quando_existir(comando, fim)
    assert Processo.morto


# ------------------------------------------------------------- a compressao --


def test_compressao_cancelada_nao_grava_nada_no_destino(tmp_path):
    origem = _video(str(tmp_path / 'origem.mp4'))
    destino = tmp_path / 'saida' / 'comprimido.webm'
    cancelamento = Cancelamento()
    resultado: dict[str, object] = {}

    def trabalho():
        try:
            with escopo_de_cancelamento(cancelamento):
                runner.run('video', origem, str(destino),
                           {'container': 'webm', 'video_codec': 'vp9', 'mode': 'advanced'})
            resultado['fim'] = 'terminou'
        except Cancelado:
            resultado['fim'] = 'cancelado'
        except Exception as e:  # noqa: BLE001
            resultado['fim'] = f'erro: {e!r}'

    t = threading.Thread(target=trabalho, daemon=True)
    t.start()
    time.sleep(1.5)
    inicio = time.monotonic()
    cancelamento.cancelar()
    t.join(timeout=30)

    assert not t.is_alive()
    assert time.monotonic() - inicio < _LIMITE_PARA_PARAR_S
    assert resultado['fim'] == 'cancelado'
    # O defeito que motivou isto: o arquivo aparecia no destino mesmo cancelado.
    assert not destino.exists()


# ---------------------------------------------------- o fio inteiro: cancel_job --


def test_cancel_job_para_a_edicao_de_video_e_nao_deixa_arquivo(tmp_path):
    origem = _video(str(tmp_path / 'origem.mp4'))
    job_id = jobs.create_job(
        input_path=origem, filename='origem.mp4', media_type='video', operation='video_edit',
        params={
            'edits': {}, 'container': 'webm', 'profile': 'quality',
            'source_width': 1280, 'source_height': 720, 'has_audio': False,
            'output_target': {'format': 'webm', 'directory': str(tmp_path / 'saida'),
                              'filename': None, 'conflict': 'rename'},
        },
    )
    job = jobs.jobs[job_id]
    t = threading.Thread(target=lambda: asyncio.run(jobs._process_job(job_id)), daemon=True)
    t.start()
    try:
        for _ in range(100):
            if job['status'] == 'processing' and job.get('partial_output'):
                break
            time.sleep(0.05)
        time.sleep(1.0)  # o ffmpeg ja' esta' codificando
        inicio = time.monotonic()
        assert jobs.cancel_job(job_id)
        t.join(timeout=30)
        assert not t.is_alive()
        assert time.monotonic() - inicio < _LIMITE_PARA_PARAR_S
    finally:
        # Daemon: se o cancelamento regredir, o teste falha acima em vez de
        # prender o processo do pytest esperando o ffmpeg terminar.
        t.join(timeout=5)

    assert job['status'] == 'cancelled'
    assert not job.get('error')
    # Nem o resultado, nem o parcial.
    saida = tmp_path / 'saida'
    assert not saida.exists() or list(saida.iterdir()) == []
    assert job_id not in jobs._cancelamentos

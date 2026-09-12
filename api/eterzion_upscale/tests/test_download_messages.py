"""A frase de um download que falhou e' para quem usa o app.

Caso real que originou isto: a tela de Componentes mostrou "Todas as fontes de
download falharam para 2xHFA2kSPAN.safetensors: - Falha ao baixar o modelo de
https://huggingface.co/... (HTTP Error 429: Too Many Requests)". Um 429 so'
pede para esperar; a tela o apresentava como defeito, com link e com o nome
interno do modelo.
"""
from __future__ import annotations

import errno
import socket
import urllib.error

import pytest

from eterzion_upscale import media
from eterzion_upscale.media import _DOWNLOAD_MESSAGES, DownloadError, download_with_fallback

URL = 'https://huggingface.co/Phips/2xHFA2kSPAN/resolve/main/2xHFA2kSPAN.safetensors'


def _http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, codigo, 'x', {}, None)


def _falha_com(monkeypatch, erro: BaseException) -> None:
    def explode(url, dst, hash_prefix=None, progress=True):
        raise erro
    monkeypatch.setattr(media, 'download_url_to_file', explode)


@pytest.mark.parametrize(('erro', 'motivo'), [
    (_http(429), 'rate_limited'),
    (_http(503), 'server_unavailable'),
    (_http(404), 'not_found'),
    (urllib.error.URLError(ConnectionRefusedError('recusada')), 'network'),
    (urllib.error.URLError(socket.timeout('lento')), 'server_unavailable'),
    (TimeoutError('lento'), 'server_unavailable'),
    (OSError(errno.ENOSPC, 'No space left on device'), 'disk_full'),
    (ValueError('qualquer outra coisa'), 'unknown'),
], ids=['429', '503', '404', 'sem-conexao', 'timeout-url', 'timeout', 'disco-cheio', 'desconhecido'])
def test_cada_falha_vira_a_frase_do_seu_motivo(tmp_path, monkeypatch, erro, motivo):
    _falha_com(monkeypatch, erro)
    with pytest.raises(DownloadError) as capturado:
        media.load_file_from_url(URL, model_dir=str(tmp_path), progress=False)
    assert capturado.value.reason == motivo
    assert str(capturado.value) == _DOWNLOAD_MESSAGES[motivo]


@pytest.mark.parametrize('motivo', sorted(_DOWNLOAD_MESSAGES))
def test_nenhuma_frase_carrega_link_nem_nome_de_arquivo(motivo):
    frase = DownloadError(motivo, f'detalhe com {URL}').args[0]
    assert 'http' not in frase.lower() and '://' not in frase
    assert '.safetensors' not in frase and '.pth' not in frase and '.onnx' not in frase
    assert 'HTTP Error' not in frase


def test_o_detalhe_tecnico_continua_disponivel(tmp_path, monkeypatch):
    """Quem investiga ainda precisa do link e do codigo -- so' nao na frase."""
    _falha_com(monkeypatch, _http(429))
    with pytest.raises(DownloadError) as capturado:
        media.load_file_from_url(URL, model_dir=str(tmp_path), progress=False)
    assert URL in capturado.value.detail
    assert '429' in capturado.value.detail
    assert '2xHFA2kSPAN.safetensors' in capturado.value.detail


def test_entre_fontes_o_motivo_acionavel_vence(tmp_path, monkeypatch):
    """Espelho sem o arquivo (404) e origem limitando (429): a pessoa precisa
    ouvir "tente em alguns minutos", nao "arquivo indisponivel"."""
    respostas = iter([_http(404), _http(429)])
    def explode(url, dst, hash_prefix=None, progress=True):
        raise next(respostas)
    monkeypatch.setattr(media, 'download_url_to_file', explode)
    with pytest.raises(DownloadError) as capturado:
        download_with_fallback(['https://espelho.invalido/w.pth', URL],
                               model_dir=str(tmp_path), progress=False, file_name='w.pth')
    assert capturado.value.reason == 'rate_limited'


def test_rede_so_e_culpada_quando_nenhuma_fonte_respondeu(tmp_path, monkeypatch):
    """Se uma fonte respondeu 404, a conexao funciona: "verifique sua internet"
    mandaria a pessoa procurar no lugar errado."""
    respostas = iter([urllib.error.URLError(ConnectionRefusedError()), _http(404)])
    def explode(url, dst, hash_prefix=None, progress=True):
        raise next(respostas)
    monkeypatch.setattr(media, 'download_url_to_file', explode)
    with pytest.raises(DownloadError) as capturado:
        download_with_fallback(['https://a.invalido/w.pth', 'https://b.invalido/w.pth'],
                               model_dir=str(tmp_path), progress=False, file_name='w.pth')
    assert capturado.value.reason == 'not_found'

    todas_de_rede = iter([urllib.error.URLError(ConnectionRefusedError())] * 2)
    def sem_rede(url, dst, hash_prefix=None, progress=True):
        raise next(todas_de_rede)
    monkeypatch.setattr(media, 'download_url_to_file', sem_rede)
    with pytest.raises(DownloadError) as capturado:
        download_with_fallback(['https://a.invalido/w.pth', 'https://b.invalido/w.pth'],
                               model_dir=str(tmp_path), progress=False, file_name='w.pth')
    assert capturado.value.reason == 'network'


def test_os_motivos_batem_com_a_lista_da_interface():
    """A interface escolhe a frase pelo motivo, em onze linguas. A mesma
    lista esta' fixada em interface/.../downloadErrorCopy.spec.ts: um motivo
    novo aqui sem frase la' mostraria a chave crua do i18n na tela."""
    assert set(_DOWNLOAD_MESSAGES) == {
        'rate_limited', 'server_unavailable', 'not_found', 'network',
        'corrupted', 'disk_full', 'unknown',
    }

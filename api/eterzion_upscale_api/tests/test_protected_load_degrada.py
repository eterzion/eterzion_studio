"""O carregamento protegido e' opcional: quando o servico de licenciamento nao
responde, o processamento tem que cair no handler estatico, nao morrer.

Regressao de um defeito real, visivel so' no app empacotado: o `_http_get` de
`app.security` deixava escapar um `urllib.error.HTTPError` cru, que atravessava
o `except ProtectedLoadError` de `_resolve_protected_module`. O job terminava
com `error='HTTP Error 404: Not Found'` e `error_category='model_failure'` --
apontando para o modelo, que estava intacto em disco e carregava normalmente.
"""
from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from app import security


def _http_error(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        'https://licencas.invalido/packages/x', codigo, 'Not Found', {},
        io.BytesIO(b'{"detail":"nao encontrado"}'),
    )


class TestHttpGetEmbrulhaOErro:
    def test_http_error_vira_protected_load_error_com_o_status(self, monkeypatch):
        monkeypatch.setattr(
            urllib.request, 'urlopen',
            lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)),
        )
        with pytest.raises(security.ProtectedLoadError) as capturado:
            security._http_get('https://licencas.invalido/packages/x')
        assert capturado.value.status == 404
        # O corpo da resposta entra na mensagem: sem ele, quem le' o log so'
        # sabe que deu 404, nao o que o servico disse.
        assert 'nao encontrado' in str(capturado.value)

    def test_o_mesmo_vale_para_installation_status(self, monkeypatch):
        monkeypatch.setattr(
            urllib.request, 'urlopen',
            lambda req, timeout=None: (_ for _ in ()).throw(_http_error(404)),
        )
        with pytest.raises(security.ProtectedLoadError):
            security.installation_status('https://licencas.invalido', 'inst123')


class TestResolveProtectedModuleDegrada:
    """O contrato que o defeito quebrava: devolver None em vez de propagar."""

    @pytest.fixture
    def resolver(self):
        from app.jobs import _resolve_protected_module

        return _resolve_protected_module

    def test_sem_protected_devolve_none(self, resolver):
        assert resolver(None) is None

    @pytest.mark.parametrize(
        'erro',
        [
            security.ProtectedLoadError('404', 404),
            urllib.error.URLError('nome nao resolvido'),
            ConnectionRefusedError('recusada'),
            TimeoutError('estourou'),
        ],
        ids=['http', 'dns', 'recusada', 'timeout'],
    )
    def test_falha_do_servico_degrada_para_none(self, resolver, monkeypatch, erro):
        def explode(**kwargs):
            raise erro

        monkeypatch.setattr(security, 'load_protected_module', explode)
        monkeypatch.setattr(security, 'ensure_identity', lambda: object())
        assert resolver({'base_url': 'https://licencas.invalido',
                         'model': 'nomos-webphoto', 'version': 'latest'}) is None

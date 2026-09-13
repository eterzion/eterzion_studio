"""T036 — HTTP-layer tests for the license facade routes. Network calls to
eterzion_licensing_service are stubbed at the same seam license_gate.py's own
tests use (license_gate._http_get / protected_loader's HTTP helpers), so the
real routing/branching logic runs end to end."""
from __future__ import annotations

import urllib.error

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import license_router


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('APPDATA', raising=False)


@pytest.fixture(autouse=True)
def no_license_details(monkeypatch):
    """Por padrao o servidor nao responde ao pedido de detalhes; cada teste
    que precisa dele troca o stub. Sem isto, /license/status 'active' iria a'
    rede de verdade."""
    from app import licensing

    def _offline(url, body, timeout=5.0):
        raise urllib.error.URLError('offline')

    monkeypatch.setattr(licensing, '_http_post_json', _offline)
    licensing.clear_license_details()
    yield
    licensing.clear_license_details()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(license_router, prefix='/license')
    return TestClient(app)


class _FakeIdentity:
    install_id = 'install-fake'
    signing_public_key_b64 = 'c2lnbmluZy1rZXk='
    encryption_public_key_b64 = 'ZW5jcnlwdGlvbi1rZXk='

    def sign(self, message: bytes) -> bytes:
        return b'assinado:' + message


def _configure(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'licensing_service_url', 'http://licensing.test')
    monkeypatch.setattr('app.security.ensure_identity', lambda: _FakeIdentity())


class TestGetStatus:
    def test_reports_not_configured_when_no_service_configured(self, client, monkeypatch):
        # 'not_configured' (not 'not_activated') is the correct distinct state here:
        # this is the dev/local default (empty licensing_service_url +
        # ASTROS_DEV_ALLOW_UNLICENSED), where check_gate() already allows job
        # creation — the frontend must not treat this the same as a real
        # never-activated installation and hard-block the whole app shell.
        from app.config import settings

        monkeypatch.setattr(settings, 'licensing_service_url', '')
        res = client.get('/license/status')
        assert res.status_code == 200
        assert res.json()['state'] == 'not_configured'

    def test_reports_active_with_seat_counts(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        monkeypatch.setattr(license_gate, '_http_get', lambda url, timeout=5.0: {
            'license_id': 'lic_1', 'status': 'active', 'installations_used': 1, 'installations_limit': 2,
        })
        res = client.get('/license/status')
        assert res.status_code == 200
        body = res.json()
        assert body['state'] == 'active'
        assert body['installations_used'] == 1
        assert body['installations_limit'] == 2

    def test_reports_not_activated_for_a_never_activated_installation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        def _raise_404(url, timeout=5.0):
            raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

        monkeypatch.setattr(license_gate, '_http_get', _raise_404)
        res = client.get('/license/status')
        assert res.json()['state'] == 'not_activated'


class TestActivate:
    def test_returns_409_when_no_service_configured(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'licensing_service_url', '')
        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 409

    def test_activates_and_records_a_successful_check(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_cache
        from app import security as protected_loader

        monkeypatch.setattr(protected_loader, '_http_post', lambda url, body: {'ok': True})
        assert license_cache.days_since_last_success() is None

        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 200
        assert license_cache.days_since_last_success() == pytest.approx(0.0, abs=0.1)

    def test_surfaces_a_clear_error_when_the_service_rejects_activation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import security as protected_loader

        def _raise(url, body):
            raise protected_loader.ProtectedLoadError('licença inválida')

        monkeypatch.setattr(protected_loader, '_http_post', _raise)
        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 502

    def test_an_unknown_license_is_the_users_error_not_a_gateway_failure(self, client, monkeypatch):
        """404 é decisão do serviço: aquela licença não existe.

        Isto saía como 502, e a tela pedia para o usuário verificar a conexão de
        internet — enquanto o serviço havia respondido na hora, dizendo o que
        estava errado. Reproduzido com o ID 'ee' num app real: HTTP 404
        {"detail":"Licença não encontrada."} apresentado como falha de rede.
        """
        _configure(monkeypatch)
        from app import security as protected_loader

        def _raise_404(url, body):
            raise protected_loader.ProtectedLoadError(
                f'{url} -> HTTP 404: {{"detail":"Licença não encontrada."}}', 404)

        monkeypatch.setattr(protected_loader, '_http_post', _raise_404)
        res = client.post('/license/activate', json={'license_id': 'inexistente'})

        assert res.status_code == 404
        detalhe = res.json()['detail']
        assert 'não encontrada' in detalhe
        # A mensagem tem de orientar, e nao expor a URL interna do servico.
        assert 'http' not in detalhe.lower()

    def test_keeps_502_when_the_service_itself_failed(self, client, monkeypatch):
        """5xx e timeout continuam sendo falha de infraestrutura — insistir ou
        checar a conexão são conselhos corretos aí."""
        _configure(monkeypatch)
        from app import security as protected_loader

        def _raise_500(url, body):
            raise protected_loader.ProtectedLoadError(f'{url} -> HTTP 500: erro', 500)

        monkeypatch.setattr(protected_loader, '_http_post', _raise_500)
        res = client.post('/license/activate', json={'license_id': 'lic_1'})
        assert res.status_code == 502


class TestRelease:
    def test_returns_409_when_not_activated(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate

        def _raise_404(url, timeout=5.0):
            raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

        monkeypatch.setattr(license_gate, '_http_get', _raise_404)
        res = client.post('/license/release')
        assert res.status_code == 409

    def test_releases_a_real_activated_installation(self, client, monkeypatch):
        _configure(monkeypatch)
        from app import licensing as license_gate
        from app import security as protected_loader

        monkeypatch.setattr(
            license_gate, '_http_get',
            lambda url, timeout=5.0: {'license_id': 'lic_1', 'status': 'active'})
        monkeypatch.setattr(
            protected_loader, '_http_get',
            lambda url: {'license_id': 'lic_1', 'status': 'active'})
        released = {}

        def _fake_release(base_url, license_id, install_id):
            released['license_id'] = license_id
            released['install_id'] = install_id
            return {'ok': True}

        monkeypatch.setattr(protected_loader, 'release', _fake_release)
        res = client.post('/license/release')
        assert res.status_code == 200
        assert released == {'license_id': 'lic_1', 'install_id': 'install-fake'}


class TestLicenseDetails:
    """O final da chave e o e-mail no popover: pedido assinado pela instalacao,
    guardado so' em memoria."""

    def _active(self, monkeypatch):
        _configure(monkeypatch)
        from app import licensing

        monkeypatch.setattr(licensing, '_http_get', lambda url, timeout=5.0: {
            'license_id': 'lic_abc', 'status': 'active', 'installations_used': 1, 'installations_limit': 1,
        })
        return licensing

    def test_active_status_carries_last4_and_email(self, client, monkeypatch):
        import base64

        licensing = self._active(monkeypatch)
        pedidos = []

        def _details(url, body, timeout=5.0):
            pedidos.append((url, body))
            return {'license_last4': '3f2a', 'email': 'cliente@example.com'}

        monkeypatch.setattr(licensing, '_http_post_json', _details)
        body = client.get('/license/status').json()
        assert body['license_last4'] == '3f2a'
        assert body['email'] == 'cliente@example.com'

        url, pedido = pedidos[0]
        assert url == 'http://licensing.test/activations/details'
        assert pedido['install_id'] == 'install-fake'
        assinado = base64.b64decode(pedido['signature_b64'])
        assert assinado == f"assinado:eterzion-license-details:install-fake:{pedido['timestamp']}".encode()

        # Uma vez por sessao: a segunda consulta usa a memoria.
        client.get('/license/status')
        assert len(pedidos) == 1

    def test_without_the_details_the_status_still_works(self, client, monkeypatch):
        """Sem rede, ou com um servidor anterior a esta rota: o popover so' nao
        mostra as duas linhas."""
        self._active(monkeypatch)
        body = client.get('/license/status').json()
        assert body['state'] == 'active'
        assert body['license_last4'] is None
        assert body['email'] is None

    def test_a_failure_is_not_retried_on_every_status(self, client, monkeypatch):
        licensing = self._active(monkeypatch)
        tentativas = []

        def _falha(url, body, timeout=5.0):
            tentativas.append(url)
            raise urllib.error.HTTPError(url, 404, 'not found', hdrs=None, fp=None)

        monkeypatch.setattr(licensing, '_http_post_json', _falha)
        client.get('/license/status')
        client.get('/license/status')
        assert len(tentativas) == 1

    def test_offline_only_uses_what_is_in_memory(self, client, monkeypatch):
        licensing = self._active(monkeypatch)
        monkeypatch.setattr(licensing, '_http_post_json',
                            lambda url, body, timeout=5.0: {'license_last4': '3f2a', 'email': 'c@example.com'})
        client.get('/license/status')

        def _sem_rede(url, timeout=5.0):
            raise urllib.error.URLError('offline')

        def _nao_chame(url, body, timeout=5.0):
            raise AssertionError('offline nao deve pedir de novo')

        monkeypatch.setattr(licensing, '_http_get', _sem_rede)
        monkeypatch.setattr(licensing, '_http_post_json', _nao_chame)
        licensing.record_successful_check()
        body = client.get('/license/status').json()
        assert body['state'] == 'offline_tolerance'
        assert body['email'] == 'c@example.com'

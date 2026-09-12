"""T070 — HTTP-layer tests for routes_components.py — GET /components,
GET /components/{id}/details, install/update. Real component_manager.py
underneath (no mocking of the registry itself); settings.models_dir points at
an empty temp dir so install_state is deterministic regardless of what's
cached on the machine running the test."""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import processing
from app.routes import components_router
from app.config import settings


def _wait_for_background(component_id: str, timeout: float = 10.0) -> None:
    """Espera a thread de instalação terminar.

    `POST /install` agora responde assim que valida e dispara, então afirmar
    sobre o resultado exige esperar — mas por condição, nunca por `sleep` de
    duração fixa, que é o que torna teste dependente da carga da máquina."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with processing._INSTALL_LOCK:
            if component_id not in processing._INSTALLING:
                return
        time.sleep(0.01)
    raise AssertionError(f'instalação de {component_id} não terminou em {timeout}s')


@pytest.fixture(autouse=True)
def empty_models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'models_dir', str(tmp_path / 'models'))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(components_router, prefix='/components')
    return TestClient(app)


class TestListComponents:
    def test_returns_the_six_content_type_components(self, client):
        from app.processing import CAPABILITY_LABELS

        res = client.get('/components')
        assert res.status_code == 200
        body = res.json()
        assert {c['id'] for c in body} == set(CAPABILITY_LABELS)

    def test_never_exposes_technical_name_in_the_list_response(self, client):
        """FR-009/FR-063 — the list-level Component schema has no
        technical_name/version/provenance/license fields at all."""
        res = client.get('/components')
        for component in res.json():
            assert set(component.keys()) == {
                'id', 'capability_label', 'size_mb', 'install_state', 'update_available',
            }

    def test_nothing_downloaded_reports_not_installed(self, client):
        res = client.get('/components')
        image_video = [c for c in res.json() if c['id'] in ('photo', 'anime_image', 'real_video', 'anime_video')]
        assert image_video
        for c in image_video:
            assert c['install_state'] == 'not_installed'
            assert c['size_mb'] == 0


class TestComponentDetails:
    def test_details_expose_technical_fields(self, client):
        res = client.get('/components/photo/details')
        assert res.status_code == 200
        body = res.json()
        assert body['technical_name'] == 'nomos-webphoto'
        assert body['license']

    def test_returns_404_for_unknown_component(self, client):
        res = client.get('/components/not-real/details')
        assert res.status_code == 404


class TestInstallUpdate:
    def test_install_speech_returns_200_and_downloads_weights(self, client, monkeypatch):
        from eterzion_upscale import processing as biblioteca

        pedidos = []
        monkeypatch.setattr(biblioteca, 'ensure_speech_weights', lambda model_dir: pedidos.append(model_dir))
        res = client.post('/components/speech/install')
        assert res.status_code == 200
        assert res.json()['id'] == 'speech'
        # Esperar a thread de fundo: sem isso ela sobrevive ao monkeypatch e
        # baixaria os pesos de verdade no proximo teste.
        _wait_for_background('speech')
        assert len(pedidos) == 1

    def test_install_music_422_carries_a_reason_for_the_ui(self, client):
        res = client.post('/components/music/install')
        assert res.status_code == 422
        assert res.json()['detail']['reason'] == 'not_available_in_app'
        assert 'README' not in res.json()['detail']['message']

    def test_install_unknown_component_returns_404(self, client):
        res = client.post('/components/not-real/install')
        assert res.status_code == 404

    def test_install_answers_immediately_with_installing(self, client, monkeypatch):
        """A rota respondia só depois do download inteiro, o que para o modelo
        maior é a tela parada por minutos — que a pessoa lê como app travado.
        Agora ela valida, dispara e responde `installing`; o estado real chega
        pela própria listagem, que a tela já consulta."""
        import threading

        from eterzion_upscale import processing as upscale

        libera = threading.Event()
        monkeypatch.setattr(upscale, 'resolve_model', lambda *a, **k: libera.wait(5))
        try:
            res = client.post('/components/anime_image/install')
            assert res.status_code == 200
            assert res.json()['install_state'] == 'installing'
            listado = next(c for c in client.get('/components').json() if c['id'] == 'anime_image')
            assert listado['install_state'] == 'installing'
        finally:
            libera.set()
            _wait_for_background('anime_image')

    @pytest.mark.slow
    def test_real_install_of_a_small_model(self, client):
        install_res = client.post('/components/anime_image/install')
        assert install_res.status_code == 200
        assert install_res.json()['install_state'] == 'installing'
        _wait_for_background('anime_image')
        state = next(c for c in client.get('/components').json() if c['id'] == 'anime_image')
        assert state['install_state'] == 'installed'


class TestUninstall:
    """`DELETE /components/{id}` — a rota que contracts/api.md já especificava
    ("POST /components/{id}/install, POST .../update, DELETE ...") e que nunca
    foi implementada. Sem ela uma capacidade instalada ocupava disco para
    sempre, apesar de a lista expor `size_mb` para a pessoa poder decidir."""

    def test_unknown_component_returns_404(self, client):
        assert client.delete('/components/not-real').status_code == 404

    def test_speech_removes_its_weights(self, client):
        """Antes recusava (era um extra do pip); agora a voz so' tem pesos a
        apagar, e remover o que nao esta' la' e' sucesso."""
        res = client.delete('/components/speech')
        assert res.status_code == 200
        assert res.json()['install_state'] == 'not_installed'

    def test_removing_what_is_not_there_succeeds(self, client):
        """Remover duas vezes seguidas tem de funcionar: quem pede a remoção
        quer o arquivo ausente, e ele já está."""
        first = client.delete('/components/anime_image')
        assert first.status_code == 200
        assert first.json()['install_state'] == 'not_installed'
        assert client.delete('/components/anime_image').status_code == 200

    @pytest.mark.slow
    def test_install_then_uninstall_frees_the_files(self, client):
        assert client.post('/components/anime_image/install').json()['install_state'] == 'installed'
        removed = client.delete('/components/anime_image')
        assert removed.status_code == 200
        assert removed.json()['install_state'] == 'not_installed'
        assert removed.json()['size_mb'] == 0

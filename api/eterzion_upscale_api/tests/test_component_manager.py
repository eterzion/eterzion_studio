"""T068 — real coverage of processing.py. list_components()/
get_component_details() run against the real models/ directory (no mocking
of file presence or license lookups) — the install round trip uses a real,
temporary models_dir so it can perform a genuine download + SHA-256 verify
without touching the shared models/ cache other tests rely on."""
from __future__ import annotations

import time

import pytest

from app import processing
from app.config import settings


def _wait_for_background(component_id: str, timeout: float = 10.0) -> None:
    """Espera a thread de instalação terminar.

    O `install_component` retorna assim que a valida e dispara — esperar aqui
    é o que permite afirmar sobre o resultado sem tornar o teste dependente de
    tempo de relógio."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with processing._INSTALL_LOCK:
            if component_id not in processing._INSTALLING:
                return
        time.sleep(0.01)
    raise AssertionError(f'instalação de {component_id} não terminou em {timeout}s')
from app.processing import (
    CAPABILITY_LABELS,
    ComponentActionUnsupportedError,
    ComponentNotFoundError,
)


class TestListComponents:
    def test_returns_exactly_the_six_content_type_components(self):
        components = processing.list_components()
        assert {c.id for c in components} == set(CAPABILITY_LABELS)

    def test_never_exposes_a_raw_model_identifier_as_the_capability_label(self):
        """FR-009/FR-063 — capability_label must be a human sentence, never
        an internal engine_ref like 'nomos-webphoto' or 'super-voz'."""
        from app.licensing import _CONTENT_TYPE_IMPLEMENTATIONS

        components = processing.list_components()
        raw_refs = {
            impl.engine_ref for impl in _CONTENT_TYPE_IMPLEMENTATIONS.values() if impl.engine_ref
        }
        for c in components:
            assert c.capability_label not in raw_refs
            assert c.id in CAPABILITY_LABELS  # id is a content_type slug, not an engine_ref

    def test_photo_reflects_real_download_state(self):
        """The real photo model (nomos-webphoto) is already downloaded on
        this dev machine (used throughout this session's other real tests)
        — list_components() must report that truthfully."""
        details = processing.get_component_details('photo')
        assert details.install_state in ('installed', 'update_available')
        assert details.size_mb > 0
        assert details.technical_name == 'nomos-webphoto'
        assert details.license  # real license string, not empty

    def test_music_details_carry_no_developer_notes(self):
        """A licenca vai limpa, como nos Creditos; sem "condicional", sem
        mandar ler MODEL_LICENSES.md ou api/README.md."""
        details = processing.get_component_details('music')
        assert details.license == 'Apache-2.0'
        for proibido in ('condicional', 'README', 'MODEL_LICENSES'):
            assert proibido not in details.license and proibido not in details.version

    def test_unknown_component_raises(self):
        with pytest.raises(ComponentNotFoundError):
            processing.get_component_details('not-a-real-component')


class TestSpeechInstallsItsWeights:
    """Voz: o motor (audiosronnx + onnxruntime) vem no instalador; Instalar
    baixa os pesos pelo mesmo caminho dos modelos de imagem. Ate' 2026-09-12
    era um `pip install` do extra [audio] -- impossivel no app empacotado, que
    nao tem pip, e a tela so' podia mandar rodar o codigo-fonte."""

    @pytest.fixture(autouse=True)
    def pasta_de_modelos(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, 'models_dir', str(tmp_path))
        return tmp_path

    def test_install_baixa_os_pesos_na_pasta_de_modelos(self, monkeypatch, pasta_de_modelos):
        from eterzion_upscale import processing as biblioteca

        pedidos = []
        monkeypatch.setattr(biblioteca, 'ensure_speech_weights', lambda model_dir: pedidos.append(model_dir))
        result = processing.install_component('speech')
        _wait_for_background('speech')

        assert result.id == 'speech'
        assert pedidos == [str(pasta_de_modelos)]
        assert processing.get_component_details('speech').error is None

    def test_install_funciona_no_app_empacotado(self, monkeypatch):
        """O caso que a mudanca existe para resolver: sys.frozen nao bloqueia mais."""
        from eterzion_upscale import processing as biblioteca

        monkeypatch.setattr('sys.frozen', True, raising=False)
        pedidos = []
        monkeypatch.setattr(biblioteca, 'ensure_speech_weights', lambda model_dir: pedidos.append(model_dir))
        processing.install_component('speech')
        _wait_for_background('speech')
        assert len(pedidos) == 1

    def test_update_garante_os_mesmos_pesos(self, monkeypatch):
        from eterzion_upscale import processing as biblioteca

        pedidos = []
        monkeypatch.setattr(biblioteca, 'ensure_speech_weights', lambda model_dir: pedidos.append(model_dir))
        processing.update_component('speech')
        _wait_for_background('speech')
        assert len(pedidos) == 1

    def test_instalada_so_com_os_pesos_no_disco(self, pasta_de_modelos):
        from eterzion_upscale.processing import SPEECH_WEIGHTS, SPEECH_WEIGHTS_DIR

        assert processing.get_component_details('speech').install_state == 'not_installed'
        pasta = pasta_de_modelos / SPEECH_WEIGHTS_DIR
        pasta.mkdir()
        for nome in SPEECH_WEIGHTS:
            (pasta / nome).write_bytes(b'x' * (1024 * 1024))
        detalhes = processing.get_component_details('speech')
        assert detalhes.install_state == 'installed'
        assert detalhes.size_mb == 2
        assert 'pip' not in detalhes.version

    def test_remover_apaga_os_pesos(self, pasta_de_modelos):
        from eterzion_upscale.processing import SPEECH_WEIGHTS, SPEECH_WEIGHTS_DIR

        pasta = pasta_de_modelos / SPEECH_WEIGHTS_DIR
        pasta.mkdir()
        for nome in SPEECH_WEIGHTS:
            (pasta / nome).write_bytes(b'x')
        assert processing.uninstall_component('speech').install_state == 'not_installed'
        assert not any(pasta.iterdir())
        # remover de novo o que ja' nao esta' la' continua sendo sucesso
        assert processing.uninstall_component('speech').install_state == 'not_installed'

    def test_falha_de_download_chega_com_motivo(self, monkeypatch):
        from eterzion_upscale import processing as biblioteca
        from eterzion_upscale.media import DownloadError

        def falha(model_dir):
            raise DownloadError('rate_limited', 'backbone.onnx: HTTP Error 429 em https://h.invalido/x')

        monkeypatch.setattr(biblioteca, 'ensure_speech_weights', falha)
        processing.install_component('speech')
        _wait_for_background('speech')
        detalhes = processing.get_component_details('speech')
        assert detalhes.error_reason == 'rate_limited'
        assert 'http' not in (detalhes.error or '').lower()


class TestMusicIsNotInstallableFromTheApp:
    """Musica precisa de um ambiente CUDA de varios GB, placa de 6-8 GB e token
    do Hugging Face com os termos da Stability aceitos. Nada disso cabe num
    botao -- e a recusa tem de falar com quem usa o app, nao com quem o
    desenvolve."""

    @pytest.mark.parametrize('acao', ['install_component', 'update_component'])
    def test_recusa_com_motivo_e_sem_texto_de_desenvolvedor(self, acao, monkeypatch):
        chamadas = []
        monkeypatch.setattr(processing.subprocess, 'run', lambda *a, **k: chamadas.append(a))
        with pytest.raises(ComponentActionUnsupportedError) as erro:
            getattr(processing, acao)('music')
        assert erro.value.reason == 'not_available_in_app'
        mensagem = str(erro.value)
        for proibido in ('README', 'venv', 'HF_TOKEN', 'pip', 'SonicMaster', 'audio-worker'):
            assert proibido not in mensagem
        assert not chamadas


@pytest.mark.slow
class TestInstallRoundTrip:
    """Real network download + real SHA-256 verify, isolated to a temp
    models_dir so the shared models/ cache other tests depend on is never
    touched."""

    def test_install_a_real_small_model(self, tmp_path, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, 'models_dir', str(tmp_path))

        before = processing.get_component_details('anime_image')
        assert before.install_state == 'not_installed'
        assert before.size_mb == 0

        processing.install_component('anime_image')
        # `install_component` volta assim que valida e dispara a thread, então o
        # que ele devolve descreve o ANTES. Afirmar sobre esse retorno era o que
        # fazia este teste falhar com `'installing' == 'installed'` — não uma
        # instalação quebrada, uma leitura cedo demais. Os testes de speech
        # acima já esperavam; este ficou para trás.
        #
        # Generoso porque aqui há download real: o modelo do anime tem ~8,5 MB,
        # e uma rede lenta não deve reprovar código correto.
        _wait_for_background('anime_image', timeout=180.0)

        depois = processing.get_component_details('anime_image')
        assert depois.install_state == 'installed'
        assert depois.size_mb > 0

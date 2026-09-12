"""O worker isolado tem de subir também no app EMPACOTADO.

Fora do bundle, `sys.executable -m app.jobs` funciona porque `sys.executable` é
um Python de verdade. Dentro de um bundle do PyInstaller ele é o próprio
executável, e o bootloader ignora `-m`: o comando subia uma SEGUNDA cópia da
API.

Isso foi medido na 1.0.7 instalada — lançar `eterzion-studio-api.exe -m
app.jobs <addr>` fazia a porta 8051 responder. O `Listener` nunca recebia
conexão, todo processamento morria no timeout de 45s, e o erro chegava à
interface sem mensagem: o usuário via "Erro no processamento. Tente novamente",
que sugere algo transitório, para um defeito que falhava 100% das vezes.
"""
from __future__ import annotations

import pytest

from app import jobs, security


class TestSpawnArgs:
    def test_uses_the_module_flag_when_running_from_source(self, monkeypatch):
        monkeypatch.delattr('sys.frozen', raising=False)
        assert jobs._default_spawn_args() == ['-m', 'app.jobs']

    def test_relaunches_itself_with_a_sentinel_when_frozen(self, monkeypatch):
        monkeypatch.setattr('sys.frozen', True, raising=False)
        args = jobs._default_spawn_args()

        assert args == [jobs.FROZEN_WORKER_FLAG]
        # `-m` num executável congelado é ignorado pelo bootloader, e o binário
        # sobe a API inteira em vez do worker. É o defeito, não uma variação.
        assert '-m' not in args

    def test_the_entrypoint_agrees_with_the_flag_jobs_publishes(self):
        """`run.py` consome a sentinela; se os dois nomes divergirem, o binário
        volta a subir a API achando que é um lançamento normal."""
        from pathlib import Path

        run_py = (Path(__file__).resolve().parents[1] / 'run.py').read_text(encoding='utf-8')
        assert 'FROZEN_WORKER_FLAG' in run_py
        assert 'from app.jobs import' in run_py


class TestNoWindow:
    def test_hides_the_console_on_windows(self, monkeypatch):
        """Sem isto, cada subprocesso de console abre uma JANELA no app
        empacotado, que roda com `console=False`. O `icacls` de
        `create_private_dir()` roda a cada trabalho — era o terminal que piscava
        toda vez que o usuário processava algo."""
        monkeypatch.setattr('subprocess.CREATE_NO_WINDOW', 0x08000000, raising=False)
        assert security.no_window_kwargs() == {'creationflags': 0x08000000}

    def test_stays_out_of_the_way_where_the_flag_does_not_exist(self, monkeypatch):
        monkeypatch.delattr('subprocess.CREATE_NO_WINDOW', raising=False)
        assert security.no_window_kwargs() == {}


class TestSpeechInAPackagedApp:
    """A mensagem do Speech precisa dizer o que fazer, não o que faltou.

    A versão anterior citava o caminho de `resources/backend` e pedia o
    código-fonte "ao lado", depois sugeria `pip install`. Num app instalado a
    partir de um .exe isso descreve um cenário que o usuário não tem e um
    comando que ele não pode rodar: o bundle não tem pip nem `site-packages`
    gravável. Dizia a verdade sobre a causa e nada sobre a saída.
    """

    def test_says_it_is_not_installable_in_the_packaged_app(self, monkeypatch):
        from app import processing

        monkeypatch.setattr('sys.frozen', True, raising=False)
        with pytest.raises(processing.ComponentActionUnsupportedError) as erro:
            processing._check_audio_install_possible()

        mensagem = str(erro.value)
        assert 'versão instalada' in mensagem
        # Não pode citar o caminho interno do bundle: para quem instalou um
        # .exe, `resources/backend` não significa nada.
        assert 'resources' not in mensagem
        # Precisa apontar a saída real, e não só recusar.
        assert 'código-fonte' in mensagem

    def test_keeps_the_source_checkout_message_when_not_frozen(self, monkeypatch, tmp_path):
        from app import processing

        monkeypatch.delattr('sys.frozen', raising=False)
        monkeypatch.setattr(processing, '_REPO_ROOT', tmp_path)  # sem pyproject.toml
        with pytest.raises(processing.ComponentActionUnsupportedError) as erro:
            processing._check_audio_install_possible()

        assert 'código-fonte do eterzion_upscale ao lado' in str(erro.value)

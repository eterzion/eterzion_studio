"""Motor de voz: pesos verificados por nos, carregados do disco.

Ate' 2026-09-12 o motor de voz nunca tinha rodado com pesos reais. A primeira
execucao mostrou que o codigo gravava a tupla `(forma_de_onda, taxa)` que o
`upscale()` devolve como se fosse o audio -- todo processamento de voz teria
falhado mesmo com o pacote instalado.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from eterzion_upscale import processing
from eterzion_upscale.processing import SPEECH_WEIGHTS, SPEECH_WEIGHTS_DIR

ESPELHO = 'https://cdn.invalido/studio/models/'


def test_pesos_passam_pelo_espelho_com_revisao_e_hash_fixados(tmp_path, monkeypatch):
    pedidos = []

    def registra(urls, model_dir, file_name, sha256, progress):
        pedidos.append((urls, model_dir, file_name, sha256))
        return os.path.join(model_dir, file_name)

    monkeypatch.setattr(processing, 'download_with_fallback', registra)
    processing.set_mirror_url_factory(lambda nome: ESPELHO + nome)
    try:
        caminhos = processing.ensure_speech_weights(str(tmp_path))
    finally:
        processing.set_mirror_url_factory(None)

    assert set(caminhos) == set(SPEECH_WEIGHTS) == {'backbone.onnx', 'spec_head.onnx'}
    for urls, pasta, nome, digest in pedidos:
        assert urls[0] == ESPELHO + nome
        # A origem e' a revisao fixada do Hugging Face, nunca `main`.
        assert processing._LAVASR_REVISION in urls[1] and '/main/' not in urls[1]
        assert digest == SPEECH_WEIGHTS[nome]
        assert pasta == os.path.join(str(tmp_path), SPEECH_WEIGHTS_DIR)


def test_instalado_so_com_os_dois_pesos(tmp_path):
    assert not processing.speech_weights_installed(str(tmp_path))
    pasta = tmp_path / SPEECH_WEIGHTS_DIR
    pasta.mkdir()
    (pasta / 'backbone.onnx').write_bytes(b'x')
    assert not processing.speech_weights_installed(str(tmp_path))
    (pasta / 'spec_head.onnx').write_bytes(b'x')
    assert processing.speech_weights_installed(str(tmp_path))


def test_o_motor_carrega_exatamente_os_arquivos_verificados(tmp_path, monkeypatch):
    """O adaptador do audiosronnx buscaria os pesos pelo nome no Hugging Face.
    A subclasse troca isso pelos arquivos que o nosso downloader verificou --
    e depende de um metodo interno do pacote, por isso a versao e' fixada."""
    pytest.importorskip('audiosronnx')
    import onnxruntime as ort

    caminhos = {nome: str(tmp_path / nome) for nome in SPEECH_WEIGHTS}
    monkeypatch.setattr(processing, 'ensure_speech_weights', lambda model_dir: caminhos)
    abertos = []
    monkeypatch.setattr(ort, 'InferenceSession', lambda path, **kw: abertos.append(path) or object())

    motor = processing.load_speech_engine(str(tmp_path))
    motor._ensure_models()
    assert abertos == [caminhos['backbone.onnx'], caminhos['spec_head.onnx']]


def test_versao_do_audiosronnx_e_a_fixada():
    """Se alguem subir o pacote, este teste avisa que o `_ensure_models`
    sobrescrito precisa ser conferido contra a versao nova."""
    audiosronnx = pytest.importorskip('audiosronnx')
    from importlib.metadata import version

    assert version('audiosronnx') == '0.9.0a2', audiosronnx
    from audiosronnx.engines.lavasr import LavaSRAdapter

    assert hasattr(LavaSRAdapter, '_ensure_models')


def test_grava_a_forma_de_onda_e_a_taxa_nao_a_tupla(tmp_path, monkeypatch):
    """Regressao do defeito que a primeira execucao real revelou."""
    sf = pytest.importorskip('soundfile')
    onda = np.linspace(-0.5, 0.5, 4800, dtype=np.float32)

    class Motor:
        def upscale(self, _entrada):
            return onda, 48000

    monkeypatch.setattr(processing, 'load_speech_engine', lambda model_dir: Motor())
    saida = tmp_path / 'saida.wav'
    processing.enhance_speech_file('entrada.wav', str(saida), str(tmp_path))
    lido, taxa = sf.read(str(saida), dtype='float32')
    assert taxa == 48000
    assert np.allclose(lido, onda, atol=1e-4)


@pytest.mark.slow
def test_extensao_de_banda_real_com_os_pesos_do_espelho(tmp_path):
    """Ponta a ponta de verdade: baixa os ~56 MB do espelho, roda o motor numa
    fala sintetica de banda telefonica (8 kHz) e confere o que a extensao de
    banda tem que fazer -- 48 kHz, mesma duracao, energia nova acima de 4 kHz."""
    pytest.importorskip('audiosronnx')
    sf = pytest.importorskip('soundfile')
    taxa = 8000
    t = np.arange(taxa * 2) / taxa
    fala = (0.4 * np.sign(np.sin(2 * np.pi * 120 * t))).astype(np.float32)
    entrada = tmp_path / 'fala8k.wav'
    sf.write(str(entrada), fala, taxa)

    saida = tmp_path / 'fala48k.wav'
    processing.enhance_speech_file(str(entrada), str(saida), str(tmp_path / 'models'))
    y, taxa_saida = sf.read(str(saida), dtype='float32')

    assert taxa_saida == 48000
    assert abs(len(y) / taxa_saida - 2.0) < 0.05
    assert np.isfinite(y).all()
    espectro = np.abs(np.fft.rfft(y)) ** 2
    freqs = np.fft.rfftfreq(len(y), 1 / taxa_saida)
    assert espectro[freqs > 4000].sum() / espectro.sum() > 0.01

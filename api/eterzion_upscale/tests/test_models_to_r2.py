"""O script que espelha os modelos no CDN le a lista pela AST, sem importar
torch. Este teste confere que essa leitura bate com os valores que o app usa
de verdade -- senao o espelho ficaria sem um arquivo que o app pede, e o
download cairia na origem (ou, pior, com hash que o app recusaria)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse

from eterzion_upscale import processing

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'models_to_r2.py'


def _script():
    spec = importlib.util.spec_from_file_location('models_to_r2', SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_manifesto_bate_com_o_que_o_app_baixa():
    esperado = {os.path.basename(urlparse(u).path): (h, u)
                for e in processing.MODELS.values() for u, h in zip(e['urls'], e['sha256'])}
    esperado['face_detection_yunet_2023mar.onnx'] = (processing._YUNET_SHA256, processing._YUNET_URL)
    for nome, digest in processing.SPEECH_WEIGHTS.items():
        esperado[nome] = (digest, processing._LAVASR_ORIGIN + nome)

    obtido = {nome: (digest, url) for nome, digest, url in _script().manifesto()}
    assert obtido == esperado


def test_origem_da_voz_e_a_revisao_fixada():
    for nome, _, url in _script().manifesto():
        if nome in processing.SPEECH_WEIGHTS:
            assert processing._LAVASR_REVISION in url and '/main/' not in url

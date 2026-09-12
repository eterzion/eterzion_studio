"""Autoteste do executável empacotado: as partes nativas carregam de verdade?

Três vezes o instalador saiu com o build verde e uma extensão nativa faltando,
porque o PyInstaller só enxerga `import` em Python e uma dependência carregada
por dentro do código C passa despercebida:

- 1.0.4/1.0.5 — `torchvision._C` (`_C_stable.pyd`): o backend morria no import;
- 1.1.2 — `scipy._cyutility`: nenhuma extensão do scipy carregava, e a voz
  falhava com "The `scipy` install you are using seems to be broken".

Guardas por arquivo pegam só o defeito que já aconteceu. Esta pega a classe:
roda DENTRO do executável congelado e exercita cada parte nativa com uma chamada
mínima — importar não basta, o `torchvision` importava sem os operadores.

O executável é empacotado sem console (`console=False`), então `print` não vai
a lugar nenhum: o resultado sai num arquivo JSON e no código de saída.
"""
from __future__ import annotations

import json
import traceback
from collections.abc import Callable


def _torchvision() -> str:
    import torch
    import torchvision

    # O operador nativo, e nao so' o import: foi assim que a 1.0.4 enganou.
    caixas = torch.tensor([[0.0, 0.0, 1.0, 1.0], [0.0, 0.0, 1.0, 1.0]])
    torchvision.ops.nms(caixas, torch.tensor([0.9, 0.8]), 0.5)
    return torchvision.__version__


def _scipy() -> str:
    import numpy as np
    import scipy
    from scipy.signal import resample_poly

    resample_poly(np.ones(64, dtype=np.float32), 6, 1)
    return scipy.__version__


def _onnxruntime() -> str:
    import onnxruntime as ort

    provedores = ort.get_available_providers()
    if 'CPUExecutionProvider' not in provedores:
        raise RuntimeError(f'sem CPUExecutionProvider: {provedores}')
    return ort.__version__


def _audiosronnx() -> str:
    """O DSP que o motor de voz roda antes e depois do ONNX, com as funcoes
    dele: reamostragem, STFT/ISTFT e a costura espectral -- tudo scipy.signal.
    O `resample_poly` sozinho ja' pegou o `array_api_compat` ausente, mas o
    motor tambem passa por STFT/ISTFT, outro caminho do scipy; o que ele usa
    de verdade e' o que precisa carregar."""
    import numpy as np
    from audiosronnx.engines import lavasr

    x = (np.sin(np.arange(16000) / 7.0) * 0.1).astype(np.float32)
    x48 = lavasr._resample(x, 16000, 48000)
    espectro = lavasr._stft(x, 16000, 512, 128)
    lavasr._istft(espectro, 16000, 512, 128, target_len=len(x))
    lavasr._spectral_merge(x48, x48, 48000, 4000.0, 8)
    lavasr._build_mel_filterbank(24000, 1024, 80, 0.0, 8000.0)
    return lavasr.LavaSRAdapter.__name__


def _opencv() -> str:
    import cv2
    import numpy as np

    ok, _ = cv2.imencode('.png', np.zeros((4, 4, 3), dtype=np.uint8))
    if not ok:
        raise RuntimeError('cv2.imencode falhou')
    return cv2.__version__


def _soundfile() -> str:
    import soundfile

    if 'WAV' not in soundfile.available_formats():
        raise RuntimeError('soundfile sem WAV')
    return soundfile.__version__


VERIFICACOES: dict[str, Callable[[], str]] = {
    'torchvision': _torchvision,
    'scipy': _scipy,
    'onnxruntime': _onnxruntime,
    'audiosronnx': _audiosronnx,
    'opencv': _opencv,
    'soundfile': _soundfile,
}


def run(caminho_relatorio: str | None = None) -> bool:
    """Roda todas as verificacoes; grava o relatorio em JSON se pedido."""
    relatorio: dict[str, dict[str, str]] = {}
    for nome, verificar in VERIFICACOES.items():
        try:
            relatorio[nome] = {'ok': 'sim', 'versao': verificar()}
        except Exception as erro:  # noqa: BLE001 - o relatorio e' o produto
            relatorio[nome] = {'ok': 'nao', 'erro': f'{type(erro).__name__}: {erro}',
                               'traceback': traceback.format_exc()[-2000:]}
    tudo_ok = all(item['ok'] == 'sim' for item in relatorio.values())
    if caminho_relatorio:
        with open(caminho_relatorio, 'w', encoding='utf-8') as arquivo:
            json.dump({'ok': tudo_ok, 'verificacoes': relatorio}, arquivo, ensure_ascii=False, indent=2)
    return tudo_ok

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


api_dir = Path(SPECPATH).resolve()
api_root = api_dir.parent
sys.path[:0] = [str(api_dir), str(api_root)]

protected_sources = [
    (str(api_dir / 'app' / filename), 'app')
    for filename in ('processing.py', 'jobs.py', 'security.py', 'integrity_manifest.json')
]

datas = protected_sources + [
    (str(api_dir / 'vendor' / 'sonicmaster'), 'vendor/sonicmaster'),
]

# As extensoes nativas do torchvision, coletadas POR DIRETORIO e nao por nome.
#
# O hook que vem com o PyInstaller pede `torchvision._C` e `torchvision.image`
# como hidden imports. Na 0.29.0 esses arquivos passaram a se chamar
# `_C_stable.pyd` e `image_stable.pyd`, entao o hook nao os encontra -- ele
# avisa "Hidden import not found" e o build segue. O bundle sai sem a extensao,
# os operadores nunca se registram, e o backend morre no import com
# "RuntimeError: operator torchvision::nms does not exist". Foi o que aconteceu
# nas versoes 1.0.4 e 1.0.5: o app instalava, abria e travava na tela de
# licenca, porque o backend local nunca chegava a escutar.
#
# `collect_dynamic_libs` varre o diretorio do pacote por nome de arquivo, entao
# sobrevive ao rename. Mas `search_patterns` PRECISA ser explicito: o padrao e
# ['*.dll', '*.dylib', 'lib*.so'] e NAO inclui `*.pyd` -- que e justamente a
# extensao dos modulos compilados do Python no Windows. Sem isso o bundle sai
# com as DLLs de imagem e sem `_C_stable.pyd`, que e' o arquivo que registra os
# operadores; medido num build real antes de acertar.
#
# No Linux as mesmas extensoes sao `.so` (inclusive os modulos do Python, como
# `_C_stable.cpython-312-x86_64-linux-gnu.so`), e o padrao `lib*.so` do
# PyInstaller perderia justamente essas.
_NATIVOS = ['*.dll', '*.pyd'] if sys.platform == 'win32' else ['*.so', '*.so.*']
binaries = collect_dynamic_libs('torchvision', search_patterns=_NATIVOS)
# Mesmo motivo para o onnxruntime, que o motor de voz usa: a extensao
# `onnxruntime_pybind11_state.pyd` fica ao lado de `onnxruntime.dll` e
# `onnxruntime_providers_shared.dll`, e sem ela o import do onnxruntime falha.
binaries += collect_dynamic_libs('onnxruntime', search_patterns=_NATIVOS)

# UPX so' no Windows: no Linux ele comprime as .so do torch e as quebra no load
# (problema conhecido do PyInstaller com bibliotecas grandes).
_UPX = sys.platform == 'win32'

hiddenimports = sorted(set(
    collect_submodules('app')
    + collect_submodules('eterzion_upscale')
    + collect_submodules('fastapi')
    + collect_submodules('pydantic')
    + collect_submodules('pydantic_settings')
    + collect_submodules('spandrel')
    + collect_submodules('uvicorn')
    # `audiosronnx` e' importado dentro de funcao (so' quando a voz roda), e os
    # adaptadores de motor se registram por import do subpacote `engines`.
    + collect_submodules('audiosronnx')
    + collect_submodules('onnxruntime')
    # O scipy recente compila o utilitario comum do Cython num modulo proprio,
    # `scipy._cyutility`, que as outras extensoes carregam por dentro do codigo
    # C -- o PyInstaller nao ve esse import e deixava o .pyd de fora. Sem ele,
    # NENHUMA extensao do scipy carrega, e a voz falhava na 1.1.2 com "The
    # `scipy` install you are using seems to be broken".
    #
    # E nao era so' ele: com o `_cyutility` no pacote, o autoteste do build
    # parou em `scipy._external.array_api_compat.numpy.fft`, que o scipy importa
    # montando o nome em tempo de execucao. Adivinhar modulo por modulo perde a
    # proxima ocorrencia; o scipy vai inteiro, menos os testes dele.
    + ['scipy._cyutility']
    + collect_submodules('scipy', filter=lambda nome: '.tests' not in nome and not nome.endswith('.conftest'))
    # A coleta a partir de `scipy` perde a subarvore `_external` inteira: ela
    # tropeca nos adaptadores de cupy/dask (nao instalados) e desiste do resto.
    # Pedida direto, ela vem -- inclusive o `numpy.fft` que faltou.
    + collect_submodules('scipy._external', filter=lambda nome: '.tests' not in nome)
))

a = Analysis(
    ['run.py'],
    pathex=[str(api_dir), str(api_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'setuptools', 'tkinter'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='eterzion-studio-api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=_UPX,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=_UPX,
    upx_exclude=[],
    name='eterzion-studio-api',
)

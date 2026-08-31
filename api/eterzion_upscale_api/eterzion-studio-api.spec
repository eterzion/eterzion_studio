from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


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

hiddenimports = sorted(set(
    collect_submodules('app')
    + collect_submodules('eterzion_upscale')
    + collect_submodules('fastapi')
    + collect_submodules('pydantic')
    + collect_submodules('pydantic_settings')
    + collect_submodules('spandrel')
    + collect_submodules('uvicorn')
))

a = Analysis(
    ['run.py'],
    pathex=[str(api_dir), str(api_root)],
    binaries=[],
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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='eterzion-studio-api',
)

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path(SPECPATH).resolve()
sys.path.insert(0, str(project_root))

datas = []
hiddenimports = []

for package_name in [
    'api',
    'analyzer',
    'collector',
    'sentiment_monitor',
    'akshare',
    'rest_framework',
    'corsheaders',
    'django_apscheduler',
    'snownlp',
    'bs4',
    'lxml',
    'playwright',
]:
    datas += collect_data_files(package_name, include_py_files=True)
    hiddenimports += collect_submodules(package_name)


a = Analysis(
    ['desktop_backend.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SentimentMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='SentimentMonitor-runtime',
)

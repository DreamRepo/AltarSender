# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

# Find customtkinter path dynamically
import customtkinter
customtkinter_path = os.path.dirname(customtkinter.__file__)

datas = [(customtkinter_path, 'customtkinter')]
binaries = []
hiddenimports = [
    'customtkinter',
    'sacred',
    'sacred.observers',
    'pymongo',
    'pandas',
    'numpy',
    'openpyxl',
    'boto3',
    'botocore',
    'minio',
    'PIL',
    'PIL._tkinter_finder',
    'keyring',
    'keyring.backends',
]

# Collect all data for these packages
for package in ['customtkinter', 'sacred']:
    tmp_ret = collect_all(package)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AltarSender',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

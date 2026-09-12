# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['psycopg2', 'sqlalchemy.dialects.postgresql.psycopg2', 'pyodbc', 'sqlalchemy.dialects.mssql.pyodbc']
hiddenimports += collect_submodules('sqlalchemy')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/app.ico', 'assets'), ('assets/seed.sqlite', 'assets'), ('config.example.json', '.')],
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
    [],
    exclude_binaries=True,
    name='ITServiceLog',
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
    icon=['assets/app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ITServiceLog',
)

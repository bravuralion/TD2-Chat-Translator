# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

# py3langid laedt sein trainiertes Sprachmodell zur Laufzeit aus einer
# eigenen Datei (py3langid/data/model.plzma) relativ zu seinem eigenen
# __file__ - das ist KEIN Python-Code und wird von PyInstaller deshalb nicht
# automatisch mitgebuendelt. collect_data_files() findet diese Datei im
# lokalen site-packages und packt sie mit dem richtigen relativen Pfad ins
# Bundle, damit py3langid sie im gebauten .exe wiederfindet.
py3langid_datas = collect_data_files('py3langid')

a = Analysis(
    ['TD2-Translator.py'],
    pathex=[],
    binaries=[],
    datas=[('res/*.png', 'res/'), ('res/*.ico', 'res/'), ('res/*.wav', 'res/'), ('res/*.csv', 'res/')] + py3langid_datas,
    hiddenimports=['py3langid'],
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
    a.binaries,
    a.datas,
    [],
    name='TD2-Translator',
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
    icon=['res\\Favicon.ico'],
)

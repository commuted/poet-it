# PyInstaller spec for Poetit — Windows standalone build
# Run from the project root:
#   pip install pyinstaller
#   pyinstaller packaging/windows/poetit.spec
#
# Output: dist/Poetit/Poetit.exe  (folder distribution)

import sys
from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH).parent.parent   # project root

a = Analysis(
    [str(ROOT / 'poetit' / '__main__.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # about.txt now lives in poetit/data and ships with the line below.
        (str(ROOT / 'poetit' / 'data'),  'poetit/data'),
        (str(ROOT / 'qr-code.png'),       '.'),
        (str(ROOT / 'LICENSE'),           '.'),
        (str(ROOT / 'NOTICE'),            '.'),
    ],
    hiddenimports=[
        # tkinter is not always auto-detected on Windows
        'tkinter',
        'tkinter.ttk',
        'tkinter.font',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        # nltk internals
        'nltk.corpus',
        'nltk.corpus.cmudict',
        'nltk.tokenize',
        # prosodic
        'prosodic',
        # stanza
        'stanza',
        # spellchecker
        'spellchecker',
        # dulwich VCS
        'dulwich',
        'dulwich.repo',
        'dulwich.porcelain',
        # imaging
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        # resvg (SVG renderer)
        'resvg_py',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Poetit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window — GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # add a .ico path here when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Poetit',
)

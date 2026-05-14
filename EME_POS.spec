# EME_POS.spec
# PyInstaller spec file for Ethan's Music Essentials POS
#
# Build command (run from inside your project folder):
#   pyinstaller EME_POS.spec
#
# NOTE: Place this .spec file inside the root of your project folder,
# alongside main.py, before running the build command.

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle ALL assets (icons + product images)
        ('assets/icons/*.ico',       'assets/icons'),
        ('assets/prod_images/*.jpg', 'assets/prod_images'),

        # Bundle the SQLite database
        ('eme.db', '.'),

        # Bundle the receipts folder (preserves existing receipts)
        ('receipts',                 'receipts'),
    ],
    hiddenimports=[
        # Pillow image formats used by image_utils.py
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',

        # SQLite is built into Python but explicitly listed for safety
        'sqlite3',
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
    a.binaries,
    a.datas,
    [],
    name='EME_POS',                          # Output .exe filename
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                                # Compress the exe (requires UPX)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                           # No black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/main_icon.ico',       # App icon
)

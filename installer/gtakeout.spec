# PyInstaller spec for building a single-file executable
# Run: pyinstaller installer/gtakeout.spec

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules
hiddenimports = collect_submodules('gtakeout')

a = Analysis(['-m','gtakeout.ui'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='gTakeOutThis',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='gTakeOutThis')

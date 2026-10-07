# PyInstaller spec for the Firmware Integrity Monitor dashboard.
#
# Same spec file builds correctly on both Linux and Windows - PyInstaller
# produces the right output format (ELF binary vs .exe) for whichever OS
# it's actually run on. There is no cross-compilation here: running this
# on Linux produces a Linux executable, running it on Windows produces a
# Windows one. You cannot get a .exe by running this on Linux.
#
# Usage (from the dashboard/ directory):
#   pyinstaller packaging/dashboard.spec
#
# Output lands in dist/FirmwareIntegrityMonitor/

import sys
from pathlib import Path

block_cipher = None

# Resolve paths relative to this spec file, not the current working
# directory, so `pyinstaller packaging/dashboard.spec` works the same
# regardless of where it's invoked from.
SPEC_DIR = Path(SPECPATH)
PROJECT_ROOT = SPEC_DIR.parent

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # theme.qss must ship alongside the executable - see main.py's
        # sys._MEIPASS handling, which is what actually finds this at
        # runtime once frozen.
        (str(PROJECT_ROOT / "app" / "resources" / "theme.qss"), "app/resources"),
    ],
    hiddenimports=[
        # PyInstaller's static import analysis doesn't always catch
        # PySide6's plugin-loading machinery - listing these explicitly
        # avoids a "could not load Qt platform plugin" failure that would
        # otherwise only show up at runtime on a clean machine, not during
        # the build itself.
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "serial",
        "serial.tools.list_ports",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly excluded even though PySide6-Essentials doesn't
        # install them anyway (see requirements.txt) - belt and suspenders
        # against PyInstaller's analysis pulling in something unused and
        # bloating the build.
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtMultimedia",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ICON_PATH picks .ico on Windows (the only format Windows executables
# accept) and .png elsewhere (Linux doesn't embed an icon into the binary
# itself the way Windows does - this mainly matters for desktop shortcuts,
# see PACKAGING.md).
_icon_dir = PROJECT_ROOT / "packaging" / "icon"
ICON_PATH = str(_icon_dir / "app.ico") if sys.platform == "win32" else str(_icon_dir / "app.png")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FirmwareIntegrityMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX compression saves space but occasionally triggers
                # false-positive antivirus flags on Windows - not worth it
                # for a first build; revisit if size becomes a real problem.
    console=False,  # GUI app - no console window behind it
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FirmwareIntegrityMonitor",
)

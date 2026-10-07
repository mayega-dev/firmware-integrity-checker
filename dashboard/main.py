from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow

# When PyInstaller bundles this into an executable, __file__-relative paths
# stop working the way they do running from source - bundled data files get
# extracted to a temp dir PyInstaller exposes as sys._MEIPASS instead. This
# picks the right base dir either way, so theme.qss loads correctly whether
# you're running `python main.py` or the packaged .exe/binary.
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    _BASE_DIR = Path(__file__).parent

THEME_PATH = _BASE_DIR / "app" / "resources" / "theme.qss"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Firmware Integrity Monitor")
    app.setOrganizationName("UTAMU Firmware Integrity Checker")

    if THEME_PATH.exists():
        app.setStyleSheet(THEME_PATH.read_text(encoding="utf-8"))
    else:
        # Fail visibly rather than silently running unstyled - if this ever
        # fires, it means the packaging step didn't bundle resources
        # correctly, and that's worth knowing immediately, not discovering
        # later as "why does this look wrong".
        print(f"Warning: theme not found at {THEME_PATH} - running unstyled.", file=sys.stderr)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

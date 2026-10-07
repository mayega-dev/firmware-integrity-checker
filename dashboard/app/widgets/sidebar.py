from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QWidget, QButtonGroup

NAV_ITEMS = [
    ("dashboard", "☷  Dashboard"),
    ("log", "≡  Alert Log"),
    ("console", "⌘  Device Console"),
    ("settings", "⚙  Settings"),
    ("docs", "📖  Documentation"),
]


class Sidebar(QWidget):
    """
    Professional bottom navigation bar featuring a horizontal layout, active pill
    states, and a live LED connection signal indicator.
    """

    page_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bottomNavbar")
        self.setFixedHeight(64)
        self.setStyleSheet("""
            QWidget#bottomNavbar {
                background-color: #0B0F19;
                border-top: 1px solid #1E293B;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(12)

        # ── Navigation Buttons Group ─────────────────────────────────────────
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton#navButton {
                    background: transparent;
                    color: #94A3B8;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton#navButton:hover {
                    background: #1E293B;
                    color: #F1F5F9;
                }
                QPushButton#navButton:checked {
                    background: #6366F1;
                    color: #FFFFFF;
                    font-weight: 700;
                }
            """)
            btn.clicked.connect(lambda _checked, k=key: self.page_changed.emit(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            nav_layout.addWidget(btn)

        layout.addWidget(nav_container)
        layout.addStretch(1)

        # ── Connection Status LED Signal Pill ────────────────────────────────
        self.conn_pill = QLabel("●  DISCONNECTED")
        self.conn_pill.setAlignment(Qt.AlignCenter)
        self.conn_pill.setStyleSheet("""
            QLabel {
                background: #1E293B;
                color: #EF4444;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
        """)
        layout.addWidget(self.conn_pill)

        self.set_active("dashboard")

    def set_active(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def set_connection_state(self, state: str) -> None:
        """state: 'connected' | 'disconnected' | 'error'"""
        mapping = {
            "connected": ("●  CONNECTED", "#10B981"),
            "disconnected": ("●  DISCONNECTED", "#EF4444"),
            "error": ("●  LINK ERROR", "#F59E0B"),
        }
        text, color = mapping.get(state, mapping["disconnected"])
        self.conn_pill.setText(text)
        self.conn_pill.setStyleSheet(f"""
            QLabel {{
                background: #1E293B;
                color: {color};
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)
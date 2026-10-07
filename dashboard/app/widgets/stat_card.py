from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QStyle, QStyleOption, QVBoxLayout


class StatCard(QFrame):
    """
    A clean, professional metric tile showcasing key telemetry indicators,
    full hash values, and dynamic status tinting for critical warnings.
    """

    def __init__(self, title: str, value: str = "--", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            StatCard {
                background-color: #0B0F19;
                border: 1px solid #1E293B;
                border-radius: 10px;
            }
        """)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        self._title_label = QLabel(title.upper())
        self._title_label.setStyleSheet("""
            color: #94A3B8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)

        self._value_label = QLabel(value)
        self._value_label.setWordWrap(True)
        self._value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._value_label.setToolTip(value)
        self._value_label.setStyleSheet("""
            color: #F8FAFC;
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        layout.addStretch(1)

    def paintEvent(self, event):  # noqa: N802
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)
        super().paintEvent(event)

    def set_value(self, value: str) -> None:
        """Sets the card value and updates hover tooltip for long hash string inspection."""
        self._value_label.setText(value)
        self._value_label.setToolTip(value)

    def set_value_color(self, hex_color: str) -> None:
        """Dynamically tints metric text (e.g. green for secure, red for tamper alert)."""
        self._value_label.setStyleSheet(f"""
            color: {hex_color};
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
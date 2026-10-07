from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame

from app.models import Severity

_SEVERITY_COLORS = {
    Severity.INFO: QColor("#10B981"),
    Severity.WARNING: QColor("#F59E0B"),
    Severity.CRITICAL: QColor("#EF4444"),
    Severity.UNKNOWN: QColor("#64748B"),
}


class IntegrityTimeline(QFrame):
    """
    Sparkline timeline rendering recent hash check history points and severity levels.
    """

    def __init__(self, max_points: int = 50, parent=None):
        super().__init__(parent)
        self._max_points = max_points
        self._points: deque[Severity] = deque(maxlen=max_points)
        self.setFixedHeight(80)
        self.setStyleSheet("""
            QFrame {
                background-color: #0B0F19;
                border: 1px solid #1E293B;
                border-radius: 8px;
            }
        """)

    def add_point(self, severity: Severity) -> None:
        self._points.append(severity)
        self.update()

    def clear(self) -> None:
        self._points.clear()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            pad = 12

            if not self._points:
                painter.setPen(QPen(QColor("#334155"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(pad, h // 2, w - pad, h // 2)
                return

            n = len(self._points)
            step_x = (w - 2 * pad) / max(n - 1, 1) if n > 1 else 0

            # Y levels corresponding to severity status
            y_map = {
                Severity.INFO: h - pad - 10,
                Severity.WARNING: h // 2,
                Severity.CRITICAL: pad + 10,
                Severity.UNKNOWN: h - pad - 10,
            }

            pts: list[QPointF] = []
            for i, sev in enumerate(self._points):
                x = pad + i * step_x if n > 1 else w / 2
                y = y_map.get(sev, h // 2)
                pts.append(QPointF(x, y))

            # Draw connecting lines
            pen = QPen(QColor("#334155"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])

            # Draw event nodes with full QColor handling
            for i, (pt, sev) in enumerate(zip(pts, self._points)):
                base_color = _SEVERITY_COLORS.get(sev, QColor("#64748B"))

                gradient = QLinearGradient(pt.x(), pt.y() - 6, pt.x(), pt.y() + 6)
                gradient.setColorAt(0.0, base_color.lighter(125))
                gradient.setColorAt(1.0, base_color)

                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(base_color.lighter(150), 1))
                painter.drawEllipse(pt, 5, 5)

        finally:
            painter.end()
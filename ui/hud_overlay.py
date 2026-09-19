from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QBrush

class TacticalOverlayHUD(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.telem = {
            "connected": False,
            "mode": "DISARMED",
            "sub_mode": "STANDBY",
            "voltage": 0.0,
            "sats": 0,
            "hdop": 99.9,
            "alt": 0.0,
            "speed": 0.0,
            "flight_time": "00:00",
            "home_dist": 0.0,
            "compass": 0.0,
            "temp": 0.00
        }

    def update_telemetry(self, t):
        self.telem.update(t)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        # 1. Clean Center Reticle
        painter.setPen(QPen(QColor(255, 255, 255, 160), 1.5))
        painter.drawLine(cx - 22, cy, cx - 6, cy)
        painter.drawLine(cx + 6, cy, cx + 22, cy)
        painter.drawLine(cx, cy - 22, cx, cy - 6)
        painter.drawLine(cx, cy + 6, cx, cy + 22)

        # 2. Skydroid / QGC Primary Flight Display Compass
        cluster_y = h - 90
        compass_center = QPoint(cx, cluster_y)

        # Translucent Dial Ring
        painter.setBrush(QBrush(QColor(10, 15, 22, 195)))
        painter.setPen(QPen(QColor(0, 229, 255, 160), 1.5))
        painter.drawEllipse(compass_center, 46, 46)

        # Cardinal Points
        f_card = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(f_card)
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(cx - 4, cluster_y - 32, "N")
        painter.drawText(cx - 4, cluster_y + 42, "S")
        painter.drawText(cx - 42, cluster_y + 4, "W")
        painter.drawText(cx + 33, cluster_y + 4, "E")

        # Compass Tick Degree Numbers
        f_tick = QFont("Consolas", 7)
        painter.setFont(f_tick)
        painter.setPen(QColor(148, 163, 184, 180))
        painter.drawText(cx - 38, cluster_y - 20, "300")
        painter.drawText(cx + 19, cluster_y - 20, "60")
        painter.drawText(cx - 38, cluster_y + 26, "240")
        painter.drawText(cx + 19, cluster_y + 26, "120")

        # Dynamic Heading Needle
        heading_deg = float(self.telem.get("compass", 0.0)) % 360.0
        painter.save()
        painter.translate(compass_center)
        painter.rotate(heading_deg)
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(QBrush(QColor(0, 255, 204, 240)))
        arrow = QPolygonF([QPoint(0, -25), QPoint(7, -8), QPoint(-7, -8)])
        painter.drawPolygon(arrow)
        painter.restore()

        # Digital Heading Display (e.g. "018°")
        f_num = QFont("Consolas", 12, QFont.Bold)
        painter.setFont(f_num)
        painter.setPen(QColor(0, 255, 204))
        painter.drawText(QRectF(cx - 30, cluster_y - 10, 60, 20), Qt.AlignCenter, f"{int(heading_deg):03d}°")

        # Top Triangle Reference Indicator
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        top_pointer = QPolygonF([QPoint(cx, cluster_y - 50), QPoint(cx - 5, cluster_y - 44), QPoint(cx + 5, cluster_y - 44)])
        painter.drawPolygon(top_pointer)

        # Left Metrics: Speed and Timer
        lx = cx - 180
        f_metric = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(f_metric)
        painter.setPen(QColor(255, 255, 255))

        g_speed = float(self.telem.get("speed", 0.0))
        painter.drawText(lx, cluster_y - 32, f"g:{g_speed:.1f}m/s")
        painter.drawText(lx, cluster_y - 14, f"a:{g_speed:.1f}m/s")

        timer_str = str(self.telem.get("flight_time", "00:00"))
        painter.drawText(lx + 10, cluster_y + 8, f"{timer_str}")
        painter.drawText(lx - 12, cluster_y + 26, f"0%  ◎ {g_speed:.1f}m/s")

        f_icon = QFont("Segoe UI", 9)
        painter.setFont(f_icon)
        painter.drawText(lx - 20, cluster_y - 32, "🏠")
        painter.drawText(lx - 20, cluster_y - 14, "⏱")
        painter.drawText(lx + 68, cluster_y + 8, "✈")

        # Right Metrics: Temp, Dist, Alt, Sats
        rx = cx + 65
        painter.setFont(f_metric)
        painter.setPen(QColor(255, 255, 255))

        temp_val = float(self.telem.get("temp", 0.0))
        alt_val = float(self.telem.get("alt", 0.0))
        dist_val = float(self.telem.get("home_dist", 0.0))
        sats = int(self.telem.get("sats", 0))

        painter.drawText(rx, cluster_y - 32, f"🌡 {temp_val:.2f}°C")
        painter.drawText(rx, cluster_y - 14, f"⌂  {dist_val:.1f}m  0.0m/s")
        painter.drawText(rx, cluster_y + 6,  f"▲  {alt_val:.1f}m   0.0")
        painter.drawText(rx, cluster_y + 26, f"🛰  {sats}  100.0")
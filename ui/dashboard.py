from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class TelemetryChip(QFrame):
    def __init__(self, title, default_val="--", unit=""):
        super().__init__()
        self.unit = unit
        self.setStyleSheet("""
            QFrame {
                background-color: #0e1318;
                border: 1px solid #1c242f;
                border-radius: 3px;
                padding: 1px 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet("color: #64748b; font-size: 8px; font-weight: 700; letter-spacing: 0.5px;")
        
        self.val_lbl = QLabel(f"{default_val} {self.unit}".strip())
        self.val_lbl.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; font-family: 'Consolas', monospace;")

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.val_lbl)

    def set_value(self, value, color="#00ffcc"):
        self.val_lbl.setText(f"{value} {self.unit}".strip())
        self.val_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; font-family: 'Consolas', monospace;")


class TacticalDashboard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #080b0e;
                border: 1px solid #161e27;
                border-radius: 4px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.chip_cam = TelemetryChip("Cam Feed", "OFF")
        self.chip_mode = TelemetryChip("Mode", "STANDBY")
        self.chip_volt = TelemetryChip("Battery", "--", "V")
        self.chip_sats = TelemetryChip("GPS", "0", "sats")
        self.chip_alt = TelemetryChip("Alt", "0.0", "m")
        self.chip_time = TelemetryChip("Duration", "00:00")
        self.chip_home = TelemetryChip("Home Dist", "0.0", "m")
        self.chip_compass = TelemetryChip("Heading", "0.0", "°")

        for c in [self.chip_cam, self.chip_mode, self.chip_volt, self.chip_sats,
                  self.chip_alt, self.chip_time, self.chip_home, self.chip_compass]:
            layout.addWidget(c)

    def update_telemetry(self, t):
        self.chip_mode.set_value(t.get('mode', 'UNKNOWN'), "#38bdf8")
        self.chip_volt.set_value(f"{t.get('voltage', 0.0):.1f}")
        self.chip_sats.set_value(f"{t.get('sats', 0)}")
        self.chip_alt.set_value(f"{t.get('alt', 0.0):.1f}")
        self.chip_time.set_value(f"{t.get('flight_time', '00:00')}")
        self.chip_home.set_value(f"{t.get('home_dist', 0.0):.1f}")
        self.chip_compass.set_value(f"{t.get('compass', 0.0):.1f}")

    def update_cam_status(self, connected: bool):
        if connected:
            self.chip_cam.set_value("LIVE", "#00ffcc")
        else:
            self.chip_cam.set_value("OFF", "#ef4444")
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QRadioButton, QButtonGroup, QMessageBox
)
from PySide6.QtCore import Qt, Signal

class CoordinateGotoDialog(QDialog):
    coordinate_selected = Signal(float, float, str, float)  # lat, lon, mgrs_str, alt

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plot Location / Waypoint Coordinate")
        self.setFixedSize(380, 240)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b1118;
                border: 2px solid #0284c7;
                border-radius: 8px;
            }
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 8.5pt;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #030712;
                border: 1px solid #334155;
                color: #facc15;
                font-family: 'Consolas', monospace;
                font-size: 9pt;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton#btn_plot {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
                color: white;
                font-weight: bold;
                font-size: 9pt;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton#btn_plot:hover {
                background-color: #0369a1;
            }
            QPushButton#btn_cancel {
                background-color: #1e293b;
                border: 1px solid #475569;
                color: #cbd5e1;
                font-weight: bold;
                font-size: 9pt;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton#btn_cancel:hover {
                background-color: #334155;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title Label
        self.lbl_title = QLabel("📍 Enter Target or Waypoint Coordinate:")
        self.lbl_title.setStyleSheet("color: #38bdf8; font-size: 9.5pt;")
        layout.addWidget(self.lbl_title)

        # Lat / Long Inputs
        row1 = QHBoxLayout()
        lbl_lat = QLabel("Latitude:")
        lbl_lat.setFixedWidth(65)
        self.txt_lat = QLineEdit()
        self.txt_lat.setPlaceholderText("e.g. 21.145800")
        row1.addWidget(lbl_lat)
        row1.addWidget(self.txt_lat)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_lon = QLabel("Longitude:")
        lbl_lon.setFixedWidth(65)
        self.txt_lon = QLineEdit()
        self.txt_lon.setPlaceholderText("e.g. 79.088200")
        row2.addWidget(lbl_lon)
        row2.addWidget(self.txt_lon)
        layout.addLayout(row2)

        # Altitude Input (for waypoints)
        row3 = QHBoxLayout()
        lbl_alt = QLabel("Altitude (m):")
        lbl_alt.setFixedWidth(65)
        self.txt_alt = QLineEdit("30.0")
        self.txt_alt.setPlaceholderText("Altitude in meters")
        row3.addWidget(lbl_alt)
        row3.addWidget(self.txt_alt)
        layout.addLayout(row3)

        layout.addSpacing(6)

        # Action Buttons
        btn_box = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_plot = QPushButton("📍 Plot / Add Point")
        self.btn_plot.setObjectName("btn_plot")
        self.btn_plot.clicked.connect(self.process_coordinate)
        btn_box.addWidget(self.btn_plot)

        layout.addLayout(btn_box)

    def set_mode_hint(self, is_plan_mode: bool):
        if is_plan_mode:
            self.lbl_title.setText("📍 Enter Coordinate to Add Waypoint:")
            self.btn_plot.setText("➕ Add to Mission")
        else:
            self.lbl_title.setText("📍 Inspect / Pan to Coordinate:")
            self.btn_plot.setText("📍 Pan & Inspect")

    def process_coordinate(self):
        lat_s = self.txt_lat.text().strip()
        lon_s = self.txt_lon.text().strip()
        alt_s = self.txt_alt.text().strip()

        try:
            lat = float(lat_s)
            lon = float(lon_s)
            alt = float(alt_s) if alt_s else 30.0
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values for Latitude and Longitude.")
            return

        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            QMessageBox.warning(self, "Out of Range", "Latitude must be between -90 and 90. Longitude between -180 and 180.")
            return

        self.coordinate_selected.emit(lat, lon, f"{lat:.6f}, {lon:.6f}", alt)
        self.accept()
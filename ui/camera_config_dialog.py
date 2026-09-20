import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import Signal, Qt

CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "camera_config.json"))

class CameraConfigDialog(QDialog):
    config_saved = Signal(str, str)  # day_url, thermal_url

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gimbal Dual Camera Feed Setup")
        self.setFixedSize(460, 260)
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
                color: #00ffcc;
                font-family: 'Consolas', monospace;
                font-size: 8.5pt;
                padding: 6px 8px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPushButton#btn_save {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
                color: white;
                font-weight: bold;
                font-size: 9pt;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton#btn_save:hover { background-color: #0369a1; }
            QPushButton#btn_cancel {
                background-color: #1e293b;
                border: 1px solid #475569;
                color: #cbd5e1;
                font-weight: bold;
                font-size: 9pt;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton#btn_cancel:hover { background-color: #334155; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        lbl_title = QLabel("Dual Stream Sensor Configuration")
        lbl_title.setStyleSheet("color: #38bdf8; font-size: 10.5pt; font-weight: bold;")
        layout.addWidget(lbl_title)

        # Day (EO) Feed
        layout.addWidget(QLabel("Day (EO / Visual) RTSP Stream URL:"))
        self.txt_day = QLineEdit()
        self.txt_day.setPlaceholderText("rtsp://192.168.144.25:8554/main.264")
        layout.addWidget(self.txt_day)

        # Thermal (IR) Feed
        layout.addWidget(QLabel("Thermal (IR / Infrared) RTSP Stream URL:"))
        self.txt_thermal = QLineEdit()
        self.txt_thermal.setPlaceholderText("rtsp://192.168.144.25:8554/thermal.264")
        layout.addWidget(self.txt_thermal)

        layout.addStretch()

        # Buttons
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btn_cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save & Connect")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self.handle_save)
        btn_box.addWidget(btn_save)

        layout.addLayout(btn_box)

        self.load_saved_config()

    def load_saved_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.txt_day.setText(data.get("day_url", ""))
                    self.txt_thermal.setText(data.get("thermal_url", ""))
            except Exception:
                pass

    def handle_save(self):
        day_url = self.txt_day.text().strip()
        thermal_url = self.txt_thermal.text().strip()

        if not day_url and not thermal_url:
            QMessageBox.warning(self, "Missing URL", "Please provide at least one RTSP Stream URL.")
            return

        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"day_url": day_url, "thermal_url": thermal_url}, f, indent=4)
        except Exception:
            pass

        self.config_saved.emit(day_url, thermal_url)
        self.accept()
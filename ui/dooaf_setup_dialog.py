import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QLineEdit, QPushButton, QGroupBox, QInputDialog, QMessageBox, QFileDialog
)
from PySide6.QtCore import Signal, Qt

SETUP_STYLE = """
QDialog {
    background-color: #0b1118;
    color: #e2e8f0;
}
QGroupBox {
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-size: 11px;
    font-weight: bold;
    color: #94a3b8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: bold;
}
QLineEdit {
    background-color: #030712;
    border: 1px solid #1f2937;
    border-radius: 4px;
    color: #10b981;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 5px 8px;
}
QLineEdit:focus {
    border: 1px solid #38bdf8;
}
QPushButton {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    color: #cbd5e1;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 12px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #1e293b;
    border-color: #38bdf8;
    color: #ffffff;
}
QPushButton#dem_btn {
    background-color: #1e3a5f;
    border: 1px solid #38bdf8;
    color: #7dd3fc;
}
QPushButton#dem_btn:hover {
    background-color: #0369a1;
    color: #ffffff;
}
QPushButton#calc_btn {
    background-color: #0284c7;
    border: 1px solid #0369a1;
    color: #ffffff;
    padding: 6px 16px;
}
QPushButton#calc_btn:hover {
    background-color: #0369a1;
}
QPushButton#reset_btn {
    background-color: #b91c1c;
    border: 1px solid #ef4444;
    color: #ffffff;
    padding: 6px 16px;
}
QPushButton#reset_btn:hover {
    background-color: #dc2626;
}
"""

class DooafSetupDialog(QDialog):
    pick_requested = Signal(str, str)
    setup_applied = Signal(dict)
    reset_requested = Signal()
    dem_uploaded = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DOOAF Mission Configuration & Coordinates")
        self.resize(620, 740)
        self.setStyleSheet(SETUP_STYLE)

        self.auth_pin = "1234"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ---------------- 0. DEM ELEVATION FILE UPLOAD ----------------
        dem_bar = QHBoxLayout()
        self.btn_upload_dem = QPushButton("📂 UPLOAD DEM (.TIF)")
        self.btn_upload_dem.setObjectName("dem_btn")
        self.btn_upload_dem.clicked.connect(self.choose_dem_file)
        dem_bar.addWidget(self.btn_upload_dem)

        self.lbl_dem_status = QLabel("DEM: No elevation file loaded (Flat baseline 0.0m)")
        self.lbl_dem_status.setStyleSheet("color: #fdba74; font-size: 10px;")
        dem_bar.addWidget(self.lbl_dem_status, stretch=1)
        main_layout.addLayout(dem_bar)

        # ---------------- 1. ARTILLERY BATTERY (REQUIRES AUTH) ----------------
        box_gun = QGroupBox("Artillery battery point (requires authentication)")
        g_layout = QGridLayout(box_gun)
        g_layout.setVerticalSpacing(8)

        g_layout.addWidget(QLabel("Latitude"), 0, 0)
        self.txt_gun_lat = QLineEdit("12.970978")
        g_layout.addWidget(self.txt_gun_lat, 0, 1, 1, 3)

        g_layout.addWidget(QLabel("Longitude"), 1, 0)
        self.txt_gun_lon = QLineEdit("77.579739")
        g_layout.addWidget(self.txt_gun_lon, 1, 1, 1, 3)

        btn_gun_map = QPushButton("Pick on map")
        btn_gun_map.clicked.connect(lambda: self.pick_gun_authenticated("MAP"))
        btn_gun_vid = QPushButton("Pick on video")
        btn_gun_vid.clicked.connect(lambda: self.pick_gun_authenticated("VIDEO"))
        btn_gun_clear = QPushButton("Clear")
        btn_gun_clear.clicked.connect(lambda: self.clear_fields("GUN"))

        g_layout.addWidget(btn_gun_map, 2, 1)
        g_layout.addWidget(btn_gun_vid, 2, 2)
        g_layout.addWidget(btn_gun_clear, 2, 3)
        main_layout.addWidget(box_gun)

        # ---------------- 2. ACTUAL TARGET POINT (NO AUTH) ----------------
        box_tgt = QGroupBox("Actual target point (officer / camera / map)")
        t_layout = QGridLayout(box_tgt)
        t_layout.setVerticalSpacing(8)

        t_layout.addWidget(QLabel("Latitude"), 0, 0)
        self.txt_tgt_lat = QLineEdit()
        self.txt_tgt_lat.setPlaceholderText("e.g. 12.971200")
        t_layout.addWidget(self.txt_tgt_lat, 0, 1, 1, 3)

        t_layout.addWidget(QLabel("Longitude"), 1, 0)
        self.txt_tgt_lon = QLineEdit()
        self.txt_tgt_lon.setPlaceholderText("e.g. 77.580100")
        t_layout.addWidget(self.txt_tgt_lon, 1, 1, 1, 3)

        t_layout.addWidget(QLabel("Altitude (MSL m)"), 2, 0)
        self.txt_tgt_alt = QLineEdit("0.0")
        t_layout.addWidget(self.txt_tgt_alt, 2, 1, 1, 3)

        btn_tgt_map = QPushButton("Pick on map")
        btn_tgt_map.clicked.connect(lambda: self.pick_direct("TARGET", "MAP"))
        btn_tgt_vid = QPushButton("Pick on video")
        btn_tgt_vid.clicked.connect(lambda: self.pick_direct("TARGET", "VIDEO"))
        btn_tgt_clear = QPushButton("Clear")
        btn_tgt_clear.clicked.connect(lambda: self.clear_fields("TARGET"))

        t_layout.addWidget(btn_tgt_map, 3, 1)
        t_layout.addWidget(btn_tgt_vid, 3, 2)
        t_layout.addWidget(btn_tgt_clear, 3, 3)
        main_layout.addWidget(box_tgt)

        # ---------------- 3. IMPACT TARGET POINT (NO AUTH) ----------------
        box_imp = QGroupBox("Impact target point (fall of shot)")
        i_layout = QGridLayout(box_imp)
        i_layout.setVerticalSpacing(8)

        i_layout.addWidget(QLabel("Latitude"), 0, 0)
        self.txt_imp_lat = QLineEdit()
        self.txt_imp_lat.setPlaceholderText("e.g. 12.971050")
        i_layout.addWidget(self.txt_imp_lat, 0, 1, 1, 3)

        i_layout.addWidget(QLabel("Longitude"), 1, 0)
        self.txt_imp_lon = QLineEdit()
        self.txt_imp_lon.setPlaceholderText("e.g. 77.580250")
        i_layout.addWidget(self.txt_imp_lon, 1, 1, 1, 3)

        t_layout.addWidget(QLabel("Altitude (MSL m)"), 2, 0)
        self.txt_imp_alt = QLineEdit("0.0")
        i_layout.addWidget(self.txt_imp_alt, 2, 1, 1, 3)

        btn_imp_map = QPushButton("Pick on map")
        btn_imp_map.clicked.connect(lambda: self.pick_direct("IMPACT", "MAP"))
        btn_imp_vid = QPushButton("Pick on video")
        btn_imp_vid.clicked.connect(lambda: self.pick_direct("IMPACT", "VIDEO"))
        btn_imp_clear = QPushButton("Clear")
        btn_imp_clear.clicked.connect(lambda: self.clear_fields("IMPACT"))

        i_layout.addWidget(btn_imp_map, 3, 1)
        i_layout.addWidget(btn_imp_vid, 3, 2)
        i_layout.addWidget(btn_imp_clear, 3, 3)
        main_layout.addWidget(box_imp)

        # ---------------- 4. FOOTER ACTIONS ----------------
        footer_layout = QHBoxLayout()
        btn_clear_all = QPushButton("Clear all")
        btn_clear_all.clicked.connect(self.clear_all)
        footer_layout.addWidget(btn_clear_all)

        footer_layout.addStretch()

        btn_reset = QPushButton("RESET MAP TARGETS")
        btn_reset.setObjectName("reset_btn")
        btn_reset.clicked.connect(self.trigger_reset)
        footer_layout.addWidget(btn_reset)

        btn_ok = QPushButton("OK (CALCULATE REPORT)")
        btn_ok.setObjectName("calc_btn")
        btn_ok.clicked.connect(self.apply_and_close)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        footer_layout.addWidget(btn_ok)
        footer_layout.addWidget(btn_cancel)
        main_layout.addLayout(footer_layout)

    def choose_dem_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Digital Elevation Model GeoTIFF", "", "Elevation Rasters (*.tif *.tiff *.dem)"
        )
        if file_path:
            self.dem_uploaded.emit(file_path)

    def set_dem_status(self, filename: str, is_active: bool):
        if is_active:
            self.lbl_dem_status.setText(f"DEM ACTIVE: {filename}")
            self.lbl_dem_status.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 10px;")
        else:
            self.lbl_dem_status.setText("DEM: Error loading file")
            self.lbl_dem_status.setStyleSheet("color: #f87171; font-weight: bold; font-size: 10px;")

    def trigger_reset(self):
        self.clear_fields("TARGET")
        self.clear_fields("IMPACT")
        self.reset_requested.emit()

    def pick_gun_authenticated(self, source):
        pin, ok = QInputDialog.getText(
            self,
            "Commander Authorization Required",
            "Enter Authorization PIN to reposition Artillery Battery:",
            QLineEdit.Password
        )
        if not ok or pin.strip() != self.auth_pin:
            QMessageBox.warning(self, "Access Denied", "Incorrect PIN. Artillery position remains unchanged.")
            return

        self.pick_requested.emit("GUN", source)
        self.hide()

    def pick_direct(self, entity, source):
        self.pick_requested.emit(entity, source)
        self.hide()

    def receive_picked_coord(self, entity, lat, lon, elev=None):
        if entity == "GUN":
            self.txt_gun_lat.setText(f"{lat:.6f}")
            self.txt_gun_lon.setText(f"{lon:.6f}")
        elif entity == "TARGET":
            self.txt_tgt_lat.setText(f"{lat:.6f}")
            self.txt_tgt_lon.setText(f"{lon:.6f}")
            if elev is not None:
                self.txt_tgt_alt.setText(f"{elev:.1f}")
        elif entity == "IMPACT":
            self.txt_imp_lat.setText(f"{lat:.6f}")
            self.txt_imp_lon.setText(f"{lon:.6f}")
            if elev is not None:
                self.txt_imp_alt.setText(f"{elev:.1f}")
        self.show()
        self.raise_()

    def clear_fields(self, entity):
        if entity == "GUN":
            self.txt_gun_lat.clear()
            self.txt_gun_lon.clear()
        elif entity == "TARGET":
            self.txt_tgt_lat.clear()
            self.txt_tgt_lon.clear()
            self.txt_tgt_alt.setText("0.0")
        elif entity == "IMPACT":
            self.txt_imp_lat.clear()
            self.txt_imp_lon.clear()
            self.txt_imp_alt.setText("0.0")

    def clear_all(self):
        self.clear_fields("GUN")
        self.clear_fields("TARGET")
        self.clear_fields("IMPACT")

    def apply_and_close(self):
        try:
            g_lat = float(self.txt_gun_lat.text().strip()) if self.txt_gun_lat.text().strip() else 12.970978
            g_lon = float(self.txt_gun_lon.text().strip()) if self.txt_gun_lon.text().strip() else 77.579739

            t_lat = float(self.txt_tgt_lat.text().strip()) if self.txt_tgt_lat.text().strip() else None
            t_lon = float(self.txt_tgt_lon.text().strip()) if self.txt_tgt_lon.text().strip() else None
            t_alt = float(self.txt_tgt_alt.text().strip()) if self.txt_tgt_alt.text().strip() else 0.0

            i_lat = float(self.txt_imp_lat.text().strip()) if self.txt_imp_lat.text().strip() else None
            i_lon = float(self.txt_imp_lon.text().strip()) if self.txt_imp_lon.text().strip() else None
            i_alt = float(self.txt_imp_alt.text().strip()) if self.txt_imp_alt.text().strip() else 0.0

            data = {
                "gun_lat": g_lat, "gun_lon": g_lon,
                "tgt_lat": t_lat, "tgt_lon": t_lon, "tgt_alt": t_alt,
                "imp_lat": i_lat, "imp_lon": i_lon, "imp_alt": i_alt
            }
            self.setup_applied.emit(data)
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Coordinate Error", "Please provide valid numeric coordinates.")
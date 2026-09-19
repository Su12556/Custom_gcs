from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QFrame
)
from PySide6.QtCore import Qt

MODAL_STYLE = """
QDialog {
    background-color: #0b1118;
    border: 2px solid #00ffcc;
    border-radius: 10px;
}
QLabel {
    font-family: 'Segoe UI', system-ui, sans-serif;
    color: #cbd5e1;
    background: transparent;
    border: none;
}
"""

class TacticalTargetPopup(QDialog):
    def __init__(self, mode: str, data: dict, parent=None):
        super().__init__(parent)
        # Use Tool/Dialog flag with frameless style to prevent taskbar fragmentation and collapse
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(MODAL_STYLE)

        # STRICT GEOMETRY LOCK: prevents Qt from collapsing the window into a line
        if mode == "IMPACT":
            self.setFixedSize(580, 640)
        else:
            self.setFixedSize(580, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 20)
        main_layout.setSpacing(14)

        # ---------------- 1. HEADER BAR ----------------
        hdr = QHBoxLayout()
        icon = "🎯" if mode == "TARGET" else "💥"
        title_text = "ACTUAL TARGET DESIGNATED" if mode == "TARGET" else "FALL OF SHOT / IMPACT OBSERVED"
        title_color = "#10b981" if mode == "TARGET" else "#f97316"
        
        lbl_title = QLabel(f"{icon}  {title_text}")
        lbl_title.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: 800; letter-spacing: 0.06em;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #dc2626;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        btn_close.clicked.connect(self.accept)
        hdr.addWidget(btn_close)
        main_layout.addLayout(hdr)

        # ---------------- 2. OBSERVED COORDINATES BOX ----------------
        loc_box = QFrame()
        loc_box.setStyleSheet("background-color: #030712; border: 1px solid #1e293b; border-radius: 6px;")
        loc_grid = QGridLayout(loc_box)
        loc_grid.setContentsMargins(16, 12, 16, 12)
        loc_grid.setVerticalSpacing(8)
        loc_grid.setHorizontalSpacing(16)

        loc_grid.addWidget(QLabel("Latitude:"), 0, 0)
        lbl_lat = QLabel(f"{data.get('lat', 0.0):.6f}°")
        lbl_lat.setStyleSheet("font-family: Consolas; color: #ffffff; font-weight: bold; font-size: 13px;")
        loc_grid.addWidget(lbl_lat, 0, 1)

        loc_grid.addWidget(QLabel("Longitude:"), 1, 0)
        lbl_lon = QLabel(f"{data.get('lon', 0.0):.6f}°")
        lbl_lon.setStyleSheet("font-family: Consolas; color: #ffffff; font-weight: bold; font-size: 13px;")
        loc_grid.addWidget(lbl_lon, 1, 1)

        loc_grid.addWidget(QLabel("Elevation (MSL):"), 2, 0)
        lbl_alt = QLabel(f"{data.get('alt', 0.0):.1f} meters")
        lbl_alt.setStyleSheet("font-family: Consolas; color: #ffffff; font-weight: bold; font-size: 13px;")
        loc_grid.addWidget(lbl_alt, 2, 1)

        loc_grid.addWidget(QLabel("MGRS (Grid Ref):"), 3, 0)
        lbl_mgrs = QLabel(data.get("mgrs", "--"))
        lbl_mgrs.setStyleSheet("font-family: Consolas; color: #00ffcc; font-size: 14px; font-weight: 800;")
        loc_grid.addWidget(lbl_mgrs, 3, 1)

        main_layout.addWidget(loc_box)

        # ---------------- 3. TARGET COMPARISON + CORRECTIONS (IMPACT ONLY) ----------------
        if mode == "IMPACT":
            tgt = data.get("target_info", {})
            corr = data.get("corr_info", {})

            # Target Reference Sub-box
            lbl_ref = QLabel("🎯  INTENDED TARGET REFERENCE")
            lbl_ref.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.08em;")
            main_layout.addWidget(lbl_ref)

            tgt_box = QFrame()
            tgt_box.setStyleSheet("background-color: #030712; border: 1px solid #1e293b; border-radius: 6px;")
            tgt_layout = QVBoxLayout(tgt_box)
            tgt_layout.setContentsMargins(14, 10, 14, 10)
            tgt_layout.setSpacing(4)

            t_coord = QLabel(f"Target Lat/Lon:  {tgt.get('lat', 0.0):.6f}°, {tgt.get('lon', 0.0):.6f}°")
            t_coord.setStyleSheet("color: #94a3b8; font-size: 12px; font-family: Consolas;")
            t_mgrs = QLabel(f"Target GR:  <b style='color:#00ffcc;'>{tgt.get('mgrs', '--')}</b>   |   Alt:  <b style='color:#ffffff;'>{tgt.get('alt', 0.0):.1f} m</b>")
            t_mgrs.setStyleSheet("color: #e2e8f0; font-size: 12px;")

            tgt_layout.addWidget(t_coord)
            tgt_layout.addWidget(t_mgrs)
            main_layout.addWidget(tgt_box)

            # Fire Shift Orders Sub-box
            lbl_shift = QLabel("⚡  FIRE SHIFT ORDERS (DOOAF SOLUTION)")
            lbl_shift.setStyleSheet("font-size: 11px; font-weight: 800; color: #94a3b8; letter-spacing: 0.08em;")
            main_layout.addWidget(lbl_shift)

            r_val = corr.get("range_m", 0.0)
            l_val = corr.get("lat_m", 0.0)
            d_mils = corr.get("defl_mils", 0.0)
            h_val = corr.get("height_m", 0.0)

            r_action = "Add" if r_val >= 0 else "Drop"
            d_action = "Right" if l_val >= 0 else "Left"
            h_action = "Up" if h_val >= 0 else "Down"

            cards_frame = QFrame()
            cards_frame.setStyleSheet("background: transparent; border: none;")
            cards_grid = QGridLayout(cards_frame)
            cards_grid.setContentsMargins(0, 0, 0, 0)
            cards_grid.setSpacing(10)

            # Style for each stat card
            card_ss = "background-color: #06101e; border: 1px solid #0284c7; border-radius: 6px; padding: 6px 10px;"

            # Card 1: Range
            c1 = QFrame()
            c1.setStyleSheet(card_ss)
            ly1 = QVBoxLayout(c1)
            ly1.setContentsMargins(4, 4, 4, 4)
            t1 = QLabel("RANGE SHIFT")
            t1.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
            v1 = QLabel(f"{r_action} {abs(r_val):.1f} m")
            v1.setStyleSheet("color: #fdba74; font-family: Consolas; font-size: 15px; font-weight: 800;")
            ly1.addWidget(t1)
            ly1.addWidget(v1)
            cards_grid.addWidget(c1, 0, 0)

            # Card 2: Deflection
            c2 = QFrame()
            c2.setStyleSheet(card_ss)
            ly2 = QVBoxLayout(c2)
            ly2.setContentsMargins(4, 4, 4, 4)
            t2 = QLabel("DEFLECTION")
            t2.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
            v2 = QLabel(f"{d_action} {abs(d_mils):.1f} mils ({abs(l_val):.1f}m)")
            v2.setStyleSheet("color: #c4b5fd; font-family: Consolas; font-size: 12px; font-weight: 800;")
            ly2.addWidget(t2)
            ly2.addWidget(v2)
            cards_grid.addWidget(c2, 0, 1)

            # Card 3: Height
            c3 = QFrame()
            c3.setStyleSheet(card_ss)
            ly3 = QVBoxLayout(c3)
            ly3.setContentsMargins(4, 4, 4, 4)
            t3 = QLabel("HEIGHT CORRECTION")
            t3.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
            v3 = QLabel(f"{h_action} {abs(h_val):.1f} m")
            v3.setStyleSheet("color: #fef08a; font-family: Consolas; font-size: 15px; font-weight: 800;")
            ly3.addWidget(t3)
            ly3.addWidget(v3)
            cards_grid.addWidget(c3, 1, 0)

            # Card 4: GTL / Total Miss
            c4 = QFrame()
            c4.setStyleSheet(card_ss)
            ly4 = QVBoxLayout(c4)
            ly4.setContentsMargins(4, 4, 4, 4)
            t4 = QLabel("GTL / TOTAL GROUND MISS")
            t4.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
            v4 = QLabel(f"{corr.get('gtl', 0.0):.1f}° TN  |  {corr.get('miss_dist', 0.0):.1f} m")
            v4.setStyleSheet("color: #00ffcc; font-family: Consolas; font-size: 12px; font-weight: 800;")
            ly4.addWidget(t4)
            ly4.addWidget(v4)
            cards_grid.addWidget(c4, 1, 1)

            main_layout.addWidget(cards_frame)

        # ---------------- 4. ACTION BUTTON ----------------
        btn_ack = QPushButton("ACKNOWLEDGE && CONTINUE")
        btn_ack.setFixedHeight(40)
        btn_ack.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                letter-spacing: 0.06em;
                border: 1px solid #0369a1;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        btn_ack.clicked.connect(self.accept)
        main_layout.addWidget(btn_ack)
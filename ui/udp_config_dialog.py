from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox
)
from PySide6.QtCore import Signal

UDP_POPUP_STYLE = """
QDialog {
    background-color: #0e1318;
    border: 1px solid #1f2a37;
    border-radius: 8px;
}
QLabel {
    color: #cbd5e1;
    font-size: 11px;
    font-family: 'Segoe UI', sans-serif;
    font-weight: bold;
}
QLineEdit {
    background-color: #070a0d;
    border: 1px solid #233040;
    border-radius: 4px;
    color: #00ffcc;
    font-family: 'Consolas', monospace;
    font-size: 11px;
    padding: 5px 8px;
}
QLineEdit:focus {
    border: 1px solid #00ffcc;
}
QComboBox {
    background-color: #070a0d;
    border: 1px solid #233040;
    border-radius: 4px;
    color: #e2e8f0;
    padding: 5px;
    font-size: 11px;
}
QPushButton {
    background-color: #16202c;
    border: 1px solid #283747;
    border-radius: 4px;
    color: #e2e8f0;
    font-size: 11px;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #1f2d3d;
    border: 1px solid #38bdf8;
}
QPushButton#connect_btn {
    background-color: #0284c7;
    border: 1px solid #0369a1;
    color: #ffffff;
}
QPushButton#connect_btn:hover {
    background-color: #0369a1;
}
"""

class UdpConfigDialog(QDialog):
    udp_configured = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MAVLink UDP Link Configuration")
        self.setFixedWidth(380)
        self.setStyleSheet(UDP_POPUP_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("ENTER MAVLINK NETWORK PARAMETERS")
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; letter-spacing: 0.5px;")
        layout.addWidget(title_lbl)

        # Mode Selection - Listen (UDP In) as default index 0
        mode_row = QHBoxLayout()
        lbl_mode = QLabel("Mode:")
        lbl_mode.setFixedWidth(80)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Listen (UDP In - Recommended)", "Client (UDP Out)"])
        self.cmb_mode.currentIndexChanged.connect(self.on_mode_changed)
        mode_row.addWidget(lbl_mode)
        mode_row.addWidget(self.cmb_mode)
        layout.addLayout(mode_row)

        # IP Address
        ip_row = QHBoxLayout()
        lbl_ip = QLabel("IP Address:")
        lbl_ip.setFixedWidth(80)
        self.txt_ip = QLineEdit("0.0.0.0")
        ip_row.addWidget(lbl_ip)
        ip_row.addWidget(self.txt_ip)
        layout.addLayout(ip_row)

        # Port Number
        port_row = QHBoxLayout()
        lbl_port = QLabel("Port:")
        lbl_port.setFixedWidth(80)
        self.txt_port = QLineEdit("14550")
        port_row.addWidget(lbl_port)
        port_row.addWidget(self.txt_port)
        layout.addLayout(port_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_connect = QPushButton("CONNECT UDP")
        self.btn_connect.setObjectName("connect_btn")
        self.btn_connect.clicked.connect(self.on_apply)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_connect)
        layout.addLayout(btn_row)

    def on_mode_changed(self, idx):
        if idx == 0:  # UDP In (Listen)
            self.txt_ip.setText("0.0.0.0")
        else:         # UDP Out (Forward)
            self.txt_ip.setText("127.0.0.1")

    def on_apply(self):
        ip = self.txt_ip.text().strip()
        try:
            port = int(self.txt_port.text().strip())
        except ValueError:
            port = 14550

        if self.cmb_mode.currentIndex() == 0:
            ip = ip or "0.0.0.0"
            conn_str = f"udpin:{ip}:{port}"
        else:
            if ip in ["0.0.0.0", ""]:
                ip = "127.0.0.1"
            conn_str = f"udpout:{ip}:{port}"

        self.udp_configured.emit(conn_str, port)
        self.accept()
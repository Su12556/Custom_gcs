import os
import webbrowser
from datetime import datetime
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt

class DooafReportDialog(QDialog):
    def __init__(self, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VIKAS GCS - DOOAF Observation Fire-Correction Report")
        self.resize(1150, 850)
        self.setStyleSheet("background-color: #0c1222; color: #ffffff;")

        # Save HTML report file to reports/ folder
        reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"observation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        self.report_path = os.path.join(reports_dir, filename)

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Bar
        top_bar = QHBoxLayout()
        title_lbl = QLabel("🎯 DOOAF OBSERVATION MISSION REPORT")
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; color: #38bdf8;")
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()

        btn_browser = QPushButton("🌐 OPEN IN BROWSER")
        btn_browser.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_browser.clicked.connect(self.open_in_browser)
        top_bar.addWidget(btn_browser)

        btn_print = QPushButton("🖨 PRINT / PDF")
        btn_print.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_print.clicked.connect(self.print_report)
        top_bar.addWidget(btn_print)

        layout.addLayout(top_bar)

        # Web Viewer
        self.web_view = QWebEngineView()
        self.web_view.setHtml(html_content)
        layout.addWidget(self.web_view)

    def open_in_browser(self):
        webbrowser.open(f"file://{self.report_path}")

    def print_report(self):
        # Triggers browser print preview dialog for one-click PDF export
        webbrowser.open(f"file://{self.report_path}")
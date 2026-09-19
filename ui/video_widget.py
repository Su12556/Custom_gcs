from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QImage
from PySide6.QtCore import Qt, Signal, QPoint, QRect


class ClickableVideoLabel(QWidget):
    pixel_clicked = Signal(int, int, int, int)  # px, py, frame_w, frame_h

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.raw_frame = None
        self.selection_mode = False
        self.selection_entity = None
        self.clicked_point = None
        self.placeholder_text = "NO GIMBAL CAMERA FEED\n[Click 📹 on Left Toolbar]"

    def setText(self, text: str):
        self.placeholder_text = text
        self.raw_frame = None
        self.update()

    def set_selection_mode(self, enabled: bool, entity: str = None):
        self.selection_mode = enabled
        self.selection_entity = entity
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            self.clicked_point = None
        self.update()

    def update_frame(self, frame):
        self.raw_frame = frame
        self.update()

    def mousePressEvent(self, event):
        if self.selection_mode and self.raw_frame is not None and event.button() == Qt.LeftButton:
            if isinstance(self.raw_frame, QImage):
                fw = self.raw_frame.width()
                fh = self.raw_frame.height()
            elif hasattr(self.raw_frame, 'shape'):
                fh, fw = self.raw_frame.shape[:2]
            else:
                return

            widget_w = self.width()
            widget_h = self.height()

            frame_aspect = fw / float(fh)
            widget_aspect = widget_w / float(widget_h)

            if widget_aspect > frame_aspect:
                render_h = widget_h
                render_w = int(widget_h * frame_aspect)
                offset_x = (widget_w - render_w) // 2
                offset_y = 0
            else:
                render_w = widget_w
                render_h = int(widget_w / frame_aspect)
                offset_x = 0
                offset_y = (widget_h - render_h) // 2

            click_x = event.position().x()
            click_y = event.position().y()

            # Ensure click is inside the active video letterbox
            if offset_x <= click_x <= offset_x + render_w and offset_y <= click_y <= offset_y + render_h:
                px = int((click_x - offset_x) * (fw / float(render_w)))
                py = int((click_y - offset_y) * (fh / float(render_h)))
                self.clicked_point = (click_x, click_y)
                self.pixel_clicked.emit(px, py, fw, fh)
                self.set_selection_mode(False)
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            widget_w = self.width()
            widget_h = self.height()

            painter.fillRect(0, 0, widget_w, widget_h, QColor(11, 15, 25))

            if self.raw_frame is None:
                painter.setPen(QColor(100, 116, 139))
                painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
                painter.drawText(self.rect(), Qt.AlignCenter, self.placeholder_text)
                return

            if isinstance(self.raw_frame, QImage):
                qimg = self.raw_frame
            elif hasattr(self.raw_frame, 'shape'):
                import cv2
                rgb_frame = cv2.cvtColor(self.raw_frame, cv2.COLOR_BGR2RGB)
                fh, fw, ch = rgb_frame.shape
                qimg = QImage(rgb_frame.data, fw, fh, ch * fw, QImage.Format_RGB888)
            else:
                return

            fw = qimg.width()
            fh = qimg.height()
            if fw == 0 or fh == 0:
                return

            frame_aspect = fw / float(fh)
            widget_aspect = widget_w / float(widget_h)

            if widget_aspect > frame_aspect:
                render_h = widget_h
                render_w = int(widget_h * frame_aspect)
                offset_x = (widget_w - render_w) // 2
                offset_y = 0
            else:
                render_w = widget_w
                render_h = int(widget_w / frame_aspect)
                offset_x = 0
                offset_y = (widget_h - render_h) // 2

            target_rect = QRect(offset_x, offset_y, render_w, render_h)
            painter.drawImage(target_rect, qimg)

            # Draw crosshair targeting banner
            if self.selection_mode:
                painter.setPen(QPen(QColor(0, 255, 204, 220), 2, Qt.DashLine))
                painter.drawRect(target_rect)

                tag = self.selection_entity or "POINT"
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
                painter.drawText(
                    QRect(offset_x + 16, offset_y + 16, 400, 30),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    f"🎯 CLICK ON VIDEO TO DESIGNATE {tag}"
                )

            # Draw persistent yellow click marker
            if self.clicked_point:
                cx, cy = self.clicked_point
                painter.setPen(QPen(QColor(250, 204, 21), 2))
                painter.drawLine(cx - 15, cy, cx + 15, cy)
                painter.drawLine(cx, cy - 15, cx, cy + 15)
                painter.drawEllipse(QPoint(cx, cy), 8, 8)

        finally:
            painter.end()
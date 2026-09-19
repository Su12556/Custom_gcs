import os
import re
import socket
from datetime import datetime
import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


def is_rtsp_reachable(url: str, timeout_sec: float = 1.5) -> bool:
    try:
        match = re.search(r"rtsp://([^:/]+)(?::(\d+))?", url)
        if not match:
            return True
        host = match.group(1)
        port = int(match.group(2)) if match.group(2) else 554

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


class GimbalCameraThread(QThread):
    frame_received = Signal(QImage)
    status_changed = Signal(str)
    snapshot_saved = Signal(str)

    def __init__(self, source="", parent=None):
        super().__init__(parent)
        self.source = str(source).strip() if source else ""
        self.running = False
        self.cap = None

        # Recording state
        self.is_recording = False
        self.video_writer = None
        self.take_snapshot_flag = False

        # Lens digital zoom state (1.0x to 10.0x)
        self.zoom_factor = 1.0

    def start_recording(self, output_dir="recordings"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        filename = os.path.join(
            output_dir, f"GIMBAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        self.record_filename = filename
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False
        if self.video_writer is not None:
            try:
                self.video_writer.release()
            except Exception:
                pass
            self.video_writer = None

    def trigger_snapshot(self):
        self.take_snapshot_flag = True

    def set_zoom(self, zoom: float):
        self.zoom_factor = max(1.0, min(10.0, zoom))

    def run(self):
        if not self.source:
            self.status_changed.emit("STREAM ERROR: Empty RTSP URL")
            return

        self.running = True
        self.status_changed.emit("Checking camera network reachability...")

        if self.source.startswith("rtsp://"):
            if not is_rtsp_reachable(self.source, timeout_sec=1.5):
                self.status_changed.emit("STREAM FAILED: Camera unreachable")
                self.running = False
                return

        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|fflags;nobuffer|max_delay;500000|timeout;3000000|stimeout;3000000"
        )

        try:
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self.cap.isOpened():
                self.status_changed.emit("STREAM FAILED: Camera refused session")
                self.running = False
                return

            self.status_changed.emit("STREAM CONNECTED")

            while self.running:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    continue

                h, w = frame.shape[:2]

                # Apply digital zoom crop if zoom > 1.0x
                if self.zoom_factor > 1.0:
                    crop_w = int(w / self.zoom_factor)
                    crop_h = int(h / self.zoom_factor)
                    x1 = (w - crop_w) // 2
                    y1 = (h - crop_h) // 2
                    frame = frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
                    frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)

                # Snapshot logic
                if self.take_snapshot_flag:
                    self.take_snapshot_flag = False
                    snap_dir = "snapshots"
                    os.makedirs(snap_dir, exist_ok=True)
                    snap_path = os.path.join(
                        snap_dir, f"SNAP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    )
                    cv2.imwrite(snap_path, frame)
                    self.snapshot_saved.emit(snap_path)

                # Recording logic
                if self.is_recording:
                    if self.video_writer is None:
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        self.video_writer = cv2.VideoWriter(
                            self.record_filename, fourcc, 25.0, (w, h)
                        )
                    self.video_writer.write(frame)
                elif self.video_writer is not None:
                    self.video_writer.release()
                    self.video_writer = None

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w
                q_img = QImage(
                    rgb_frame.data,
                    w,
                    h,
                    bytes_per_line,
                    QImage.Format_RGB888
                ).copy()

                self.frame_received.emit(q_img)

        except Exception as e:
            self.status_changed.emit(f"STREAM ERROR: {e}")
        finally:
            self.running = False
            self.stop_recording()
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            self.status_changed.emit("STREAM STOPPED")

    def stop(self):
        self.running = False
        self.stop_recording()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.quit()
        self.wait(1500)
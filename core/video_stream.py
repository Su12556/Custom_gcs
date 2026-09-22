import os
import re
import socket
import threading
from datetime import datetime
import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

def is_rtsp_reachable(url: str, timeout_sec: float = 1.0) -> bool:
    try:
        match = re.search(r"rtsp://([^:/]+)(?::(\d+))?", url)
        if not match:
            return True
        host = match.group(1)
        port = int(match.group(2)) if match.group(2) else 554
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_sec)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False

class GimbalCameraThread(QThread):
    frame_received = Signal(QImage)
    status_changed = Signal(str)
    snapshot_saved = Signal(str)

    def __init__(self, source="", parent=None):
        super().__init__(parent)
        self.source = str(source).strip() if source else ""
        self._is_running = False
        self.cap = None

        # Thread-safe synchronization
        self._lock = threading.Lock()
        self.is_recording = False
        self._start_rec_requested = False
        self._stop_rec_requested = False
        self.output_rec_dir = "recordings"
        self.record_filename = None
        self.video_writer = None

        self.take_snapshot_flag = False
        self.zoom_factor = 1.0

    def start_recording(self, output_dir="recordings"):
        with self._lock:
            self.output_rec_dir = output_dir
            self._start_rec_requested = True
            self._stop_rec_requested = False

    def stop_recording(self):
        with self._lock:
            self._stop_rec_requested = True
            self._start_rec_requested = False

    def trigger_snapshot(self):
        self.take_snapshot_flag = True

    def set_zoom(self, zoom: float):
        self.zoom_factor = max(1.0, min(10.0, zoom))

    def _close_writer(self):
        if self.video_writer is not None:
            try:
                self.video_writer.release()
            except Exception:
                pass
            self.video_writer = None
        self.is_recording = False

    def run(self):
        if not self.source:
            self.status_changed.emit("STREAM ERROR: URL empty")
            return

        self._is_running = True
        self.status_changed.emit("CONNECTING...")

        # Guard: Check host socket reachability before invoking OpenCV FFMPEG
        if self.source.startswith("rtsp://"):
            if not is_rtsp_reachable(self.source, timeout_sec=1.2):
                self.status_changed.emit("STREAM OFFLINE: Host unreachable")
                self._is_running = False
                return

        # Modern FFmpeg options: enforce TCP, discard corrupt slices, low buffer delay
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|fflags;nobuffer+discardcorrupt|flags;low_delay|"
            "max_delay;250000|stimeout;3000000|timeout;3000000"
        )

        try:
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self.cap.isOpened():
                self.status_changed.emit("STREAM ERROR: Failed to open device")
                self._is_running = False
                return

            self.status_changed.emit("STREAM CONNECTED")

            consecutive_failures = 0

            while self._is_running:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 60:
                        self.status_changed.emit("STREAM TIMEOUT: Feed lost")
                        break
                    QThread.msleep(15)
                    continue

                consecutive_failures = 0
                h, w = frame.shape[:2]

                # Atomic Recording State Handling
                with self._lock:
                    if self._start_rec_requested:
                        self._start_rec_requested = False
                        os.makedirs(self.output_rec_dir, exist_ok=True)
                        self.record_filename = os.path.join(
                            self.output_rec_dir,
                            f"GIMBAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                        )
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        self.video_writer = cv2.VideoWriter(
                            self.record_filename, fourcc, 25.0, (w, h)
                        )
                        self.is_recording = True

                    if self._stop_rec_requested:
                        self._stop_rec_requested = False
                        self._close_writer()

                # Digital Zoom
                if self.zoom_factor > 1.0:
                    crop_w = int(w / self.zoom_factor)
                    crop_h = int(h / self.zoom_factor)
                    x1 = (w - crop_w) // 2
                    y1 = (h - crop_h) // 2
                    frame = frame[y1:y1 + crop_h, x1:x1 + crop_w]
                    frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)

                # Snapshot Handling
                if self.take_snapshot_flag:
                    self.take_snapshot_flag = False
                    snap_dir = "snapshots"
                    os.makedirs(snap_dir, exist_ok=True)
                    snap_path = os.path.join(
                        snap_dir, f"SNAP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    )
                    cv2.imwrite(snap_path, frame)
                    self.snapshot_saved.emit(snap_path)

                # Thread-safe write
                if self.is_recording and self.video_writer is not None:
                    try:
                        self.video_writer.write(frame)
                    except Exception:
                        pass

                # Convert to QImage for PySide6 GUI
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
            self.status_changed.emit(f"STREAM EXCEPTION: {e}")
        finally:
            self._is_running = False
            self._close_writer()
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def stop(self):
        """Clean and synchronous thread termination."""
        self._is_running = False
        with self._lock:
            self._stop_rec_requested = True
        
        # Unblock VideoCapture read if waiting
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass

        self.quit()
        self.wait(1500)
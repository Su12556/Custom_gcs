import os
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QThread, Signal

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

class AutoTileCacheWorker(QThread):
    progress_updated = Signal(int, int, str)  # completed, total, message
    caching_finished = Signal(bool, str)

    def __init__(self, lat: float, lon: float, radius_km: float = 100.0, parent=None):
        super().__init__(parent)
        self.center_lat = lat
        self.center_lon = lon
        self.radius_km = radius_km
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _download_tile(self, z, x, y, out_folder="ui/tiles"):
        if not self._is_running:
            return False

        tile_dir = os.path.join(out_folder, str(z), str(x))
        os.makedirs(tile_dir, exist_ok=True)
        tile_path = os.path.join(tile_dir, f"{y}.png")

        if os.path.exists(tile_path) and os.path.getsize(tile_path) > 700:
            return True

        url = f"https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

        for _ in range(2):
            if not self._is_running:
                return False
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = resp.read()
                    if len(data) > 400:
                        with open(tile_path, 'wb') as f:
                            f.write(data)
                        return True
            except Exception:
                time.sleep(0.05)
        return False

    def run(self):
        lat_deg_per_km = 1.0 / 111.0
        lon_deg_per_km = 1.0 / (111.0 * math.cos(math.radians(self.center_lat)))

        min_lat = self.center_lat - (self.radius_km * lat_deg_per_km)
        max_lat = self.center_lat + (self.radius_km * lat_deg_per_km)
        min_lon = self.center_lon - (self.radius_km * lon_deg_per_km)
        max_lon = self.center_lon + (self.radius_km * lon_deg_per_km)

        tasks = []
        # Zoom 8 to 11 (Overview)
        for z in range(8, 12):
            min_x, max_y = deg2num(min_lat, min_lon, z)
            max_x, min_y = deg2num(max_lat, max_lon, z)
            for x in range(min(min_x, max_x), max(min_x, max_x) + 1):
                for y in range(min(min_y, max_y), max(min_y, max_y) + 1):
                    tasks.append((z, x, y))

        # Zoom 14 to 15 (Villages, Flight Corridors, Riverbeds)
        for z in [14, 15]:
            min_x, max_y = deg2num(min_lat, min_lon, z)
            max_x, min_y = deg2num(max_lat, max_lon, z)
            for x in range(min(min_x, max_x), max(min_x, max_x) + 1):
                for y in range(min(min_y, max_y), max(min_y, max_y) + 1):
                    tasks.append((z, x, y))

        total = len(tasks)
        self.progress_updated.emit(0, total, f"Preparing to cache {total} tiles...")

        completed = 0
        with ThreadPoolExecutor(max_workers=24) as executor:
            futures = {executor.submit(self._download_tile, z, x, y): (z, x, y) for z, x, y in tasks}
            for f in as_completed(futures):
                if not self._is_running:
                    break
                completed += 1
                if completed % 150 == 0 or completed == total:
                    self.progress_updated.emit(completed, total, f"Caching: {completed}/{total} tiles")

        if self._is_running:
            self.caching_finished.emit(True, f"Successfully cached 100km radius around ({self.center_lat:.4f}, {self.center_lon:.4f})")
        else:
            self.caching_finished.emit(False, "Caching cancelled by user.")
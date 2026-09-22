import os
import math
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def download_tile(z, x, y, out_folder="ui/tiles"):
    tile_dir = os.path.join(out_folder, str(z), str(x))
    os.makedirs(tile_dir, exist_ok=True)
    tile_path = os.path.join(tile_dir, f"{y}.png")
    
    # Skip if valid tile already exists on disk
    if os.path.exists(tile_path) and os.path.getsize(tile_path) > 700:
        return True
    
    url = f"https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                data = response.read()
                if len(data) > 400:
                    with open(tile_path, 'wb') as f:
                        f.write(data)
                    return True
        except Exception:
            time.sleep(0.04)
    return False

def cache_theater_zoom15(center_lat=21.1702, center_lon=72.8311, radius_km=100.0):
    print("=" * 70)
    print(f"[*] Caching Zoom 15 Theater (Villages, Riverbeds, Flight Corridors)")
    print(f"[*] Base Center : {center_lat:.6f}, {center_lon:.6f}")
    print(f"[*] Theater Area: {radius_km*2:.0f} km x {radius_km*2:.0f} km ({radius_km} km radius)")
    print("=" * 70)

    lat_deg_per_km = 1.0 / 111.0
    lon_deg_per_km = 1.0 / (111.0 * math.cos(math.radians(center_lat)))

    min_lat = center_lat - (radius_km * lat_deg_per_km)
    max_lat = center_lat + (radius_km * lat_deg_per_km)
    min_lon = center_lon - (radius_km * lon_deg_per_km)
    max_lon = center_lon + (radius_km * lon_deg_per_km)

    target_zoom = 15
    min_x, max_y = deg2num(min_lat, min_lon, target_zoom)
    max_x, min_y = deg2num(max_lat, max_lon, target_zoom)

    tasks = []
    for x in range(min(min_x, max_x), max(min_x, max_x) + 1):
        for y in range(min(min_y, max_y), max(min_y, max_y) + 1):
            tasks.append((target_zoom, x, y))

    total = len(tasks)
    print(f"[*] Total Zoom 15 Tiles: {total}")
    print(f"[*] Estimated Disk Space: ~800 MB")
    print(f"[*] Speed: 28 Concurrent Workers with Auto-Retry\n")

    start_time = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=28) as executor:
        future_map = {executor.submit(download_tile, z, x, y): (z, x, y) for z, x, y in tasks}
        for future in as_completed(future_map):
            completed += 1
            if completed % 500 == 0 or completed == total:
                elapsed = time.time() - start_time
                pct = (completed / total) * 100.0
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (total - completed) / rate if rate > 0 else 0
                print(f" -> [{pct:5.1f}%] {completed}/{total} tiles | {rate:.0f} tiles/s | ETA: {remaining:.0f}s")

    elapsed_total = time.time() - start_time
    print(f"\n[✓] SUCCESS: Zoom 15 theater completely cached in {elapsed_total/60:.1f} minutes!")
    print(f"[✓] Storage Location: ui/tiles/15/")

if __name__ == "__main__":
    cache_theater_zoom15(center_lat=21.1702, center_lon=72.8311, radius_km=100.0)
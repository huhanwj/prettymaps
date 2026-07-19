"""terrain-RGB 瓦片（Mapbox 编码）：SRTM DEM → PNG 金字塔 → MapLibre setTerrain。

编码：h = -10000 + (R*65536 + G*256 + B) * 0.1
瓦片数学：标准 slippy map（Web Mercator）。
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import map_coordinates

ZMIN, ZMAX = 10, 16
TILE_SIZE = 256


def encode_height(h):
    v = int(round((h + 10000) * 10))
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def decode_height(r, g, b):
    return (r * 65536 + g * 256 + b) / 10 - 10000


def lon2tilex(lon, z):
    return (lon + 180.0) / 360.0 * 2**z


def lat2tiley(lat, z):
    r = math.radians(lat)
    return (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * 2**z


def tilex2lon(x, z):
    return x / 2**z * 360.0 - 180.0


def tiley2lat(y, z):
    n = math.pi - 2.0 * math.pi * y / 2**z
    return math.degrees(math.atan(math.sinh(n)))


def tiles_covering(minlon, minlat, maxlon, maxlat, z):
    x0 = int(math.floor(lon2tilex(minlon, z)))
    x1 = int(math.floor(lon2tilex(maxlon, z)))
    y0 = int(math.floor(lat2tiley(maxlat, z)))  # 北在上
    y1 = int(math.floor(lat2tiley(minlat, z)))
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def render_tile(dem, lons, lats, z, x, y, size=TILE_SIZE):
    """从 (dem, lons, lats) 双线性采样出一张 size×size×3 的 terrain-RGB 瓦片。"""
    west, east = tilex2lon(x, z), tilex2lon(x + 1, z)
    north, south = tiley2lat(y, z), tiley2lat(y + 1, z)
    out_lons = np.linspace(west, east, size, endpoint=False) + (east - west) / (2 * size)
    out_lats = np.linspace(north, south, size, endpoint=False) + (south - north) / (2 * size)
    cols = (out_lons - lons[0]) / (lons[-1] - lons[0]) * (len(lons) - 1)
    rows = (lats[0] - out_lats) / (lats[0] - lats[-1]) * (len(lats) - 1)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    sampled = map_coordinates(dem, [rr, cc], order=1, mode="nearest")
    v = np.rint((sampled + 10000) * 10).astype(np.int64)
    rgb = np.stack(
        [(v >> 16) & 255, (v >> 8) & 255, v & 255], axis=-1
    ).astype(np.uint8)
    return rgb


def generate_terrain_tiles(dem, lons, lats, out_dir, zmin=ZMIN, zmax=ZMAX):
    """为 (lons,lats) 覆盖范围生成 zmin..zmax 全部瓦片，返回瓦片数。"""
    out_dir = Path(out_dir)
    minlon, maxlon = float(lons[0]), float(lons[-1])
    minlat, maxlat = float(lats[-1]), float(lats[0])
    count = 0
    for z in range(zmin, zmax + 1):
        for z_, x, y in tiles_covering(minlon, minlat, maxlon, maxlat, z):
            rgb = render_tile(dem, lons, lats, z_, x, y)
            path = out_dir / str(z_) / str(x)
            path.mkdir(parents=True, exist_ok=True)
            plt.imsave(path / f"{y}.png", rgb)
            count += 1
    return count

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
MAX_LAT = 85.0511287798066  # Web Mercator 纬度极限


def encode_height(h):
    if not math.isfinite(h):
        raise ValueError(f"无法编码非有限高度：{h}")
    v = int(round((h + 10000) * 10))
    v = max(0, min(v, 0xFFFFFF))  # 钳制到 24bit，防位移溢出回绕
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
    """覆盖 bbox 的 z 级瓦片列表 [(z, x, y), ...]。

    东/南边缘按半开区间处理：bbox 边缘恰好落在瓦片边界上时，不把东侧/
    南侧的相邻瓦片算进来。纬度钳制在 Web Mercator 有效范围 ±MAX_LAT，
    瓦片索引钳制在 [0, 2^z - 1]。跨越反经线（antimeridian）的 bbox 不支持。
    """
    minlat = max(minlat, -MAX_LAT)
    maxlat = min(maxlat, MAX_LAT)
    x0 = int(math.floor(lon2tilex(minlon, z)))
    x1 = int(math.floor(math.nextafter(lon2tilex(maxlon, z), -math.inf)))
    y0 = int(math.floor(lat2tiley(maxlat, z)))  # 北在上
    y1 = int(math.floor(math.nextafter(lat2tiley(minlat, z), -math.inf)))
    n = 2**z
    x0, x1 = max(x0, 0), min(x1, n - 1)
    y0, y1 = max(y0, 0), min(y1, n - 1)
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def render_tile(dem, lons, lats, z, x, y, size=TILE_SIZE):
    """从 (dem, lons, lats) 双线性采样出一张 size×size×3 的 terrain-RGB 瓦片。"""
    west, east = tilex2lon(x, z), tilex2lon(x + 1, z)
    out_lons = np.linspace(west, east, size, endpoint=False) + (east - west) / (2 * size)
    # XYZ 像素在 Web Mercator y 上均匀分布（经度方向线性、纬度方向非线性）：
    # 逐行算分数瓦片 y → 纬度，不能按纬度线性插值
    py = y + (np.arange(size) + 0.5) / size
    out_lats = np.degrees(np.arctan(np.sinh(math.pi - 2 * math.pi * py / 2**z)))
    cols = (out_lons - lons[0]) / (lons[-1] - lons[0]) * (len(lons) - 1)
    rows = (lats[0] - out_lats) / (lats[0] - lats[-1]) * (len(lats) - 1)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    # 边缘策略：DEM 覆盖范围外的像素按海平面（0m）渲染——海岸地图未知即海；
    # 不能用 mode="nearest"（会把 DEM 边缘高程复制成假的台地）
    sampled = map_coordinates(dem, [rr, cc], order=1, mode="constant", cval=0.0)
    v = np.rint((sampled + 10000) * 10).astype(np.int64)
    v = np.clip(v, 0, 0xFFFFFF)  # 与 encode_height 一致的 24bit 钳制
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

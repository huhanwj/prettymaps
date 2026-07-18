"""SRTM 高程：下载/解析 .hgt、山体阴影 PNG、等高线 GeoJSON。

无 rasterio 依赖：.hgt 用 numpy 读，hillshade 用 matplotlib LightSource，
等高线用 matplotlib contour（经纬度网格直接出地理坐标）。
"""

import gzip
import json
import urllib.request
from pathlib import Path

import geopandas as gp
import matplotlib

matplotlib.use("Agg")  # 管线无界面运行
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter
from shapely.geometry import LineString

SKADI_URL = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}/{tile}.hgt.gz"
TILE = "N22E114"  # CUHK 所在 SRTM 瓦片
VOID = -32768


def tile_bounds(tile):
    """'N22E114' -> (west, south, east, north)，瓦片覆盖 1°×1°。"""
    lat = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    lon = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    north = lat + 1 if lat >= 0 else lat
    south = north - 1
    west = lon
    east = lon + 1
    return (float(west), float(south), float(east), float(north))


def download_hgt(tile, dest_dir):
    """从 skadi S3 下载并解压 .hgt，返回本地路径。已存在则跳过。"""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{tile}.hgt"
    if out.exists():
        return out
    url = SKADI_URL.format(ns=tile[:3], tile=tile)
    print(f"[elevation] 下载 {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        payload = resp.read()
    out.write_bytes(gzip.decompress(payload))
    return out


def read_hgt(path):
    """读 .hgt 为 (n, n) float32 数组，第 0 行是北边缘。void 置 nan。"""
    raw = np.fromfile(path, dtype=">i2")
    n = int(round(np.sqrt(raw.size)))
    if n * n != raw.size or n not in (1201, 3601):
        raise ValueError(f"非法 HGT 文件大小：{path} ({raw.size} cells)")
    dem = raw.reshape(n, n).astype(np.float32)
    dem[dem == VOID] = np.nan
    return dem


def fill_voids(dem):
    """nan 用全局均值填充（SRTM 水域常为 void/0，CUHK 山地无大空洞）。"""
    if not np.isnan(dem).any():
        return dem
    fill = np.nanmean(dem)
    return np.where(np.isnan(dem), fill, dem)


def crop_to_bounds(dem, tile, west, south, east, north):
    """把整瓦片裁到目标范围，返回 (dem_crop, lons, lats)（1° 瓦片内）。"""
    tw, ts, te, tn = tile_bounds(tile)
    n = dem.shape[0]

    def col(lon):
        return int(round((lon - tw) / (te - tw) * (n - 1)))

    def row(lat):
        return int(round((tn - lat) / (tn - ts) * (n - 1)))

    c0, c1 = sorted((col(west), col(east)))
    r0, r1 = sorted((row(north), row(south)))
    c0, r0 = max(c0, 0), max(r0, 0)
    c1, r1 = min(c1, n - 1), min(r1, n - 1)
    lons = np.linspace(tw + c0 / (n - 1), tw + c1 / (n - 1), c1 - c0 + 1)
    lats = np.linspace(tn - r0 / (n - 1), tn - r1 / (n - 1), r1 - r0 + 1)
    return dem[r0 : r1 + 1, c0 : c1 + 1], lons, lats


def cellsize_m(lons, lats):
    """经纬度步长换算成米（等距圆柱近似）。"""
    mean_lat = np.deg2rad(np.mean(lats))
    dx = np.abs(lons[1] - lons[0]) * 111320 * np.cos(mean_lat)
    dy = np.abs(lats[1] - lats[0]) * 110540
    return dx, dy


def hillshade_rgba(dem, cellsize_m=30, azdeg=315, altdeg=45, vert_exag=1.5):
    """山体阴影 → RGBA：黑色阴影，alpha 随坡度阴影增强（海面已被置 0 → 无阴影）。"""
    ls = LightSource(azdeg=azdeg, altdeg=altdeg)
    shade = ls.hillshade(dem, vert_exag=vert_exag, dx=cellsize_m, dy=cellsize_m)
    rgba = np.zeros((*shade.shape, 4), dtype=np.uint8)
    rgba[..., 3] = ((1 - shade) * 255 * 0.85).astype(np.uint8)
    return rgba


def contour_lines(dem, lons, lats, interval=10, min_ele=None):
    """等高线 → GeoDataFrame(LineString, 属性 ele)。经纬度网格直接出地理坐标。"""
    lo = float(np.nanmin(dem))
    hi = float(np.nanmax(dem))
    start = max(interval, int(np.ceil(lo / interval)) * interval)
    if min_ele is not None:
        start = max(start, min_ele)
    levels = list(range(int(start), int(hi) + 1, interval))
    X, Y = np.meshgrid(lons, lats)
    cs = plt.contour(X, Y, dem, levels=levels)
    rows = []
    for level, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            if len(seg) >= 2:
                rows.append({"ele": int(level), "geometry": LineString(seg)})
    plt.close("all")
    return gp.GeoDataFrame(rows, crs="EPSG:4326")


def build_elevation_products(boundary_gdf, cache_dir, out_dir, interval=10):
    """主流程：下载瓦片 → 裁剪到边界 bbox(含 5% 余量) → 填洞/平滑 →
    写出 hillshade.png + hillshade.json（四角坐标）+ contours.geojson。"""
    hgt = download_hgt(TILE, Path(cache_dir) / "srtm")
    dem = read_hgt(hgt)

    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    dem, lons, lats = crop_to_bounds(
        dem, TILE, minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y
    )
    dem = fill_voids(dem)
    dem = np.clip(dem, 0, None)  # 海面置 0
    dem = gaussian_filter(dem, sigma=2)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgba = hillshade_rgba(dem, cellsize_m=cellsize_m(lons, lats)[0])
    plt.imsave(out_dir / "hillshade.png", rgba)
    coords = [
        [float(lons[0]), float(lats[0])],  # NW
        [float(lons[-1]), float(lats[0])],  # NE
        [float(lons[-1]), float(lats[-1])],  # SE
        [float(lons[0]), float(lats[-1])],  # SW
    ]
    (out_dir / "hillshade.json").write_text(
        json.dumps({"coordinates": coords}), encoding="utf-8"
    )

    contours = contour_lines(dem, lons, lats, interval=interval, min_ele=10)
    contours.to_file(out_dir / "contours.geojson", driver="GeoJSON")
    print(f"[elevation] hillshade {rgba.shape[:2]}, 等高线 {len(contours)} 条")
    return contours

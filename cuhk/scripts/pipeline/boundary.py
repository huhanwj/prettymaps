"""CUHK 校园边界：Overpass 直查 relation 7802779，组装多边形，米制 buffer。

Nominatim 在本机不可达，因此不用 osmnx geocoder；一律走 OverpassClient。
"""

from pathlib import Path

import geopandas as gp
from shapely import make_valid
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

CUHK_RELATION_ID = 7802779
FALLBACK_PATH = Path(__file__).resolve().parents[2] / "data" / "boundary_fallback.geojson"


def assemble_multipolygon(relation):
    """把 Overpass `out geom` 的 relation JSON 组装成 shapely 多边形（含洞）。"""
    outers, inners = [], []
    for member in relation["members"]:
        if member["type"] != "way" or "geometry" not in member:
            continue
        coords = [(p["lon"], p["lat"]) for p in member["geometry"]]
        if member["role"] == "outer":
            outers.append(coords)
        elif member["role"] == "inner":
            inners.append(coords)

    outer_rings = list(polygonize(outers))
    if not outer_rings:
        raise ValueError("relation 的 outer ways 无法拼成闭合多边形")
    shell = unary_union(outer_rings)

    holes = []
    for ring in polygonize(inners):
        holes.append(list(ring.exterior.coords))

    # shell 可能是 Polygon 或 MultiPolygon；洞统一扣掉
    result = shell
    for hole in holes:
        result = result.difference(Polygon(hole))

    result = make_valid(result)
    if not result.is_valid:
        raise ValueError("assembled boundary is invalid")
    return result


def buffer_polygon_meters(geom, meters):
    """在投影坐标系（自动选 UTM）下 buffer，返回 EPSG:4326 多边形。"""
    gdf = gp.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
    projected = gdf.to_crs(gdf.estimate_utm_crs())
    projected["geometry"] = projected.geometry.buffer(meters)
    return projected.to_crs("EPSG:4326").geometry.iloc[0]


def fetch_campus_boundary(client, buffer_m=800):
    """主流程：Overpass 取 relation → 组装 → buffer → GeoDataFrame(4326)。
    失败时回退到 cuhk/data/boundary_fallback.geojson（fallback 仍为未 buffer 边界，
    buffer 在此函数中统一应用）。"""
    ql = f"[out:json][timeout:60];relation({CUHK_RELATION_ID});out geom;"
    try:
        payload = client.query(ql)
        geom = assemble_multipolygon(payload["elements"][0])
    except RuntimeError as e:
        if not FALLBACK_PATH.exists():
            raise RuntimeError(
                f"Overpass 取边界失败且无 fallback 文件：{e}"
            ) from e
        print(f"[boundary] Overpass 失败（{e}），使用 fallback 文件")
        geom = gp.read_file(FALLBACK_PATH).geometry.iloc[0]

    if buffer_m:
        geom = buffer_polygon_meters(geom, buffer_m)
    return gp.GeoDataFrame(geometry=[geom], crs="EPSG:4326")

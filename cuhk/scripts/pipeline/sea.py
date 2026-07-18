"""海面多边形：bbox - 海岸线 → 候选面 → 排除与非桥车行道相交的一侧。

移植自 prettymaps fetch.py 的 sea 逻辑；桥（bridge=* 非空且非 no，含
yes/viaduct 等）跨水不算陆侧——原 prettymaps 只认 bridge=yes，大老山公路
高架段 bridge=viaduct 会把吐露港误判成陆地，这里按 OSM 语义放宽。
"""

import geopandas as gp
import osmnx as ox
import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union


def sea_candidates(bbox_polygon, coastline_gdf):
    """bbox 减海岸线 buffer，返回候选多边形列表。"""
    coastline = unary_union(list(coastline_gdf.geometry))
    diff = bbox_polygon.difference(coastline.buffer(1e-9))
    if diff.is_empty:
        return []
    if diff.geom_type == "Polygon":
        return [diff]
    return list(diff.geoms)


def _is_bridge(value):
    """OSM bridge 语义：非空且非 no 即桥（yes/viaduct/aqueduct/...）。"""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return False
    return str(value).strip().lower() not in ("", "no", "nan", "none")


def pick_sea_side(candidates, roads_gdf, crs="EPSG:4326"):
    """排除与非桥车行道路相交的候选面，剩下的合并为海面 GeoDataFrame。"""
    def on_land(candidate):
        hit = roads_gdf.geometry.intersects(candidate)
        if not hit.any():
            return False
        if "bridge" not in roads_gdf.columns:
            return True
        return not all(_is_bridge(v) for v in roads_gdf.loc[hit, "bridge"])

    sea_parts = [c for c in candidates if not on_land(c)]
    if not sea_parts:
        return gp.GeoDataFrame(geometry=[], crs=crs)
    merged = unary_union(sea_parts)
    return gp.GeoDataFrame(geometry=[merged], crs=crs)


def fetch_sea(boundary_gdf):
    """主流程：以边界的外接矩形为 bbox 抓海岸线和车行网，返回海面 gdf。"""
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    bbox_polygon = box(minx, miny, maxx, maxy)

    try:
        coastline = ox.features_from_polygon(bbox_polygon, tags={"natural": "coastline"})
    except ox._errors.InsufficientResponseError:
        print("[sea] 范围内无海岸线，返回空海面")
        return gp.GeoDataFrame(geometry=[], crs="EPSG:4326")

    coastline = coastline[coastline.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    if coastline.empty:
        print("[sea] 范围内无海岸线，返回空海面")
        return gp.GeoDataFrame(geometry=[], crs="EPSG:4326")

    candidates = sea_candidates(bbox_polygon, coastline)
    graph = ox.graph_from_polygon(
        bbox_polygon, network_type="drive", truncate_by_edge=True
    )
    roads = ox.graph_to_gdfs(graph, nodes=False)
    sea_gdf = pick_sea_side(candidates, roads, crs="EPSG:4326")
    # 海面为 bbox 矩形中海岸线以外的一侧，前端直接展示
    if not sea_gdf.empty:
        area = sea_gdf.to_crs(sea_gdf.estimate_utm_crs()).area.sum()
        print(f"[sea] 海面面积 {area:.0f} m²")
    else:
        print("[sea] 无海面")
    return sea_gdf

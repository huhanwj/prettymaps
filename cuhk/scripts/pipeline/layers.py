"""OSM 图层抓取：tag 组合（沿用 prettymaps default preset）+ 道路分级 + 边界裁剪。

osmnx 自带 HTTP 缓存，cache_folder 指到 cuhk/cache/osmnx，重复跑不重抓。
"""

import geopandas as gp
import osmnx as ox
import pandas as pd

ox.settings.use_cache = True
ox.settings.cache_folder = None  # 由 fetch_all_layers 按 cache_dir 设置

LAYER_TAGS = {
    "buildings": {"building": True},
    "roads": {"highway": True},
    "railway": {"railway": ["rail", "light_rail"]},
    "water": {"natural": ["water", "bay"]},
    "waterway": {"waterway": ["river", "stream", "drain"]},
    "forest": {"landuse": "forest"},
    "green": {
        "landuse": ["grass", "orchard", "meadow"],
        "natural": ["wood", "wetland"],
        "leisure": [
            "garden", "golf_course", "park", "pitch", "sports_centre", "track",
        ],
    },
    "beach": {"natural": "beach"},
    "parking": {"amenity": "parking"},
}

ROAD_CLASS = {
    "motorway": "major", "trunk": "major", "primary": "major",
    "secondary": "medium", "tertiary": "medium",
    "residential": "minor", "unclassified": "minor", "service": "minor",
    "living_street": "minor",
    "pedestrian": "path", "footway": "path", "path": "path",
    "track": "path", "cycleway": "path",
    "steps": "steps",
}


def classify_roads(gdf):
    """按 highway 标签给道路分级：major/medium/minor/path/steps。
    highway 列可能是 list（双向不同值），取第一个能匹配上的。"""
    def to_class(value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v in ROAD_CLASS:
                return ROAD_CLASS[v]
        return "minor"

    gdf = gdf.copy()
    gdf["road_class"] = gdf["highway"].map(to_class)
    return gdf


def clip_to_boundary(gdf, boundary_gdf):
    """要素与边界求交，丢掉空几何。"""
    if gdf.empty:
        return gdf
    boundary = boundary_gdf.geometry.union_all()
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.intersection(boundary)
    gdf = gdf[~gdf.geometry.is_empty]
    return gdf.reset_index(drop=True)


def fetch_all_layers(boundary_gdf, cache_dir):
    """抓取全部图层，返回 {layer_name: GeoDataFrame}（已裁剪到边界）。"""
    ox.settings.cache_folder = str(cache_dir / "osmnx")
    polygon = boundary_gdf.geometry.union_all()
    out = {}
    for name, tags in LAYER_TAGS.items():
        try:
            gdf = ox.features_from_polygon(polygon, tags=tags)
        except Exception as e:
            print(f"[layers] {name} 抓取失败：{e}")
            gdf = gp.GeoDataFrame(geometry=[], crs="EPSG:4326")
        # 只保留面（水/绿地）或线（道路/铁路/水道）或混合；osmnx 会混入点
        if name in ("roads", "railway", "waterway") and not gdf.empty:
            gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]
        elif not gdf.empty:
            gdf = gdf[
                gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon", "LineString"])
            ]
        if name == "roads" and not gdf.empty:
            gdf = classify_roads(gdf)
        out[name] = clip_to_boundary(gdf, boundary_gdf)
        print(f"[layers] {name}: {len(out[name])} 要素")
    return out

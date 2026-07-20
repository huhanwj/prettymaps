"""OSM 图层抓取：tag 组合（沿用 prettymaps default preset）+ 道路分级 + 边界裁剪。

osmnx 自带 HTTP 缓存，cache_folder 指到 cuhk/cache/osmnx，重复跑不重抓。
"""

from pathlib import Path

import geopandas as gp
import osmnx as ox
import pandas as pd
from shapely.geometry import Polygon


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
            "garden", "golf_course", "park", "pitch", "sports_centre",
            "swimming_pool", "track",
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

SPORTS_LEISURE = {"pitch", "track", "sports_centre", "stadium", "swimming_pool"}
PEDESTRIAN_HIGHWAYS = {"pedestrian", "footway", "path", "steps", "cycleway"}


def _tag_values(value):
    return value if isinstance(value, (list, tuple, set)) else [value]


def split_green_and_sports(gdf):
    """把运动场地从普通绿地拆出，避免白色底图吞掉体育设施。"""
    if gdf.empty:
        sports = gdf.copy()
        sports["sports_kind"] = pd.Series(dtype=str)
        return gdf.copy(), sports
    leisure = gdf.get("leisure", pd.Series(None, index=gdf.index))
    sports_mask = leisure.map(
        lambda value: any(str(item) in SPORTS_LEISURE for item in _tag_values(value))
    )
    sports = gdf.loc[sports_mask].copy()
    sports["sports_kind"] = leisure.loc[sports_mask].map(
        lambda value: (
            "pool" if "swimming_pool" in {str(item) for item in _tag_values(value)}
            else "track" if "track" in {str(item) for item in _tag_values(value)}
            else "field"
        )
    )
    # OSM athletic tracks are commonly mapped as polygon rings.  Export their
    # interior rings as explicit fields so renderers always show a pale-green
    # centre instead of treating the whole stadium as the orange track.
    interior_fields = []
    for _, row in sports.loc[sports["sports_kind"] == "track"].iterrows():
        geometry = row.geometry
        if geometry.geom_type == "Polygon":
            polygons = [geometry]
        elif geometry.geom_type == "MultiPolygon":
            polygons = list(geometry.geoms)
        else:
            continue
        for polygon in polygons:
            for interior in polygon.interiors:
                field = row.copy()
                field["geometry"] = Polygon(interior)
                field["sports_kind"] = "field"
                interior_fields.append(field)
    if interior_fields:
        sports = gp.GeoDataFrame(
            pd.concat(
                [sports, gp.GeoDataFrame(interior_fields, crs=sports.crs)],
                ignore_index=True,
            ),
            crs=sports.crs,
        )
    return gdf.loc[~sports_mask].copy(), sports


def remove_green_courtyards(green, official_buildings, building_codes):
    """Remove green polygons occupying selected, now-paved building courtyards."""
    if green.empty or official_buildings.empty:
        return green.copy()
    targets = official_buildings.loc[
        official_buildings["bldg_code"].isin(building_codes), "geometry"
    ]
    if targets.empty:
        return green.copy()
    remove_mask = green.geometry.map(
        lambda polygon: any(polygon.covers(point) for point in targets)
    )
    return green.loc[~remove_mask].copy()


def classify_roads(gdf):
    """按 highway 标签给道路分级：major/medium/minor/path/steps。
    highway 列可能是 list（双向不同值），取第一个能匹配上的。"""
    def to_class(value):
        values = value if isinstance(value, list) else [value]
        for v in values:
            normalized = v.removesuffix("_link") if isinstance(v, str) else v
            if normalized in ROAD_CLASS:
                return ROAD_CLASS[normalized]
        return "minor"

    def positive_layer(value):
        for item in _tag_values(value):
            try:
                if float(item) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def is_yes(value):
        return any(
            str(item).strip().lower() in {"yes", "true", "1"}
            for item in _tag_values(value)
        )

    def pedestrian_kind(row):
        highways = {str(v).strip().lower() for v in _tag_values(row.get("highway"))}
        if not highways & PEDESTRIAN_HIGHWAYS:
            return ""
        if "steps" in highways:
            return "stairs"
        if is_yes(row.get("bridge")) or positive_layer(row.get("layer")):
            return "bridge"
        return "path"

    def drive_direction(row):
        values = {str(item).strip().lower() for item in _tag_values(row.get("oneway"))}
        if values & {"-1", "reverse"}:
            return "reverse"
        if values & {"yes", "true", "1"}:
            return "forward"
        if values & {"no", "false", "0"}:
            return "both"
        junctions = {str(item).strip().lower() for item in _tag_values(row.get("junction"))}
        return "forward" if "roundabout" in junctions else "both"

    gdf = gdf.copy()
    gdf["road_class"] = gdf["highway"].map(to_class)
    gdf["pedestrian_kind"] = gdf.apply(pedestrian_kind, axis=1)
    gdf["drive_direction"] = gdf.apply(drive_direction, axis=1)
    return gdf


def clip_to_boundary(gdf, boundary_gdf):
    """要素与边界求交，丢掉空几何。"""
    assert gdf.crs == boundary_gdf.crs, "gdf and boundary_gdf must have the same CRS"
    if gdf.empty:
        return gdf
    boundary = boundary_gdf.geometry.union_all()
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.intersection(boundary)
    gdf = gdf[~gdf.geometry.is_empty]
    return gdf.reset_index(drop=True)


def fetch_all_layers(boundary_gdf, cache_dir):
    """抓取全部图层，返回 {layer_name: GeoDataFrame}（已裁剪到边界）。"""
    cache_dir = Path(cache_dir)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(cache_dir / "osmnx")
    polygon = boundary_gdf.geometry.union_all()
    out = {}
    for name, tags in LAYER_TAGS.items():
        try:
            gdf = ox.features_from_polygon(polygon, tags=tags)
        except ox._errors.InsufficientResponseError:
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

"""POI 解析：pois.yml → pois.geojson。

定位二选一：lon/lat 直接给点；osm_name 与抓取的命名要素做模糊匹配，
取匹配要素的 representative_point()（保证落在要素内部）。
匹配失败的条目全量报错（不静默丢弃）。
"""

import difflib
from pathlib import Path

import geopandas as gp
import osmnx as ox
import pandas as pd
import yaml
from shapely.geometry import Point

REQUIRED_FIELDS = {"id", "name_zh", "name_en", "category", "desc"}
CATEGORIES = {"study", "life", "sports", "transport", "landmark"}
MATCH_THRESHOLD = 0.55

NAME_TAGS = {
    "amenity": True, "building": True, "leisure": True, "tourism": True,
    "railway": True, "shop": True, "office": True, "historic": True,
    "man_made": True, "natural": True,
}


def _cache_folder():
    return Path(__file__).resolve().parents[2] / "cache" / "osmnx"


def load_pois(path):
    """加载并校验 pois.yml，返回条目列表。"""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or not isinstance(data.get("pois"), list):
        raise ValueError("pois.yml 缺少 pois 列表")
    entries = data["pois"]
    ids = set()
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError(f"POI 条目必须是 mapping：{e!r}")
        missing = REQUIRED_FIELDS - set(e)
        if missing:
            raise ValueError(f"POI {e.get('id', '?')} 缺字段：{missing}")
        if e["category"] not in CATEGORIES:
            raise ValueError(f"POI {e['id']} 类别非法：{e['category']}")
        if "osm_name" in e and (
            not isinstance(e["osm_name"], str) or not e["osm_name"].strip()
        ):
            raise ValueError(f"POI {e['id']} osm_name 必须是非空字符串")
        if "lon" in e or "lat" in e:
            if not ("lon" in e and "lat" in e):
                raise ValueError(f"POI {e['id']} lon/lat 必须成对给出")
            lon, lat = e["lon"], e["lat"]
            numeric = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in (lon, lat)
            )
            if not numeric or not (113.8 <= lon <= 114.5 and 22.1 <= lat <= 22.6):
                raise ValueError(f"POI {e['id']} 经纬度越出香港范围：{lon}, {lat}")
        if not (("lon" in e and "lat" in e) or "osm_name" in e):
            raise ValueError(f"POI {e['id']} 必须给 lon/lat 或 osm_name")
        if e["id"] in ids:
            raise ValueError(f"POI id 重复：{e['id']}")
        ids.add(e["id"])
    return entries


def fetch_named_features(boundary_gdf):
    """抓边界内所有带名字的要素（一次大请求，osmnx 缓存）。"""
    ox.settings.use_cache = True
    cache = _cache_folder()
    cache.mkdir(parents=True, exist_ok=True)
    ox.settings.cache_folder = str(cache)

    polygon = boundary_gdf.geometry.union_all()
    try:
        gdf = ox.features_from_polygon(polygon, tags=NAME_TAGS)
    except ox._errors.InsufficientResponseError:
        return gp.GeoDataFrame(geometry=[], crs="EPSG:4326")
    if gdf.empty:
        return gdf
    has_name = pd.Series(False, index=gdf.index)
    for col in ("name", "name:en", "name:zh"):
        if col in gdf.columns:
            has_name |= gdf[col].notna()
    return gdf[has_name]


def _similarity(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _match_feature(osm_name, features):
    """在要素的 name/name:en/name:zh 中找最佳匹配，返回 (row, score)。"""
    best_row, best_score = None, 0.0
    for _, row in features.iterrows():
        candidates = [
            str(row[c]) for c in ("name", "name:en", "name:zh")
            if c in row and pd.notna(row[c])
        ]
        score = max((_similarity(osm_name, c) for c in candidates), default=0.0)
        if score > best_score:
            best_row, best_score = row, score
    return best_row, best_score


def resolve_pois(entries, features):
    """条目 → 点要素。返回 (GeoDataFrame, unmatched_id_list)。"""
    rows, unmatched = [], []
    for e in entries:
        if "lon" in e and "lat" in e:
            point = Point(e["lon"], e["lat"])
        else:
            row, score = _match_feature(e["osm_name"], features)
            if row is None or score < MATCH_THRESHOLD:
                unmatched.append(e["id"])
                continue
            point = row.geometry.representative_point()
        rows.append({
            "id": e["id"],
            "name_zh": e["name_zh"],
            "name_en": e["name_en"],
            "category": e["category"],
            "desc": e["desc"],
            "geometry": point,
        })
    if not rows:
        empty = gp.GeoDataFrame(
            {c: [] for c in ("id", "name_zh", "name_en", "category", "desc")},
            geometry=gp.GeoSeries([], crs="EPSG:4326"),
        )
        return empty, unmatched
    return gp.GeoDataFrame(rows, crs="EPSG:4326"), unmatched

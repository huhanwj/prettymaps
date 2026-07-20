"""提取 OSM 天桥/楼梯，并与官方 PDF 人工校准数据合并。"""

from pathlib import Path

import geopandas as gp
import pandas as pd

VALID_KINDS = {"bridge", "stairs"}
PEDESTRIAN_HIGHWAYS = {"pedestrian", "footway", "path", "steps", "cycleway"}


def _empty_links(crs="EPSG:4326"):
    return gp.GeoDataFrame(
        pd.DataFrame([], columns=["kind", "source", "note", "geometry"]),
        geometry="geometry",
        crs=crs,
    )


def _values(value):
    if isinstance(value, (list, tuple, set)):
        return value
    return [value]


def _has_positive_layer(value):
    for item in _values(value):
        try:
            if float(item) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _is_yes(value):
    return any(str(item).strip().lower() in {"yes", "true", "1"} for item in _values(value))


def extract_osm_links(roads):
    """从道路原始 OSM 标签中提取步行天桥和楼梯。"""
    if roads.empty:
        return _empty_links(roads.crs or "EPSG:4326")
    rows = []
    for _, road in roads.iterrows():
        highways = {str(v).strip().lower() for v in _values(road.get("highway"))}
        if not highways & PEDESTRIAN_HIGHWAYS:
            continue
        if "steps" in highways:
            kind = "stairs"
        elif _is_yes(road.get("bridge")) or _has_positive_layer(road.get("layer")):
            kind = "bridge"
        else:
            continue
        raw_name = road.get("name", "")
        note = "" if pd.isna(raw_name) else str(raw_name)
        rows.append({
            "kind": kind,
            "source": "osm",
            "note": note,
            "geometry": road.geometry,
        })
    if not rows:
        return _empty_links(roads.crs or "EPSG:4326")
    return gp.GeoDataFrame(rows, geometry="geometry", crs=roads.crs)


def load_curated_links(path, boundary):
    """读取并校验人工校准的官方 PDF 行人连接线。"""
    path = Path(path)
    if not path.exists():
        return _empty_links(boundary.crs or "EPSG:4326")
    links = gp.read_file(path)
    if links.empty:
        return _empty_links(boundary.crs or links.crs or "EPSG:4326")
    if "kind" not in links.columns:
        raise ValueError("curated pedestrian links missing kind")
    invalid = sorted(set(links["kind"].astype(str)) - VALID_KINDS)
    if invalid:
        raise ValueError(f"invalid pedestrian link kind: {invalid}")
    if not links.geometry.geom_type.eq("LineString").all():
        raise ValueError("curated pedestrian links geometry must be LineString")
    if links.crs is None:
        raise ValueError("curated pedestrian links require a CRS")
    links = links.to_crs(boundary.crs)
    campus = boundary.geometry.union_all()
    if not links.geometry.within(campus).all():
        raise ValueError("curated pedestrian link outside campus boundary")
    links = links.copy()
    links["source"] = "official_pdf"
    if "note" not in links.columns:
        links["note"] = ""
    links["note"] = links["note"].fillna("").astype(str)
    return links[["kind", "source", "note", "geometry"]]


def merge_links(osm, curated, duplicate_distance_m=8):
    """合并连接线；同类近似重复时保留人工 PDF 记录。"""
    if curated.empty:
        return osm[["kind", "source", "note", "geometry"]].copy()
    if osm.empty:
        return curated[["kind", "source", "note", "geometry"]].copy()
    if osm.crs != curated.crs:
        osm = osm.to_crs(curated.crs)
    combined = gp.GeoDataFrame(
        pd.concat([curated, osm], ignore_index=True), geometry="geometry", crs=curated.crs
    )
    metric = combined.to_crs(combined.estimate_utm_crs())
    curated_count = len(curated)
    keep = list(range(curated_count))
    for i in range(curated_count, len(metric)):
        candidate = metric.iloc[i]
        duplicate = False
        for j in keep:
            existing = metric.iloc[j]
            if candidate["kind"] != existing["kind"]:
                continue
            if candidate.geometry.hausdorff_distance(existing.geometry) <= duplicate_distance_m:
                duplicate = True
                break
        if not duplicate:
            keep.append(i)
    return combined.iloc[keep].reset_index(drop=True)[["kind", "source", "note", "geometry"]]


def select_v3_links(osm, curated):
    """V3 严格采用官方 PDF 校准线；OSM 仅保留为未来审计输入。"""
    del osm
    return curated[["kind", "source", "note", "geometry"]].copy().reset_index(drop=True)

"""建筑功能分类：官方建筑点 → OSM 建筑面匹配，写入 bt 属性。

规则：hostel_type ∈ {"1","2","3"} → dorm；名称含 College → college；Sports/Pool/Gym/Field → sports；
Library/Museum/Gallery → study；其余 → other（保留红/棕交替色）。
官方 type 字段是住宿类型代码，不能用作功能分类。
College 优先于 sports/study 是刻意的取舍：书院建筑按书院色，面向迎新地图更合理。
"""

import re

import pandas as pd

SPORTS_RE = re.compile(r"\b(?:Sports|Pool|Gym|Field|Playground|Stadium)\b", re.I)
STUDY_RE = re.compile(r"\b(?:Library|Libraries|Museum|Gallery)\b", re.I)
COLLEGE_RE = re.compile(r"\bCollege\b", re.I)

# 官方 DB hostel_type 码表（cuhk_location_db.js）：
#   1=Guests 賓客, 2=Staff 教職員, 3=Students 學生, 4=Others 其他
# 1/2/3 均为住宿 → dorm；4 是"其他"（如 Theology Building），不归宿舍。
DORM_TYPES = {"1", "2", "3"}


def classify_building(name_en, hostel_type):
    if str(hostel_type).strip().lower() in DORM_TYPES:
        return "dorm"
    name = str(name_en or "")
    if COLLEGE_RE.search(name):
        return "college"
    if SPORTS_RE.search(name):
        return "sports"
    if STUDY_RE.search(name):
        return "study"
    return "other"


def assign_attributes(osm_buildings, official_points, max_dist_m=60):
    """OSM 建筑面 ← 官方点两段匹配，返回与 osm 对齐的 bt/campus_id。

    Pass 1 包含优先：点落在面内（UTM 下 within）→ 该面得分类；
    嵌套包含时取质心离点最近的面。
    Pass 2 距离兜底：不在任何面内的点 → 最近质心 ≤max_dist_m。
    同一建筑被多个点命中时严格更近者赢，与点的输入顺序无关。
    """
    if osm_buildings.empty:
        return pd.DataFrame(
            {"bt": pd.Series(dtype=str), "campus_id": pd.Series(dtype=str)},
            index=osm_buildings.index,
        )
    osm_u = osm_buildings.to_crs(osm_buildings.estimate_utm_crs())
    centroids = osm_u.geometry.centroid
    if official_points.empty:
        return pd.DataFrame(
            {"bt": ["other"] * len(osm_u), "campus_id": [""] * len(osm_u)},
            index=osm_buildings.index,
        )
    off_u = official_points.to_crs(osm_u.crs)

    best = {}  # 建筑位置 → (获胜距离, 分类, 区域)；只在严格更近时覆盖
    fallback = []  # 不在任何面内的点，留到 Pass 2
    for _, off in off_u.iterrows():
        cls = classify_building(off.get("name_en"), off.get("hostel_type"))
        raw_campus_id = off.get("campus_id", "")
        campus_id = "" if pd.isna(raw_campus_id) else str(raw_campus_id).strip()
        containing = [i for i, ok in enumerate(osm_u.contains(off.geometry)) if ok]
        if containing:
            i = min(containing, key=lambda j: centroids.iloc[j].distance(off.geometry))
            d = float(centroids.iloc[i].distance(off.geometry))
            if i not in best or d < best[i][0]:
                best[i] = (d, cls, campus_id)
        else:
            fallback.append((off.geometry, cls, campus_id))

    for geom, cls, campus_id in fallback:
        dists = centroids.distance(geom)
        nearest = dists.idxmin()
        d = float(dists.loc[nearest])
        i = osm_u.index.get_loc(nearest)
        if d <= max_dist_m and (i not in best or d < best[i][0]):
            best[i] = (d, cls, campus_id)

    types = ["other"] * len(osm_u)
    campus_ids = [""] * len(osm_u)
    for i, (_, cls, campus_id) in best.items():
        types[i] = cls
        campus_ids[i] = campus_id
    return pd.DataFrame(
        {"bt": types, "campus_id": campus_ids}, index=osm_buildings.index
    )


def assign_types(osm_buildings, official_points, max_dist_m=60):
    """兼容入口：只返回建筑功能分类。"""
    return assign_attributes(osm_buildings, official_points, max_dist_m)["bt"]

"""建筑功能分类：官方建筑点 → OSM 建筑面匹配，写入 bt 属性。

规则：hostel_type 非空 → dorm；名称含 College → college；Sports/Pool/Gym/Field → sports；
Library/Museum/Gallery → study；其余 → other（保留红/棕交替色）。
官方 type 字段是住宿类型，不能用作功能分类（见 v2 计划头注）。
"""

import re

import geopandas as gp

SPORTS_RE = re.compile(r"Sports|Pool|Gym|Field|Playground|Stadium", re.I)
STUDY_RE = re.compile(r"Library|Libraries|Museum|Gallery", re.I)
COLLEGE_RE = re.compile(r"College", re.I)

# 官方 DB hostel_type 码表（cuhk_location_db.js）：
#   1=Guests 賓客, 2=Staff 教職員, 3=Students 學生, 4=Others 其他
# 1/2/3 均为住宿 → dorm；4 是"其他"住宿（如 Theology Building），不归宿舍。
DORM_TYPES = {"student", "staff", "guest", "1", "2", "3"}

PALETTE = {
    "college": "#E8B64C",
    "dorm": "#F2A65A",
    "sports": "#64B96A",
    "study": "#2f6fb5",
}


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


def assign_types(osm_buildings, official_points, max_dist_m=60):
    """OSM 建筑面 ← 最近官方点（UTM 下 ≤max_dist_m），返回与 osm 对齐的 bt Series。"""
    if osm_buildings.empty:
        return gp.pd.Series([], dtype=str)
    osm_u = osm_buildings.to_crs(osm_buildings.estimate_utm_crs())
    centroids = osm_u.geometry.centroid
    result = ["other"] * len(osm_u)
    if official_points.empty:
        return gp.pd.Series(result, index=osm_buildings.index)
    off_u = official_points.to_crs(osm_u.crs)
    for _, off in off_u.iterrows():
        dists = centroids.distance(off.geometry)
        nearest = dists.idxmin()
        if dists.loc[nearest] <= max_dist_m:
            result[osm_u.index.get_loc(nearest)] = classify_building(
                off.get("name_en"), off.get("hostel_type")
            )
    return gp.pd.Series(result, index=osm_buildings.index)

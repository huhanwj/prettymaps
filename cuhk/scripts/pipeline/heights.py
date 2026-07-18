"""建筑高度估算：height 标签 → building:levels × 3 → 默认 8m。

（spec 原本按楼宇类别给默认值；OSM 无可靠类别标签，简化为统一 8m。）
"""

import re

DEFAULT_HEIGHT = 8.0
METERS_PER_LEVEL = 3.0


def _parse_number(value):
    """从 '15' / '12.5 m' / '12,5' 中提取数字；失败返回 None。"""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", str(value))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def estimate_height(row):
    """单行建筑的高度（米）。优先级：height 标签 > levels×3 > 默认。"""
    h = _parse_number(row.get("height"))
    if h is not None and 1 <= h <= 300:
        return h
    levels = _parse_number(row.get("building:levels"))
    if levels is not None and 0 < levels <= 100:
        return levels * METERS_PER_LEVEL
    return DEFAULT_HEIGHT


def add_heights(buildings_gdf):
    """给建筑图层加两列：h（高度）和 c（0/1 交替配色索引，用于红/棕撞色）。"""
    gdf = buildings_gdf.copy()
    gdf["h"] = gdf.apply(estimate_height, axis=1)
    gdf["c"] = range(len(gdf))
    gdf["c"] = gdf["c"] % 2
    return gdf

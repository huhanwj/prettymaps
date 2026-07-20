"""管线产出校验：图层数量下限、香港范围检查、POI 数量下限。

失败即 raise（build 中止），报告行同时返回供打印。
"""

HK_BBOX = (113.8, 22.1, 114.5, 22.6)  # (min_lon, min_lat, max_lon, max_lat)

REQUIRED_MIN = {
    "buildings": 300,
    "roads": 50,
    "green": 20,
    "railway": 1,
    "sea": 1,
    "contours": 5,
    "official_buildings": 150,
    "shuttle_routes": 10,
    "walking": 2,
}
MIN_POIS = 30


def _check_bounds(name, gdf, problems):
    if gdf.empty:
        return
    minx, miny, maxx, maxy = gdf.total_bounds
    lon0, lat0, lon1, lat1 = HK_BBOX
    if not (lon0 <= minx and maxx <= lon1 and lat0 <= miny and maxy <= lat1):
        problems.append(f"{name} 范围越出香港：{gdf.total_bounds}")


def validate(gdfs, pois_gdf):
    """gdfs: {layer: GeoDataFrame}；pois_gdf: GeoDataFrame。返回报告行列表。"""
    problems, report = [], []

    for layer, min_count in REQUIRED_MIN.items():
        gdf = gdfs.get(layer)
        n = 0 if gdf is None else len(gdf)
        if n < min_count:
            problems.append(f"{layer} 只有 {n} 个要素（要求 ≥{min_count}）")
        else:
            report.append(f"OK {layer}: {n} 个要素")

    for name, gdf in gdfs.items():
        if gdf is not None:
            _check_bounds(name, gdf, problems)

    if len(pois_gdf) < MIN_POIS:
        problems.append(f"POI 只有 {len(pois_gdf)} 条（要求 ≥{MIN_POIS}）")
    else:
        report.append(f"OK POI: {len(pois_gdf)} 条")

    if problems:
        raise RuntimeError("校验失败：\n" + "\n".join(problems))
    report.append("全部校验通过")
    return report

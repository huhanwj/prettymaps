import geopandas as gp
from shapely.geometry import LineString, box

from pipeline import sea


def test_sea_candidates_split_by_coastline():
    bbox = box(0, 0, 10, 10)
    # 一条南北向海岸线把 bbox 切成东西两半
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    assert len(candidates) == 2
    areas = sorted([g.area for g in candidates])
    assert abs(sum(areas) - 100) < 1.0  # buffer 极窄，总面积≈bbox


def test_filter_land_side_by_roads():
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    # 车行道路只在西半边（陆侧）
    roads = gp.GeoDataFrame(
        {"geometry": [LineString([(2, 2), (2, 8)])]}, crs="EPSG:4326"
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    # 东半边（不与道路相交）是海
    assert len(sea_gdf) == 1
    assert sea_gdf.geometry.iloc[0].bounds[0] > 5  # minx 在海岸线以东

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


def test_pick_sea_side_all_filtered_returns_empty():
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    # 两条道路分别穿过东西两侧，海面被完全过滤
    roads = gp.GeoDataFrame(
        {
            "geometry": [
                LineString([(2, 2), (2, 8)]),
                LineString([(8, 2), (8, 8)]),
            ]
        },
        crs="EPSG:4326",
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    assert len(sea_gdf) == 0
    assert sea_gdf.empty


def test_pick_sea_side_bridge_over_water_kept():
    """桥（bridge=viaduct 等）跨水不算陆侧——大老山公路高架跨吐露港回归测试。"""
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    roads = gp.GeoDataFrame(
        {
            "bridge": ["viaduct", None],
            "geometry": [
                LineString([(8, 2), (8, 8)]),  # 高架桥跨东侧海面
                LineString([(2, 2), (2, 8)]),  # 普通道路在西侧陆上
            ],
        },
        crs="EPSG:4326",
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    # 东侧虽有桥相交仍是海；西侧有普通道路是陆
    assert len(sea_gdf) == 1
    assert sea_gdf.geometry.iloc[0].bounds[0] > 5  # minx 在海岸线以东


def test_pick_sea_side_mixed_bridge_and_road_is_land():
    """候选面同时被桥和非桥道路相交 → 仍是陆侧。"""
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    roads = gp.GeoDataFrame(
        {
            "bridge": ["yes", None],
            "geometry": [
                LineString([(8, 2), (8, 8)]),
                LineString([(7, 2), (7, 8)]),
            ],
        },
        crs="EPSG:4326",
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    assert len(sea_gdf) == 1
    assert sea_gdf.geometry.iloc[0].bounds[0] < 5
    assert sea_gdf.geometry.iloc[0].bounds[2] < 5.1  # maxx：保留的是西半边


def test_pick_sea_side_list_valued_bridge_kept():
    """osmnx 多重取值 bridge=["viaduct", None]：不崩溃且按桥处理（保留海面）。"""
    bbox = box(0, 0, 10, 10)
    coastline = gp.GeoDataFrame(
        {"geometry": [LineString([(5, -1), (5, 11)])]}, crs="EPSG:4326"
    )
    candidates = sea.sea_candidates(bbox, coastline)
    roads = gp.GeoDataFrame(
        {
            "bridge": [["viaduct", None], None],
            "geometry": [
                LineString([(8, 2), (8, 8)]),  # list 取值的桥跨东侧海面
                LineString([(2, 2), (2, 8)]),  # 普通道路在西侧陆上
            ],
        },
        crs="EPSG:4326",
    )
    sea_gdf = sea.pick_sea_side(candidates, roads, crs="EPSG:4326")
    assert len(sea_gdf) == 1
    assert sea_gdf.geometry.iloc[0].bounds[0] > 5  # minx 在海岸线以东

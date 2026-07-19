import geopandas as gp
import pytest
from shapely.geometry import Point, box

from pipeline import building_types


def test_classify_rules():
    c = building_types.classify_building
    assert c("New Asia College", "") == "college"
    assert c("University Library", "") == "study"
    assert c("Ch'ien Mu Library", "") == "study"
    assert c("University Sports Centre", "") == "sports"
    assert c("University Swimming Pool", "") == "sports"
    assert c("Postgraduate Halls", "3") == "dorm"
    assert c("Staff Quarters", "2") == "dorm"
    # 官方 DB hostel_type 是数字码：1=Guests, 2=Staff, 3=Students（4=Others 不算）
    assert c("Adam Schall Residence", "3") == "dorm"
    assert c("Staff Quarters A", "2") == "dorm"
    assert c("Yali Guest House", "1") == "dorm"
    assert c("Theology Building", "4") == "other"
    assert c("Esther Lee Building", "") == "other"


def test_match_official_to_osm():
    osm = gp.GeoDataFrame(
        {"geometry": [box(114.2000, 22.4100, 114.2010, 22.4110),
                      box(114.2100, 22.4200, 114.2110, 22.4210)]},
        crs="EPSG:4326",
    )
    official = gp.GeoDataFrame(
        {"name_en": ["A", "B"], "hostel_type": ["", "3"],
         "geometry": [Point(114.2005, 22.4105), Point(114.2105, 22.4205)]},
        crs="EPSG:4326",
    )
    bt = building_types.assign_types(osm, official, max_dist_m=60)
    assert list(bt) == ["other", "dorm"]


def test_no_match_stays_other():
    osm = gp.GeoDataFrame({"geometry": [box(114.2, 22.4, 114.21, 22.41)]}, crs="EPSG:4326")
    official = gp.GeoDataFrame(
        {"name_en": ["Far"], "hostel_type": [""],
         "geometry": [Point(114.3, 22.45)]},
        crs="EPSG:4326",
    )
    bt = building_types.assign_types(osm, official, max_dist_m=60)
    assert list(bt) == ["other"]


def test_containment_beats_closer_centroid():
    """官方点在 A 内、但 B 的质心离点更近 → 包含优先，A 得分类，B 保持 other。"""
    osm = gp.GeoDataFrame(
        {"geometry": [box(114.2000, 22.4100, 114.2020, 22.4120),
                      box(114.20015, 22.41015, 114.20025, 22.41025)]},
        crs="EPSG:4326",
    )
    official = gp.GeoDataFrame(
        {"name_en": ["Some Hall"], "hostel_type": ["3"],
         "geometry": [Point(114.2001, 22.4101)]},
        crs="EPSG:4326",
    )
    bt = building_types.assign_types(osm, official, max_dist_m=60)
    assert list(bt) == ["dorm", "other"]


def test_collision_nearest_wins_order_independent():
    """两个官方点命中同一建筑（不同距离）→ 近者的分类赢；交换输入顺序结果相同。"""
    osm = gp.GeoDataFrame(
        {"geometry": [box(114.2000, 22.4100, 114.2010, 22.4110)]}, crs="EPSG:4326"
    )
    near = ("Near Hall", "3", Point(114.2006, 22.4106))    # 面内，距质心 ~15m
    far = ("Far Library", "", Point(114.20105, 22.4105))   # 面外，距质心 ~57m ≤ 60
    for first, second in [(near, far), (far, near)]:
        official = gp.GeoDataFrame(
            {"name_en": [first[0], second[0]],
             "hostel_type": [first[1], second[1]],
             "geometry": [first[2], second[2]]},
            crs="EPSG:4326",
        )
        bt = building_types.assign_types(osm, official, max_dist_m=60)
        assert list(bt) == ["dorm"]

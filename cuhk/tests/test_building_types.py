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
    assert c("Postgraduate Halls", "student") == "dorm"
    assert c("Staff Quarters", "staff") == "dorm"
    # 官方 DB 实际 hostel_type 是数字码：1=Guests, 2=Staff, 3=Students（4=Others 不算）
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
        {"name_en": ["A", "B"], "hostel_type": ["", "student"],
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

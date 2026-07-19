import geopandas as gp
import pytest
from shapely.geometry import LineString, Point, box

from pipeline import validate


def good_gdfs():
    g = lambda geoms: gp.GeoDataFrame({"geometry": geoms}, crs="EPSG:4326")
    return {
        "buildings": g([box(114.20, 22.41, 114.201, 22.411)] * 301),
        "roads": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 51),
        "green": g([box(114.20, 22.41, 114.202, 22.412)] * 21),
        "railway": g([LineString([(114.2, 22.41), (114.21, 22.42)])]),
        "sea": g([box(114.22, 22.41, 114.23, 22.42)]),
        "contours": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 6),
        "official_buildings": g([box(114.20, 22.41, 114.201, 22.411)] * 151),
        "shuttle_routes": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 11),
        "walking": g([LineString([(114.2, 22.41), (114.21, 22.42)])] * 2),
    }


def good_pois():
    return gp.GeoDataFrame(
        {"geometry": [Point(114.2, 22.41)] * 31}, crs="EPSG:4326"
    )


def test_valid_passes():
    report = validate.validate(good_gdfs(), good_pois())
    assert any("OK" in line for line in report)


def test_empty_buildings_fails():
    gdfs = good_gdfs()
    gdfs["buildings"] = gdfs["buildings"].iloc[:0]
    with pytest.raises(RuntimeError, match="buildings"):
        validate.validate(gdfs, good_pois())


def test_out_of_hk_fails():
    gdfs = good_gdfs()
    gdfs["sea"] = gp.GeoDataFrame(
        {"geometry": [box(10.0, 10.0, 11.0, 11.0)]}, crs="EPSG:4326"
    )
    with pytest.raises(RuntimeError, match="香港"):
        validate.validate(gdfs, good_pois())


def test_too_few_pois_fails():
    with pytest.raises(RuntimeError, match="POI"):
        validate.validate(good_gdfs(), good_pois().iloc[:5])

import geopandas as gp
import pandas as pd
from shapely.geometry import LineString, Point, Polygon, box

from pipeline import layers


def test_road_classification():
    gdf = gp.GeoDataFrame(
        {
            "highway": ["primary", "residential", "footway", "steps", "service", "path"],
            "geometry": [LineString([(0, 0), (1, 1)])] * 6,
        },
        crs="EPSG:4326",
    )
    out = layers.classify_roads(gdf)
    assert list(out["road_class"]) == [
        "major", "minor", "path", "steps", "minor", "path",
    ]


def test_clip_to_boundary():
    gdf = gp.GeoDataFrame(
        {"geometry": [box(0, 0, 2, 2), box(10, 10, 11, 11)]}, crs="EPSG:4326"
    )
    boundary = gp.GeoDataFrame({"geometry": [box(1, 1, 3, 3)]}, crs="EPSG:4326")
    out = layers.clip_to_boundary(gdf, boundary)
    assert len(out) == 1
    assert abs(out.geometry.iloc[0].area - 1.0) < 1e-9


def test_layer_tags_complete():
    for name, spec in layers.LAYER_TAGS.items():
        assert spec, f"{name} tags 为空"

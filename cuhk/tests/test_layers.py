import geopandas as gp
from shapely.geometry import LineString, box

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


def test_pedestrian_kind_is_mutually_exclusive_for_path_bridge_and_stairs():
    gdf = gp.GeoDataFrame(
        {
            "highway": ["footway", "footway", "steps", "primary"],
            "bridge": [None, "yes", None, "yes"],
            "layer": [None, "1", None, "1"],
            "geometry": [LineString([(0, 0), (1, 1)])] * 4,
        },
        crs="EPSG:4326",
    )

    out = layers.classify_roads(gdf)

    assert list(out["pedestrian_kind"]) == ["path", "bridge", "stairs", ""]


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


def test_classify_roads_list_value_first_match():
    gdf = gp.GeoDataFrame(
        {"highway": [["primary", "residential"]], "geometry": [LineString([(0, 0), (1, 1)])]},
        crs="EPSG:4326",
    )
    out = layers.classify_roads(gdf)
    assert list(out["road_class"]) == ["major"]


def test_classify_roads_link_normalization():
    gdf = gp.GeoDataFrame(
        {"highway": ["motorway_link", "primary_link", "trunk_link"], "geometry": [LineString([(0, 0), (1, 1)])] * 3},
        crs="EPSG:4326",
    )
    out = layers.classify_roads(gdf)
    assert list(out["road_class"]) == ["major", "major", "major"]


def test_classify_roads_preserves_oneway_and_roundabout_direction():
    gdf = gp.GeoDataFrame(
        {
            "highway": ["service"] * 5,
            "oneway": ["yes", "-1", "no", None, None],
            "junction": [None, None, None, None, "roundabout"],
            "geometry": [LineString([(0, 0), (1, 0)])] * 5,
        },
        crs="EPSG:4326",
    )

    out = layers.classify_roads(gdf)

    assert list(out["drive_direction"]) == [
        "forward", "reverse", "both", "both", "forward",
    ]


def test_fetch_empty_layers(monkeypatch, campus_square, tmp_path):
    boundary_gdf = gp.GeoDataFrame(geometry=[campus_square], crs="EPSG:4326")

    def raise_insufficient(*args, **kwargs):
        raise layers.ox._errors.InsufficientResponseError("no data")

    monkeypatch.setattr(layers.ox, "features_from_polygon", raise_insufficient)
    out = layers.fetch_all_layers(boundary_gdf, tmp_path)
    assert set(out.keys()) == set(layers.LAYER_TAGS.keys())
    for name, gdf in out.items():
        assert gdf.empty, f"{name} should be empty"


def test_split_green_and_sports_keeps_only_generic_land_in_green():
    source = gp.GeoDataFrame(
        {
            "leisure": ["pitch", "track", "swimming_pool", "park", None],
            "landuse": [None, None, None, None, "grass"],
            "geometry": [
                box(114.200, 22.410, 114.201, 22.411),
                box(114.202, 22.410, 114.203, 22.411),
                box(114.204, 22.410, 114.205, 22.411),
                box(114.206, 22.410, 114.207, 22.411),
                box(114.208, 22.410, 114.209, 22.411),
            ],
        },
        crs="EPSG:4326",
    )

    green, sports = layers.split_green_and_sports(source)

    assert list(green["leisure"].fillna("")) == ["park", ""]
    assert list(sports["sports_kind"]) == ["field", "track", "pool"]


def test_green_query_fetches_swimming_pools():
    assert "swimming_pool" in layers.LAYER_TAGS["green"]["leisure"]

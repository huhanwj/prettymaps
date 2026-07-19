import geopandas as gp
import pytest
from shapely.geometry import LineString, box

from pipeline import pedestrian


def _line(y=22.42):
    return LineString([(114.20, y), (114.201, y)])


def test_extract_osm_links_distinguishes_bridge_stairs_and_plain_path():
    roads = gp.GeoDataFrame(
        {
            "highway": ["footway", "steps", "path", "residential"],
            "bridge": ["yes", None, None, "yes"],
            "layer": [None, None, "1", "1"],
            "name": ["Footbridge", "Hill steps", "Raised walk", "Flyover"],
            "geometry": [_line(22.420), _line(22.421), _line(22.422), _line(22.423)],
        },
        crs="EPSG:4326",
    )

    result = pedestrian.extract_osm_links(roads)

    assert list(result["kind"]) == ["bridge", "stairs", "bridge"]
    assert list(result["source"]) == ["osm", "osm", "osm"]
    assert list(result["note"]) == ["Footbridge", "Hill steps", "Raised walk"]


def test_load_curated_links_rejects_unknown_kind(tmp_path):
    path = tmp_path / "links.geojson"
    gp.GeoDataFrame(
        {"kind": ["escalator"], "note": ["bad"], "geometry": [_line()]},
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")
    boundary = gp.GeoDataFrame(geometry=[box(114.19, 22.40, 114.22, 22.44)], crs="EPSG:4326")

    with pytest.raises(ValueError, match="kind"):
        pedestrian.load_curated_links(path, boundary)


def test_load_curated_links_rejects_geometry_outside_campus(tmp_path):
    path = tmp_path / "links.geojson"
    gp.GeoDataFrame(
        {"kind": ["bridge"], "note": ["far"], "geometry": [_line(23.0)]},
        crs="EPSG:4326",
    ).to_file(path, driver="GeoJSON")
    boundary = gp.GeoDataFrame(geometry=[box(114.19, 22.40, 114.22, 22.44)], crs="EPSG:4326")

    with pytest.raises(ValueError, match="campus"):
        pedestrian.load_curated_links(path, boundary)


def test_merge_links_prefers_curated_duplicate():
    osm = gp.GeoDataFrame(
        {"kind": ["bridge"], "source": ["osm"], "note": ["OSM"], "geometry": [_line()]},
        crs="EPSG:4326",
    )
    curated = gp.GeoDataFrame(
        {
            "kind": ["bridge"],
            "source": ["official_pdf"],
            "note": ["PDF"],
            "geometry": [_line()],
        },
        crs="EPSG:4326",
    )

    result = pedestrian.merge_links(osm, curated, duplicate_distance_m=5)

    assert len(result) == 1
    assert result.iloc[0]["source"] == "official_pdf"
    assert result.iloc[0]["note"] == "PDF"

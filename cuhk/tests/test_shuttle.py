from pathlib import Path

import geopandas as gp
import pytest
from shapely.geometry import LineString, Point

from pipeline import official, shuttle


CONFIG = Path(__file__).parents[1] / "data" / "shuttle_routes.yml"


def test_public_route_catalog_and_explicit_constraints():
    config = shuttle.load_config(CONFIG)
    routes = config["routes"]

    assert list(routes) == [
        "1A", "1B", "2", "3", "4", "8",
        "5", "6A", "6B", "7", "N", "H",
    ]
    assert "postgraduate_hall_1" in routes["1B"]["stops"]
    assert "residence_10" not in routes["3"]["stops"]
    assert "area_39_up" not in routes["3"]["stops"]
    assert routes["4"]["stops"].index("cw_chu_down") < routes["4"]["stops"].index("area_39_up")
    assert routes["5"]["stops"][-1] == "cw_chu_down"
    assert routes["5"]["departures"] == [18, 22, 26]
    assert routes["6A"]["stops"][0] == "cw_chu_down"
    assert routes["6B"]["stops"][-2:] == ["station_piazza", "chung_chi_teaching"]
    assert routes["7"]["stops"][-2:] == ["station_piazza", "chung_chi_teaching"]
    assert "residence_10" not in routes["N"]["stops"]
    assert routes["H"]["stops"][0] == "residence_10"


def sample_roads_with_residence_10_spur():
    return gp.GeoDataFrame(
        {"road_class": ["minor", "minor", "minor"]},
        geometry=[
            LineString([(0, 0), (2, 0)]),
            LineString([(2, 0), (4, 0)]),
            LineString([(2, 0), (2, 1)]),
        ],
        crs="EPSG:32650",
    )


def test_ordered_route_avoids_unrequested_spur():
    roads = sample_roads_with_residence_10_spur()
    stops = {
        "start": Point(0, 0),
        "middle": Point(2, 0),
        "end": Point(4, 0),
    }

    line = shuttle.build_route_geometry(
        "X", ["start", "middle", "end"], stops, roads, max_snap_m=0.1
    )

    assert list(line.coords)[0] == (0, 0)
    assert list(line.coords)[-1] == (4, 0)
    assert line.distance(Point(2, 1)) > 0.5


def test_disconnected_route_names_failed_stop_pair():
    roads = gp.GeoDataFrame(
        {"road_class": ["minor", "minor"]},
        geometry=[
            LineString([(0, 0), (1, 0)]),
            LineString([(10, 0), (11, 0)]),
        ],
        crs="EPSG:32650",
    )
    stops = {"A": Point(0, 0), "B": Point(11, 0)}

    with pytest.raises(ValueError, match="route X: no road path from A to B"):
        shuttle.build_route_geometry("X", ["A", "B"], stops, roads, max_snap_m=0.1)


def test_variant_insertions_and_tail_replacement():
    base = ["A", "B", "C", "D"]
    inserted = shuttle.variant_stops(base, {"insertions": [{"after": "B", "stop": "X"}]})
    replaced = shuttle.variant_stops(base, {"replace_tail": {"from": "C", "with": ["Y", "Z"]}})

    assert inserted == ["A", "B", "X", "C", "D"]
    assert replaced == ["A", "B", "C", "Y", "Z"]


def test_real_public_products_use_current_ids_and_constraints():
    roads = gp.read_file(Path(__file__).parents[1] / "site" / "data" / "roads.geojson")
    products = shuttle.build_products(
        roads=roads,
        official_db=official.load_official_db(),
        config_path=CONFIG,
    )
    routes = products["shuttle_routes"]
    stops = products["shuttle_stops"]
    base = routes.loc[~routes["is_conditional"]].set_index("route_id")

    assert list(base.index) == [
        "1A", "1B", "2", "3", "4", "8",
        "5", "6A", "6B", "7", "N", "H",
    ]
    assert "postgraduate_hall_1" in base.loc["1B", "stop_ids"]
    assert "residence_10" not in base.loc["3", "stop_ids"]
    assert "residence_10" not in base.loc["N", "stop_ids"]
    assert base.loc["5", "stop_ids"].split("|")[-1] == "cw_chu_down"
    assert base.loc["6A", "stop_ids"].split("|")[0] == "cw_chu_down"
    assert base.loc["6B", "stop_ids"].split("|")[-2:] == ["station_piazza", "chung_chi_teaching"]
    assert base.loc["7", "stop_ids"].split("|")[-2:] == ["station_piazza", "chung_chi_teaching"]
    assert base.loc["H", "stop_ids"].split("|")[0] == "residence_10"
    assert all(set(value.strip("|").split("|")) <= set(shuttle.PUBLIC_ROUTE_IDS) for value in stops["route_ids"])
    assert routes.geometry.is_valid.all()
    assert (~routes.geometry.is_empty).all()

from pathlib import Path

import geopandas as gp
import pytest

from pipeline import boundary


def test_assemble_multipolygon_with_hole(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    # 外正方形面积 0.01*0.01，内洞 0.002*0.002
    assert abs(geom.area - (0.01 * 0.01 - 0.002 * 0.002)) < 1e-12


def test_buffer_polygon_meters(synthetic_relation):
    geom = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    buffered = boundary.buffer_polygon_meters(geom, 800)
    # buffer 后面积必须变大，且仍然合法
    assert buffered.area > geom.area
    assert buffered.is_valid
    # CRS 必须是经纬度
    assert abs(buffered.bounds[0] - 114.2) < 0.05


class FakeSuccessClient:
    def __init__(self, payload):
        self.payload = payload

    def query(self, ql):
        return self.payload


class FakeFailingClient:
    def query(self, ql):
        raise RuntimeError("Overpass down")


def test_fetch_success_path(synthetic_relation):
    client = FakeSuccessClient(synthetic_relation)
    unbuffered = boundary.assemble_multipolygon(synthetic_relation["elements"][0])
    campus = boundary.fetch_campus_boundary(client, buffer_m=800)
    assert isinstance(campus, gp.GeoDataFrame)
    assert campus.crs.to_string() == "EPSG:4326"
    assert campus.geometry.iloc[0].area > unbuffered.area


def test_fetch_fallback_path():
    client = FakeFailingClient()
    fallback = gp.read_file(boundary.FALLBACK_PATH)
    campus = boundary.fetch_campus_boundary(client, buffer_m=800)
    assert isinstance(campus, gp.GeoDataFrame)
    assert campus.crs.to_string() == "EPSG:4326"
    # 800m buffer 会让边界比未 buffer 的 fallback 更宽
    assert campus.total_bounds[0] < fallback.total_bounds[0]
    assert campus.total_bounds[1] < fallback.total_bounds[1]
    assert campus.total_bounds[2] > fallback.total_bounds[2]
    assert campus.total_bounds[3] > fallback.total_bounds[3]


def test_fetch_missing_fallback_raises(monkeypatch):
    monkeypatch.setattr(
        boundary, "FALLBACK_PATH", Path("/nonexistent/fallback.geojson")
    )
    client = FakeFailingClient()
    with pytest.raises(RuntimeError, match="fallback"):
        boundary.fetch_campus_boundary(client, buffer_m=800)


def test_assemble_no_inner_rings(synthetic_relation):
    relation = synthetic_relation["elements"][0]
    relation_no_inner = {
        "type": "relation",
        "id": relation["id"],
        "members": [m for m in relation["members"] if m["role"] != "inner"],
    }
    geom = boundary.assemble_multipolygon(relation_no_inner)
    assert abs(geom.area - (0.01 * 0.01)) < 1e-12
    if geom.geom_type == "Polygon":
        assert len(geom.interiors) == 0
